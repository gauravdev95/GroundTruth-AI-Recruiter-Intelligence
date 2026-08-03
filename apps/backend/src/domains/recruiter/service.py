"""Business logic for recruiter job postings.

State machine (see `models.py::JobStatus` and the module docstring in
`router.py` for the endpoint-to-transition mapping):

    draft --submit--> extracting --succeeds--> awaiting_confirmation --confirm--> published
    extracting --fails (any reason)--> draft (+ extraction_error)
    published --edit requirements--> awaiting_confirmation (+ needs_reembedding)
    published --close--> closed
    closed --reopen--> published

`confirm_requirements` is the single function behind **both** "confirm the
LLM's first draft" and "re-confirm after editing a published job's
requirements" — both paths land the job in `AWAITING_CONFIRMATION` first
(`submit_for_extraction`'s success path and `start_requirement_edit`
respectively), so there is exactly one place structured requirements are
ever written, matching the "MANDATORY confirmation screen" requirement:
skills can only ever reach `job_requirements` through this one, human-
reviewed function.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.exceptions import Conflict, NotFound
from src.domains.ai.job_extraction_schema import JobRequirementExtraction
from src.domains.auth.models import RecruiterProfile
from src.domains.recruiter.models import JobPosting, JobRequirement, JobStatus
from src.domains.recruiter.schemas import JobCreateRequest, JobRequirementsConfirmRequest, JobUpdateRequest
from src.domains.skills.models import ProficiencyLevel
from src.domains.verification.skills import get_or_create_skill
from src.platform.models import AsyncJob

logger = structlog.get_logger(__name__)

JOB_TYPE_EXTRACT_REQUIREMENTS = "extract_job_requirements"


class CompanyRequired(Conflict):
    """A recruiter account without a linked company cannot post a job."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_job_for_user(db: Session, job_id: uuid.UUID) -> JobPosting:
    job = db.get(JobPosting, job_id)
    if job is None:
        raise NotFound("Job not found")
    return job


def list_jobs(db: Session, recruiter_profile: RecruiterProfile) -> list[JobPosting]:
    return list(
        db.execute(
            select(JobPosting)
            .where(JobPosting.created_by_user_id == recruiter_profile.user_id)
            .order_by(JobPosting.created_at.desc())
        ).scalars()
    )


def create_job(db: Session, recruiter_profile: RecruiterProfile, payload: JobCreateRequest) -> JobPosting:
    if recruiter_profile.company_id is None:
        raise CompanyRequired("Your recruiter account has no linked company yet")

    job = JobPosting(
        company_id=recruiter_profile.company_id,
        created_by_user_id=recruiter_profile.user_id,
        title=payload.title,
        description=payload.description,
        job_type=payload.job_type,
        experience_level=payload.experience_level,
        location=payload.location,
        is_remote=payload.is_remote,
        deadline=payload.deadline,
        status=JobStatus.DRAFT,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job(db: Session, job: JobPosting, payload: JobUpdateRequest) -> JobPosting:
    if job.status is not JobStatus.DRAFT:
        raise Conflict("Only a draft job's core fields can be edited directly")

    job.title = payload.title
    job.description = payload.description
    job.job_type = payload.job_type
    job.experience_level = payload.experience_level
    job.location = payload.location
    job.is_remote = payload.is_remote
    job.deadline = payload.deadline
    db.commit()
    db.refresh(job)
    return job


@dataclass(frozen=True)
class SubmittedForExtraction:
    job: JobPosting
    async_job: AsyncJob


def submit_for_extraction(db: Session, job: JobPosting) -> SubmittedForExtraction:
    """`draft -> extracting`. Publishing the `AsyncJob` row (not dispatching
    it) happens here, inside the caller's transaction; the router dispatches
    to Celery after commit — same ordering `resume/service.py::create_upload`
    and `interview/service.py::start_interview` already use."""
    if job.status is not JobStatus.DRAFT:
        raise Conflict("Only a draft job can be submitted for extraction")

    job.status = JobStatus.EXTRACTING
    job.extraction_error = None
    db.flush()

    async_job = AsyncJob(job_type=JOB_TYPE_EXTRACT_REQUIREMENTS, payload={"job_posting_id": str(job.id)})
    db.add(async_job)
    db.commit()
    db.refresh(job)
    db.refresh(async_job)
    return SubmittedForExtraction(job=job, async_job=async_job)


def apply_extraction_result(db: Session, job: JobPosting, extraction: JobRequirementExtraction) -> None:
    """Called only from `jobs/tasks/job_extraction.py` — writes the LLM's
    raw output as a draft, never as live `job_requirements` rows."""
    job.extracted_requirements = extraction.model_dump(mode="json")
    job.extraction_error = None
    job.status = JobStatus.AWAITING_CONFIRMATION
    db.commit()


def fail_extraction(db: Session, job: JobPosting, message: str) -> None:
    """`extracting -> draft`, with the error attached so the recruiter can
    see why and resubmit (constraint: a silent extraction error must never
    corrupt matching — reverting to `draft` rather than leaving a job stuck
    `extracting` or auto-publishing a bad draft is what enforces that)."""
    job.status = JobStatus.DRAFT
    job.extraction_error = message
    db.commit()


def start_requirement_edit(db: Session, job: JobPosting) -> JobPosting:
    """`published -> awaiting_confirmation`. Only the status changes here —
    the confirmation screen pre-fills from the *current* `job_requirements`
    rows (still intact), and nothing is unpublished or removed from
    `match_results` until the recruiter actually re-confirms."""
    if job.status is not JobStatus.PUBLISHED:
        raise Conflict("Only a published job's requirements can be edited this way")
    job.status = JobStatus.AWAITING_CONFIRMATION
    db.commit()
    db.refresh(job)
    return job


@dataclass(frozen=True)
class ConfirmedJob:
    job: JobPosting
    async_job: AsyncJob


def confirm_requirements(
    db: Session, job: JobPosting, payload: JobRequirementsConfirmRequest
) -> ConfirmedJob:
    """`awaiting_confirmation -> published`. See module docstring — this is
    the only function that ever writes `job_requirements`."""
    if job.status is not JobStatus.AWAITING_CONFIRMATION:
        raise Conflict("This job has no pending confirmation")

    existing_by_skill_id = {req.skill_id: req for req in job.requirements}
    seen_skill_ids: set[uuid.UUID] = set()
    skill_names: list[tuple[str, bool]] = []

    for item in payload.skills:
        skill = get_or_create_skill(db, item.skill_name)
        seen_skill_ids.add(skill.id)
        skill_names.append((skill.name, item.is_required))
        proficiency = ProficiencyLevel(item.min_proficiency)

        current = existing_by_skill_id.get(skill.id)
        if current is not None:
            current.min_proficiency = proficiency
            current.is_required = item.is_required
            current.weight = item.weight
        else:
            db.add(
                JobRequirement(
                    job_posting_id=job.id,
                    skill_id=skill.id,
                    min_proficiency=proficiency,
                    is_required=item.is_required,
                    weight=item.weight,
                )
            )

    for skill_id, requirement in existing_by_skill_id.items():
        if skill_id not in seen_skill_ids:
            db.delete(requirement)

    job.embedding_text = _build_embedding_text(job, skill_names)
    job.needs_reembedding = True
    job.status = JobStatus.PUBLISHED
    if job.published_at is None:
        job.published_at = _utcnow()
    db.flush()

    # Same durable-row-before-dispatch ordering as `submit_for_extraction`:
    # the AsyncJob is committed alongside the publish itself, and the
    # router dispatches it to Celery only after this transaction lands.
    async_job = AsyncJob(job_type="embed_and_match_job", payload={"job_posting_id": str(job.id)})
    db.add(async_job)
    db.commit()
    db.refresh(job)
    db.refresh(async_job)

    logger.info("job_published", job_id=str(job.id), skill_count=len(skill_names))
    return ConfirmedJob(job=job, async_job=async_job)


def close_job(db: Session, job: JobPosting) -> JobPosting:
    if job.status is not JobStatus.PUBLISHED:
        raise Conflict("Only a published job can be closed")
    job.status = JobStatus.CLOSED
    job.closed_at = _utcnow()
    db.commit()

    # A closed job is matched to nobody — pruned from the shared computation
    # rather than merely hidden, so "below-threshold results go to neither
    # side" also holds for "no-longer-open" results.
    from src.domains.matching import service as matching_service

    matching_service.remove_matches_for_job(db, job.id)

    db.refresh(job)
    return job


def reopen_job(db: Session, job: JobPosting) -> ConfirmedJob:
    """`closed -> published`. Re-triggers matching (not re-embedding
    strictly, but `embed_and_match_job_task` does both and the text hasn't
    changed, so the embedding call is idempotent) since `close_job` pruned
    every `match_results` row for this job."""
    if job.status is not JobStatus.CLOSED:
        raise Conflict("Only a closed job can be reopened")
    job.status = JobStatus.PUBLISHED
    job.closed_at = None
    db.flush()

    async_job = AsyncJob(job_type="embed_and_match_job", payload={"job_posting_id": str(job.id)})
    db.add(async_job)
    db.commit()
    db.refresh(job)
    db.refresh(async_job)
    return ConfirmedJob(job=job, async_job=async_job)


def _build_embedding_text(job: JobPosting, skill_names: list[tuple[str, bool]]) -> str:
    """The confirmed, human-approved text the embedding service actually
    embeds — built from structured fields plus the *confirmed* skill list,
    never the raw LLM draft and never the raw description alone."""
    must_have = [name for name, is_required in skill_names if is_required]
    desirable = [name for name, is_required in skill_names if not is_required]

    lines = [
        f"Title: {job.title}",
        f"Experience level: {job.experience_level.value}",
        f"Job type: {job.job_type.value}",
        f"Location: {'Remote' if job.is_remote else (job.location or 'Not specified')}",
    ]
    if must_have:
        lines.append(f"Must-have skills: {', '.join(must_have)}")
    if desirable:
        lines.append(f"Desirable skills: {', '.join(desirable)}")
    lines.append(f"Description: {job.description}")
    return "\n".join(lines)
