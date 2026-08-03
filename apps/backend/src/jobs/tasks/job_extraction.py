"""The job-requirement extraction worker task.

Same shape as `jobs/tasks/resume.py`: runs entirely off the request path,
sorts failures into deterministic (fails the job immediately, reverts to
`DRAFT`) vs. transient (retried, then reverted to `DRAFT` only once the
backoff ladder is exhausted — see `_exhausted`, the same helper
`jobs/tasks/verification.py` and `jobs/tasks/interview.py` use). Never
writes a `JobRequirement` row — only `JobPosting.extracted_requirements`,
the draft the confirmation screen reads.
"""

from __future__ import annotations

import uuid

import structlog

from src.db.database import SessionLocal
from src.domains.ai.exceptions import (
    LLMMalformedOutput,
    LLMNotConfigured,
    LLMOutputTruncated,
    LLMRefused,
)
from src.domains.ai.llm import get_job_requirement_extractor
from src.domains.recruiter import service as recruiter_service
from src.domains.recruiter.models import JobPosting
from src.jobs.celery_app import DatabaseTask, NonRetryableJobError, celery_app
from src.platform.models import AsyncJob

logger = structlog.get_logger(__name__)

_DETERMINISTIC_ERRORS = (LLMMalformedOutput, LLMRefused, LLMOutputTruncated, LLMNotConfigured)


def _exhausted(task: DatabaseTask) -> bool:
    request = getattr(task, "request", None)
    if request is None:
        return True
    return request.retries >= task.max_retries


def _load_job_posting_id(async_job_id: str) -> uuid.UUID:
    with SessionLocal() as session:
        job = session.get(AsyncJob, uuid.UUID(async_job_id))
        if job is None or not job.payload:
            raise NonRetryableJobError(f"Job {async_job_id} has no payload")
        return uuid.UUID(job.payload["job_posting_id"])


@celery_app.task(base=DatabaseTask, bind=True, name="src.jobs.tasks.job_extraction.extract_job_requirements_task")
def extract_job_requirements_task(self: DatabaseTask, async_job_id: str) -> dict[str, str]:
    job_posting_id = _load_job_posting_id(async_job_id)

    with SessionLocal() as session:
        posting = session.get(JobPosting, job_posting_id)
        if posting is None:
            raise NonRetryableJobError(f"Job posting {job_posting_id} no longer exists")
        title, description = posting.title, posting.description

    try:
        extraction = get_job_requirement_extractor().extract_requirements(title=title, description=description)
    except _DETERMINISTIC_ERRORS as exc:
        message = getattr(exc, "message", str(exc))
        with SessionLocal() as session:
            posting = session.get(JobPosting, job_posting_id)
            if posting is not None:
                recruiter_service.fail_extraction(session, posting, message)
        logger.warning("job_extraction_failed_permanently", job_posting_id=str(job_posting_id), error=message)
        raise NonRetryableJobError(message) from exc
    except Exception as exc:
        if _exhausted(self):
            with SessionLocal() as session:
                posting = session.get(JobPosting, job_posting_id)
                if posting is not None:
                    recruiter_service.fail_extraction(session, posting, f"{type(exc).__name__}: {exc}")
        logger.warning("job_extraction_retrying", job_posting_id=str(job_posting_id), error=str(exc))
        raise

    with SessionLocal() as session:
        posting = session.get(JobPosting, job_posting_id)
        if posting is not None:
            recruiter_service.apply_extraction_result(session, posting, extraction)

    logger.info("job_requirements_extracted", job_posting_id=str(job_posting_id))
    return {"status": "awaiting_confirmation"}
