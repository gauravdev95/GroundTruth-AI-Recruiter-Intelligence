"""The resume extraction worker task.

Runs entirely off the request path: download → parse → LLM → validate → write a
DRAFT row. Nothing here touches a live profile table.

Failure classification is the substance of this module. Every error is sorted
into exactly one of two buckets, because retrying the wrong one is expensive in
opposite directions:

- **Deterministic** (`NonRetryableJobError`): a scanned PDF, an encrypted file,
  malformed model output, a refusal. Re-running produces the identical failure
  while burning LLM quota and delaying the student's error message.
- **Transient** (anything else): timeouts, connection failures, upstream 5xx
  and rate limits. These get the exponential-backoff ladder from
  `DatabaseTask`, then dead-letter.
"""

from __future__ import annotations

import uuid

import structlog

from src.config.config import get_llm_settings
from src.core.exceptions import AppError
from src.db.database import SessionLocal
from src.domains.ai.exceptions import (
    LLMMalformedOutput,
    LLMNotConfigured,
    LLMOutputTruncated,
    LLMRefused,
)
from src.domains.ai.llm import get_resume_extractor
from src.domains.resume.models import (
    ResumeExtractionDraft,
    ResumeUpload,
    ResumeUploadStatus,
)
from src.domains.resume.parsing import (
    NoTextContent,
    UnparseableDocument,
    UnsupportedFileType,
    extract_text,
)
from src.domains.storage import client as storage
from src.jobs.celery_app import DatabaseTask, NonRetryableJobError, celery_app
from src.platform.models import AsyncJob

logger = structlog.get_logger(__name__)

# Failures that will recur identically on a retry.
_DETERMINISTIC_ERRORS = (
    UnparseableDocument,
    NoTextContent,
    UnsupportedFileType,
    LLMMalformedOutput,
    LLMRefused,
    LLMOutputTruncated,
    LLMNotConfigured,
)


def _fail_upload(upload_id: uuid.UUID, message: str) -> None:
    """Record a student-facing failure on the upload row.

    Written in its own session so it survives whatever rollback the task's own
    session is doing.
    """
    with SessionLocal() as session:
        upload = session.get(ResumeUpload, upload_id)
        if upload is None:
            return
        upload.status = ResumeUploadStatus.FAILED
        upload.error = message
        session.commit()


@celery_app.task(
    base=DatabaseTask,
    bind=True,
    name="src.jobs.tasks.resume.extract_resume_task",
)
def extract_resume_task(self: DatabaseTask, async_job_id: str) -> dict[str, str]:
    """Download, parse, extract, and store a draft. Never writes a live profile."""
    settings = get_llm_settings()

    with SessionLocal() as session:
        job = session.get(AsyncJob, uuid.UUID(async_job_id))
        if job is None or not job.payload:
            raise NonRetryableJobError(f"Job {async_job_id} has no payload")
        payload = dict(job.payload)

    upload_id = uuid.UUID(payload["resume_upload_id"])
    candidate_profile_id = uuid.UUID(payload["candidate_profile_id"])
    object_key = payload["object_key"]
    content_type = payload["content_type"]

    with SessionLocal() as session:
        upload = session.get(ResumeUpload, upload_id)
        if upload is None:
            raise NonRetryableJobError(f"Resume upload {upload_id} no longer exists")
        upload.status = ResumeUploadStatus.PROCESSING
        upload.error = None
        session.commit()

    try:
        # Storage faults are transient and fall through to the retry ladder.
        raw = storage.download_bytes(object_key)

        # Deterministic from here: a file that fails to parse fails identically
        # every time, so these are re-raised as non-retryable below.
        text = extract_text(raw, content_type)

        extraction = get_resume_extractor().extract_resume(text)

    except _DETERMINISTIC_ERRORS as exc:
        message = exc.message if isinstance(exc, AppError) else str(exc)
        _fail_upload(upload_id, message)
        logger.warning(
            "resume_extraction_failed_permanently",
            upload_id=str(upload_id),
            error_type=type(exc).__name__,
            error=message,
        )
        raise NonRetryableJobError(message) from exc

    except Exception as exc:
        # Transient: leave the upload PROCESSING so the UI keeps showing work
        # in flight while the backoff ladder runs.
        logger.warning(
            "resume_extraction_retrying",
            upload_id=str(upload_id),
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise

    with SessionLocal() as session:
        draft = ResumeExtractionDraft(
            resume_upload_id=upload_id,
            candidate_profile_id=candidate_profile_id,
            payload=extraction.model_dump(mode="json"),
            provider=settings.default_llm_provider,
            model=settings.llm_model,
        )
        session.add(draft)

        upload = session.get(ResumeUpload, upload_id)
        if upload is not None:
            upload.status = ResumeUploadStatus.EXTRACTED
            upload.error = None
        session.commit()
        draft_id = str(draft.id)

    logger.info("resume_extraction_succeeded", upload_id=str(upload_id), draft_id=draft_id)
    return {"draft_id": draft_id, "resume_upload_id": str(upload_id)}
