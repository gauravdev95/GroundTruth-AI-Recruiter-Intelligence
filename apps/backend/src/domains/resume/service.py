"""Business logic for resume upload, draft retrieval, and confirmation.

The upload path deliberately does the least possible work synchronously: size
check, type check, store the bytes, write two rows, enqueue. Parsing and the
LLM call happen in the worker, so no user request ever blocks on a third-party
call.
"""

from __future__ import annotations

import uuid
from typing import BinaryIO

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.config import get_storage_settings
from src.core.exceptions import Conflict, NotFound
from src.domains.auth.models import CandidateProfile
from src.domains.resume import confirm as confirm_module
from src.domains.resume.models import (
    ResumeDraftStatus,
    ResumeExtractionDraft,
    ResumeUpload,
    ResumeUploadStatus,
)
from src.domains.resume.parsing import UnsupportedFileType, detect_content_type
from src.domains.resume.schemas import ConfirmDraftRequest
from src.domains.storage import client as storage
from src.domains.student.completeness import ProfileCompleteness
from src.jobs import dispatch
from src.platform.models import AsyncJob

logger = structlog.get_logger(__name__)

JOB_EXTRACT_RESUME = "extract_resume"


class ResumeTooLarge(UnsupportedFileType):
    """The uploaded file exceeds the configured size ceiling."""

    status_code = 413
    code = "FILE_TOO_LARGE"


def create_upload(
    db: Session,
    profile: CandidateProfile,
    *,
    fileobj: BinaryIO,
    filename: str,
    size_bytes: int,
) -> tuple[ResumeUpload, AsyncJob]:
    """Store the file and queue extraction. Returns immediately — nothing blocks.

    There is no `declared_content_type` parameter by design: the browser's
    `Content-Type` was the only thing it ever carried, and the type is now
    sniffed from the bytes. Accepting it would invite a caller to pass it back
    in as authoritative.
    """
    settings = get_storage_settings()

    if size_bytes <= 0:
        raise UnsupportedFileType("The uploaded file is empty")
    if size_bytes > settings.resume_max_bytes:
        raise ResumeTooLarge(
            f"Resumes must be at most {settings.resume_max_bytes // (1024 * 1024)} MB"
        )

    # Sniffed from the bytes, not from `filename` or `declared_content_type`:
    # both are client-supplied, and the stored `content_type` is what the
    # worker dispatches its parser on. Trusting a claim here would let a
    # renamed file pick the wrong parser.
    content_type = detect_content_type(fileobj)
    suffix = ".pdf" if content_type.endswith("pdf") else ".docx"
    object_key = storage.build_object_key(profile.id, suffix)

    # Storage first: a stored object with no row is recoverable garbage, while
    # a row pointing at an object that was never written is a broken record the
    # worker would fail on.
    storage.upload_fileobj(fileobj, key=object_key, content_type=content_type)

    upload = ResumeUpload(
        candidate_profile_id=profile.id,
        object_key=object_key,
        original_filename=filename[:255],
        content_type=content_type,
        size_bytes=size_bytes,
        status=ResumeUploadStatus.UPLOADED,
    )
    db.add(upload)
    db.flush()

    job = dispatch.create_job(
        db,
        job_type=JOB_EXTRACT_RESUME,
        payload={
            "resume_upload_id": str(upload.id),
            "candidate_profile_id": str(profile.id),
            "object_key": object_key,
            "content_type": content_type,
        },
    )
    upload.async_job_id = job.id
    db.commit()
    db.refresh(upload)

    # Published only after the rows are committed — see `jobs/dispatch.py`.
    from src.jobs.celery_app import QUEUE_EXTRACTION
    from src.jobs.tasks.resume import extract_resume_task

    dispatch.dispatch(job, extract_resume_task, queue=QUEUE_EXTRACTION)

    logger.info("resume_upload_queued", upload_id=str(upload.id), async_job_id=str(job.id))
    return upload, job


def list_uploads(db: Session, profile: CandidateProfile) -> list[ResumeUpload]:
    return list(
        db.execute(
            select(ResumeUpload)
            .where(
                ResumeUpload.candidate_profile_id == profile.id,
                ResumeUpload.deleted_at.is_(None),
            )
            .order_by(ResumeUpload.created_at.desc())
        ).scalars()
    )


def get_upload(db: Session, profile: CandidateProfile, upload_id: uuid.UUID) -> ResumeUpload:
    upload = db.execute(
        select(ResumeUpload).where(
            ResumeUpload.id == upload_id,
            ResumeUpload.candidate_profile_id == profile.id,
            ResumeUpload.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if upload is None:
        raise NotFound("Resume upload not found")
    return upload


def get_draft(db: Session, profile: CandidateProfile, draft_id: uuid.UUID) -> ResumeExtractionDraft:
    """Fetch a draft, scoped to the caller's own profile.

    The profile filter is part of the query rather than a check afterwards, so
    another student's draft is not found rather than found-then-rejected.
    """
    draft = db.execute(
        select(ResumeExtractionDraft).where(
            ResumeExtractionDraft.id == draft_id,
            ResumeExtractionDraft.candidate_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if draft is None:
        raise NotFound("Extraction draft not found")
    return draft


def latest_draft_for_upload(
    db: Session, profile: CandidateProfile, upload_id: uuid.UUID
) -> ResumeExtractionDraft | None:
    return db.execute(
        select(ResumeExtractionDraft)
        .where(
            ResumeExtractionDraft.resume_upload_id == upload_id,
            ResumeExtractionDraft.candidate_profile_id == profile.id,
        )
        .order_by(ResumeExtractionDraft.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def confirm_draft(
    db: Session,
    profile: CandidateProfile,
    draft: ResumeExtractionDraft,
    payload: ConfirmDraftRequest,
) -> ProfileCompleteness:
    """Apply the confirmed sections, then mark the draft confirmed.

    Ordering matters: the draft is only marked confirmed after every section
    write has landed. A failure partway leaves it `pending_review`, and because
    each section service reconciles by natural key, re-confirming converges
    rather than duplicating.
    """
    if draft.status is ResumeDraftStatus.CONFIRMED:
        raise Conflict("This draft has already been confirmed")
    if draft.status is ResumeDraftStatus.DISCARDED:
        raise Conflict("This draft was discarded")

    completeness = confirm_module.apply_confirmation(
        db,
        profile,
        basic=payload.basic,
        technical=payload.technical,
        projects=payload.projects,
        certificates=payload.certificates,
        experience=payload.experience,
    )

    draft.status = ResumeDraftStatus.CONFIRMED
    draft.confirmed_at = confirm_module.utcnow()
    # The audit trail for "the student accepted this; the model only proposed it".
    draft.confirmed_selection = payload.model_dump(mode="json", exclude_none=True)
    db.commit()

    logger.info("resume_draft_confirmed", draft_id=str(draft.id), profile_id=str(profile.id))
    return completeness


def discard_draft(db: Session, draft: ResumeExtractionDraft) -> ResumeExtractionDraft:
    if draft.status is ResumeDraftStatus.CONFIRMED:
        raise Conflict("This draft has already been confirmed")
    draft.status = ResumeDraftStatus.DISCARDED
    db.commit()
    db.refresh(draft)
    return draft


def delete_upload(db: Session, upload: ResumeUpload) -> None:
    """Soft-delete the record and remove the stored file.

    The row is retained (soft delete) so drafts and their audit trail stay
    coherent, but the personal data itself is removed from object storage.
    """
    upload.deleted_at = confirm_module.utcnow()
    db.commit()
    storage.delete_object(upload.object_key)
