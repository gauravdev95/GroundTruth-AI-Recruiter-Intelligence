"""Resume upload and extraction-draft tables.

`ResumeExtractionDraft` is the whole point of this design: LLM output lands
here and **never** in a live profile table. The student reviews it
field-by-field and confirms; only then does
`domains/resume/confirm.py` map the accepted values into the existing section
service functions. Until that happens, a hallucinated degree or invented
employer is inert data in a draft row.

The draft's `payload` is JSONB rather than a set of typed columns because it
mirrors `domains/ai/extraction_schema.ResumeExtraction`, which is a
document-shaped claim set, not a profile. Giving it columns would imply a
schema commitment the extraction doesn't have, and would need a migration
every time the prompt learns to read one more field.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base
from src.shared.db_mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ResumeUploadStatus(str, enum.Enum):
    """Lifecycle of one uploaded file.

    Mirrors the async job but is not redundant with it: the job row is
    infrastructure (retries, queue state) while this is the domain state the
    student sees, and it outlives the job's retention.
    """

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    FAILED = "failed"


class ResumeDraftStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    CONFIRMED = "confirmed"
    DISCARDED = "discarded"


class ResumeUpload(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A resume file in object storage, plus its extraction status."""

    __tablename__ = "resume_uploads"

    candidate_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Storage key, not a URL: the bucket is private and links are presigned on
    # demand, so a persisted URL would be expired or leaked.
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    status: Mapped[ResumeUploadStatus] = mapped_column(
        SAEnum(ResumeUploadStatus, name="resume_upload_status", native_enum=True),
        default=ResumeUploadStatus.UPLOADED,
        nullable=False,
        index=True,
    )
    # The job the UI polls. SET NULL rather than CASCADE: job rows are
    # operational and may be pruned, but losing one must not delete the upload.
    async_job_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("async_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    candidate_profile: Mapped["CandidateProfile"] = relationship()  # noqa: F821
    drafts: Mapped[list["ResumeExtractionDraft"]] = relationship(
        back_populates="resume_upload", cascade="all, delete-orphan"
    )


class ResumeExtractionDraft(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A validated reading of one resume, awaiting student review.

    Never a live profile value — `confirm.py` is the only path from here into
    a profile section, and it runs field by field on the student's explicit
    selection.

    Produced by `domains/resume/extraction/`, which is deterministic-first:
    most drafts are built entirely by the parser, and the LLM runs only when
    the document defeats it. `extraction_method` below records which
    happened for this row.
    """

    __tablename__ = "resume_extraction_drafts"

    resume_upload_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("resume_uploads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Shape of `ai.extraction_schema.ResumeExtraction`, already validated
    # against it before the row was written.
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Which provider and model produced this, recorded per draft so a later
    # accuracy regression can be traced to a specific model version. On a
    # purely deterministic draft these name the parser itself
    # ("groundtruth"/"deterministic-v1") rather than being left blank — the
    # column answers "what produced this row", and "nothing" is never true.
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Per-field provenance and confidence, shaped by
    # `extraction/pipeline.py::ResumeDraft.wire()`. Parallel to `payload` so
    # the review screen indexes both with the same paths.
    #
    # Kept out of `payload` deliberately: `payload` is the
    # `ResumeExtraction` contract that `confirm.py` and both LLM providers
    # already share, and widening it with metadata only one screen consumes
    # would force every consumer to understand a shape it has no use for.
    #
    # NULL on drafts written before the deterministic pipeline shipped. That
    # is distinct from `{}`, which would mean "the pipeline ran and scored
    # nothing" — the review screen renders the two differently.
    confidence_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # "deterministic" | "hybrid" | "model". NULL on legacy rows, whose
    # method genuinely is not known.
    extraction_method: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Why the LLM fallback ran, from `pipeline.py::needs_escalation`. NULL
    # whenever it did not. Indexed (partially, on non-NULL) because "which
    # documents defeat the parser, and why" is the question that drives
    # threshold tuning, and it is only ever asked over these rows.
    escalation_reason: Mapped[str | None] = mapped_column(String(60), nullable=True)

    status: Mapped[ResumeDraftStatus] = mapped_column(
        SAEnum(ResumeDraftStatus, name="resume_draft_status", native_enum=True),
        default=ResumeDraftStatus.PENDING_REVIEW,
        nullable=False,
        index=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # The exact selection the student confirmed — kept as the audit trail for
    # "the student accepted this, the model only proposed it".
    confirmed_selection: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    resume_upload: Mapped["ResumeUpload"] = relationship(back_populates="drafts")
