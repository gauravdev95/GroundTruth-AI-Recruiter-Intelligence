"""Job status polling.

The UI polls this while a background job runs. It reads the `async_jobs` row —
the durable record — not the Celery result backend, so a broker restart doesn't
turn a running job into a 404.

Authorization is the awkward part: `async_jobs` has no owner column by design
(§7 — a job's subject lives in its `payload`, because job shapes vary too much
for a fixed FK). Rather than add one, ownership is proved by resolving the
job's subject back to the caller's own identity. A candidate's job names a
`candidate_profile_id`; a recruiter's job (job-requirement extraction) names a
`job_posting_id` whose `created_by_user_id` must be the caller. Either way,
the caller can only poll jobs whose payload names something they own —
constraint: "recruiters access only their own jobs; students get 403", which
falls out of `_owns_job` simply returning `False` for a role/payload
combination that doesn't match (a candidate's token against a
`job_posting_id`-shaped payload matches neither branch).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.exceptions import Conflict, Forbidden, NotFound
from src.db.database import get_db
from src.domains.auth.dependencies import get_current_user
from src.domains.auth.models import CandidateProfile, User, UserRole
from src.domains.recruiter.models import JobPosting
from src.domains.resume.schemas import JobStatusResponse
from src.jobs import dispatch
from src.platform.models import AsyncJobStatus

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _owns_job(db: Session, user: User, payload: dict) -> bool:
    if user.role == UserRole.CANDIDATE:
        candidate_profile_id = payload.get("candidate_profile_id")
        if not candidate_profile_id:
            return False
        profile = db.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == user.id)
        ).scalar_one_or_none()
        return profile is not None and str(profile.id) == candidate_profile_id

    if user.role == UserRole.RECRUITER:
        job_posting_id = payload.get("job_posting_id")
        if not job_posting_id:
            return False
        posting = db.get(JobPosting, uuid.UUID(job_posting_id))
        return posting is not None and posting.created_by_user_id == user.id

    return False


@router.get("/{job_id}", response_model=JobStatusResponse)
def read_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    job = dispatch.get_job(db, job_id)
    if job is None:
        raise NotFound("Job not found")

    payload = job.payload or {}
    if not _owns_job(db, user, payload):
        # 403, not 404 — consistent with `core/authorization.verify_ownership`,
        # which deliberately does not leak whether the resource exists.
        raise Forbidden()

    return JobStatusResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        attempts=job.attempts,
        error=job.error,
        result=job.result,
        is_dead_lettered=job.dead_lettered_at is not None,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
    )


def _task_and_queue_for(job_type: str):
    """Lazily-imported registry (same pattern as `evidence.dispatch_all`) so
    this module doesn't import every task module at process start just to
    support the rare retry path."""
    from src.jobs.celery_app import QUEUE_EXTRACTION, QUEUE_MATCHING, QUEUE_VERIFICATION
    from src.jobs.tasks.interview import evaluate_interview_task, generate_interview_questions_task
    from src.jobs.tasks.job_extraction import extract_job_requirements_task
    from src.jobs.tasks.matching import embed_and_match_candidate_task, embed_and_match_job_task
    from src.jobs.tasks.resume import extract_resume_task
    from src.jobs.tasks.verification import (
        verify_certificate_task,
        verify_coding_platform_account_task,
        verify_experience_task,
        verify_github_account_task,
        verify_repository_task,
    )

    registry = {
        "extract_resume": (extract_resume_task, QUEUE_EXTRACTION),
        "generate_interview_questions": (generate_interview_questions_task, QUEUE_EXTRACTION),
        "evaluate_interview": (evaluate_interview_task, QUEUE_EXTRACTION),
        "extract_job_requirements": (extract_job_requirements_task, QUEUE_EXTRACTION),
        "verify_github_account": (verify_github_account_task, QUEUE_VERIFICATION),
        "verify_coding_platform_account": (verify_coding_platform_account_task, QUEUE_VERIFICATION),
        "verify_repository": (verify_repository_task, QUEUE_VERIFICATION),
        "verify_certificate": (verify_certificate_task, QUEUE_VERIFICATION),
        "verify_experience": (verify_experience_task, QUEUE_VERIFICATION),
        "embed_and_match_job": (embed_and_match_job_task, QUEUE_MATCHING),
        "embed_and_match_candidate": (embed_and_match_candidate_task, QUEUE_MATCHING),
    }
    return registry.get(job_type, (None, None))


@router.post("/{job_id}/retry", response_model=JobStatusResponse)
def retry_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    """Requeue a dead-lettered job — the dead-letter surface's retry action.
    Only a job that actually exhausted retries (`FAILED` + `dead_lettered_at`
    set) is eligible; a still-running or already-succeeded job can't be
    "retried" without risking duplicate side effects."""
    job = dispatch.get_job(db, job_id)
    if job is None:
        raise NotFound("Job not found")

    payload = job.payload or {}
    if not _owns_job(db, user, payload):
        raise Forbidden()

    if job.status != AsyncJobStatus.FAILED or job.dead_lettered_at is None:
        raise Conflict("Only a dead-lettered job can be retried")

    task, queue = _task_and_queue_for(job.job_type)
    if task is None:
        raise Conflict(f"Unknown job type '{job.job_type}' — cannot retry")

    from src.jobs.tasks.dead_letter import requeue_dead_lettered

    requeue_dead_lettered(job.id, db=db)
    db.refresh(job)

    dispatch.dispatch(job, task, queue=queue)

    return JobStatusResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        attempts=job.attempts,
        error=job.error,
        result=job.result,
        is_dead_lettered=job.dead_lettered_at is not None,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
    )


@router.get("", response_model=list[JobStatusResponse])
def list_my_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[JobStatusResponse]:
    """Every async job owned by the caller, most recent first — the
    dead-letter surface reads this and filters client-side for
    `is_dead_lettered`. Filtered at the query layer via the JSONB payload
    (no owner FK exists on `async_jobs` by design — see this module's
    docstring), not fetch-then-filter in Python, so this scales with the
    caller's own job count rather than total platform job volume."""
    from src.platform.models import AsyncJob

    if user.role == UserRole.CANDIDATE:
        profile = db.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == user.id)
        ).scalar_one_or_none()
        if profile is None:
            return []
        query = select(AsyncJob).where(AsyncJob.payload["candidate_profile_id"].astext == str(profile.id))
    elif user.role == UserRole.RECRUITER:
        owned_job_ids = db.execute(
            select(JobPosting.id).where(JobPosting.created_by_user_id == user.id)
        ).scalars().all()
        if not owned_job_ids:
            return []
        query = select(AsyncJob).where(
            AsyncJob.payload["job_posting_id"].astext.in_([str(jid) for jid in owned_job_ids])
        )
    else:
        return []

    rows = list(db.execute(query.order_by(AsyncJob.created_at.desc()).limit(100)).scalars())

    return [
        JobStatusResponse(
            id=row.id,
            job_type=row.job_type,
            status=row.status,
            attempts=row.attempts,
            error=row.error,
            result=row.result,
            is_dead_lettered=row.dead_lettered_at is not None,
            started_at=row.started_at,
            finished_at=row.finished_at,
            created_at=row.created_at,
        )
        for row in rows
    ]
