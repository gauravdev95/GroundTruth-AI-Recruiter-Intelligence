"""Recruiter job-posting API routes.

Thin by design, matching every other router in this codebase. Every route
resolves the recruiter's own profile via `get_own_recruiter_profile` (a
candidate gets 403 from `require_role` before any handler body runs) and
every job-scoped route resolves via `get_own_job` (another recruiter's job
also gets 403, not 404 — `core/authorization.verify_ownership`).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.domains.auth.models import RecruiterProfile
from src.domains.auth.rate_limit import limiter
from src.domains.recruiter import service
from src.domains.recruiter.dependencies import get_own_job, get_own_recruiter_profile
from src.domains.recruiter.models import JobPosting, JobRequirement
from src.domains.recruiter.schemas import (
    ExtractedRequirementsResponse,
    ExtractedSkillResponse,
    JobCreateRequest,
    JobDetailResponse,
    JobListResponse,
    JobRequirementResponse,
    JobRequirementsConfirmRequest,
    JobResponse,
    JobSubmitAcceptedResponse,
    JobUpdateRequest,
)
from src.domains.skills.models import Skill

router = APIRouter(prefix="/api/v1/recruiter/jobs", tags=["recruiter-jobs"])


def _requirement_responses(db: Session, job: JobPosting) -> list[JobRequirementResponse]:
    rows = db.execute(
        select(JobRequirement, Skill.name)
        .join(Skill, Skill.id == JobRequirement.skill_id)
        .where(JobRequirement.job_posting_id == job.id)
    ).all()
    return [
        JobRequirementResponse(
            id=req.id,
            skill_id=req.skill_id,
            skill_name=name,
            min_proficiency=req.min_proficiency.value,
            is_required=req.is_required,
            weight=float(req.weight),
        )
        for req, name in rows
    ]


def _extracted_requirements_response(job: JobPosting) -> ExtractedRequirementsResponse | None:
    if not job.extracted_requirements:
        return None
    data = job.extracted_requirements
    return ExtractedRequirementsResponse(
        must_have_skills=[ExtractedSkillResponse(**s) for s in data.get("must_have_skills", [])],
        desirable_skills=[ExtractedSkillResponse(**s) for s in data.get("desirable_skills", [])],
        seniority=data.get("seniority", "mid"),
        role_type=data.get("role_type"),
        is_remote=data.get("is_remote", False),
        location_constraints=data.get("location_constraints"),
    )


def _detail_response(db: Session, job: JobPosting) -> JobDetailResponse:
    return JobDetailResponse(
        job=JobResponse.model_validate(job),
        extracted_requirements=_extracted_requirements_response(job),
        requirements=_requirement_responses(db, job),
    )


@router.get("", response_model=JobListResponse)
def list_jobs(
    recruiter: RecruiterProfile = Depends(get_own_recruiter_profile), db: Session = Depends(get_db)
) -> JobListResponse:
    return JobListResponse(jobs=[JobResponse.model_validate(job) for job in service.list_jobs(db, recruiter)])


@router.post("", response_model=JobResponse, status_code=201)
def create_job(
    payload: JobCreateRequest,
    recruiter: RecruiterProfile = Depends(get_own_recruiter_profile),
    db: Session = Depends(get_db),
) -> JobResponse:
    job = service.create_job(db, recruiter, payload)
    return JobResponse.model_validate(job)


@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job(job: JobPosting = Depends(get_own_job), db: Session = Depends(get_db)) -> JobDetailResponse:
    return _detail_response(db, job)


@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    payload: JobUpdateRequest, job: JobPosting = Depends(get_own_job), db: Session = Depends(get_db)
) -> JobResponse:
    updated = service.update_job(db, job, payload)
    return JobResponse.model_validate(updated)


@router.post("/{job_id}/submit", response_model=JobSubmitAcceptedResponse, status_code=202)
@limiter.limit("20/hour")
def submit_job(
    request: Request, job: JobPosting = Depends(get_own_job), db: Session = Depends(get_db)
) -> JobSubmitAcceptedResponse:
    """`draft -> extracting`. 202, same shape as resume upload — the
    response returns before the LLM call happens."""
    result = service.submit_for_extraction(db, job)

    from src.jobs import dispatch as job_dispatch
    from src.jobs.celery_app import QUEUE_EXTRACTION
    from src.jobs.tasks.job_extraction import extract_job_requirements_task

    job_dispatch.dispatch(result.async_job, extract_job_requirements_task, queue=QUEUE_EXTRACTION)

    return JobSubmitAcceptedResponse(
        job=JobResponse.model_validate(result.job), async_job_id=result.async_job.id
    )


@router.post("/{job_id}/requirements/edit", response_model=JobDetailResponse)
def start_requirement_edit(
    job: JobPosting = Depends(get_own_job), db: Session = Depends(get_db)
) -> JobDetailResponse:
    """`published -> awaiting_confirmation`. Returns the *current*
    requirements (not a fresh LLM draft) so the edit screen pre-fills from
    what's actually live."""
    updated = service.start_requirement_edit(db, job)
    return _detail_response(db, updated)


@router.post("/{job_id}/confirm", response_model=JobDetailResponse)
def confirm_requirements(
    payload: JobRequirementsConfirmRequest,
    job: JobPosting = Depends(get_own_job),
    db: Session = Depends(get_db),
) -> JobDetailResponse:
    """`awaiting_confirmation -> published`. Handles both "confirm the
    first extraction" and "re-confirm after editing" — see
    `recruiter/service.py::confirm_requirements`."""
    result = service.confirm_requirements(db, job, payload)

    from src.jobs import dispatch as job_dispatch
    from src.jobs.celery_app import QUEUE_MATCHING
    from src.jobs.tasks.matching import embed_and_match_job_task

    job_dispatch.dispatch(result.async_job, embed_and_match_job_task, queue=QUEUE_MATCHING)

    return _detail_response(db, result.job)


@router.post("/{job_id}/close", response_model=JobResponse)
def close_job(job: JobPosting = Depends(get_own_job), db: Session = Depends(get_db)) -> JobResponse:
    closed = service.close_job(db, job)
    return JobResponse.model_validate(closed)


@router.post("/{job_id}/reopen", response_model=JobResponse)
def reopen_job(job: JobPosting = Depends(get_own_job), db: Session = Depends(get_db)) -> JobResponse:
    result = service.reopen_job(db, job)

    from src.jobs import dispatch as job_dispatch
    from src.jobs.celery_app import QUEUE_MATCHING
    from src.jobs.tasks.matching import embed_and_match_job_task

    job_dispatch.dispatch(result.async_job, embed_and_match_job_task, queue=QUEUE_MATCHING)

    return JobResponse.model_validate(result.job)
