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
from src.domains.ai.llm import get_resume_extractor, require_llm_configured
from src.domains.resume.models import (
    ResumeExtractionDraft,
    ResumeUpload,
    ResumeUploadStatus,
)
from src.domains.resume.extraction import (
    merge_model_result,
    needs_escalation,
    parse_resume,
    to_extraction,
)
from src.domains.resume.extraction.normalize import clean_text, to_lines
from src.domains.resume.extraction.sections import SectionKind, segment
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

#: Recorded as `provider`/`model` on drafts the parser resolved without any
#: model call. Not left blank: the columns answer "what produced this row",
#: and a deterministic pass is a real answer with a real version. The version
#: is bumped whenever `extraction/` changes in a way that could move a field,
#: so an accuracy regression stays traceable to a specific parser revision —
#: exactly what `provider`/`model` already do for hosted models.
DETERMINISTIC_PROVIDER = "groundtruth"
DETERMINISTIC_MODEL = "deterministic-v1"

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

        # ---- Stage 1: the deterministic pass -------------------------------
        # Runs on every upload, costs nothing, and cannot fail — a document it
        # cannot read yields an empty draft rather than an exception, which is
        # what makes "found nothing" a recoverable state rather than a job
        # failure. See `extraction/pipeline.py`.
        draft = parse_resume(text)
        sections_found = {
            SectionKind(kind)
            for kind in {
                section.kind.value for section in segment(to_lines(clean_text(text)))
            }
        }
        escalate, reason = needs_escalation(draft, sections_found)

        if not escalate:
            # The common path. No provider call, no key required, no network.
            extraction = to_extraction(draft)
            resolved_provider = DETERMINISTIC_PROVIDER
            resolved_model = DETERMINISTIC_MODEL
            method = "deterministic"
            escalation_reason = None
        else:
            # ---- Stage 2: the LLM fallback, on hard documents only ---------
            # Configuration is checked before the call, not after it fails, so
            # a deployment with no key raises `LLMNotConfigured` on the
            # non-retryable branch below rather than burning the retry ladder.
            # Both values come from the same cached settings the extractor
            # itself reads, so the provenance cannot name a model that did not
            # run.
            resolved_provider = require_llm_configured()
            resolved_model = settings.llm_model
            model_output = get_resume_extractor().extract_resume(text)
            # One-directional merge: the model may fill gaps, never overwrite
            # a value read off the document. See `merge_model_result`.
            extraction, draft = merge_model_result(draft, model_output)
            method = "hybrid"
            escalation_reason = reason

        logger.info(
            "resume_extraction_method",
            upload_id=str(upload_id),
            method=method,
            reason=reason,
            confidence=draft.confidence,
            entries=draft.entry_count,
        )

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
        row = ResumeExtractionDraft(
            resume_upload_id=upload_id,
            candidate_profile_id=candidate_profile_id,
            payload=extraction.model_dump(mode="json"),
            # Per-field provenance for the review screen's confidence badges.
            confidence_payload=draft.wire(),
            # What actually produced this draft — the deterministic parser on
            # the common path, Gemini when the document escalated. Reading a row
            # is the only way to tell the two apart after the fact, which is why
            # both branches above set it rather than leaving it null.
            provider=resolved_provider,
            model=resolved_model,
            extraction_method=method,
            escalation_reason=escalation_reason,
        )
        session.add(row)

        upload = session.get(ResumeUpload, upload_id)
        if upload is not None:
            upload.status = ResumeUploadStatus.EXTRACTED
            upload.error = None
        session.commit()
        draft_id = str(row.id)

    logger.info(
        "resume_extraction_succeeded",
        upload_id=str(upload_id),
        draft_id=draft_id,
        method=method,
    )
    return {"draft_id": draft_id, "resume_upload_id": str(upload_id), "method": method}
