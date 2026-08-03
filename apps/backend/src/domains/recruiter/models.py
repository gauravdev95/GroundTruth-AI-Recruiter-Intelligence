"""SQLAlchemy models for recruiter job postings.

`JobPosting` carries both the recruiter-authored fields (title, description,
job_type, experience_level, location, deadline) and the LLM-extracted ones
(`extracted_requirements`, written by `jobs/tasks/job_extraction.py`,
confirmed into `JobRequirement` rows by `recruiter/service.py::confirm_job`).
`embedding_text` is the confirmed, human-approved blob the embedding service
(`domains/matching/embeddings.py`) actually embeds — never the raw
`description`, and never `extracted_requirements` before a human confirmed it.

`JobRequirement` reuses the existing `skills`/`proficiency_level` taxonomy
(`domains/skills/models.py`) rather than storing skill names as free text —
the same table `verify_repository_task` already writes into, so a
candidate's `candidate_skills` row and a job's `job_requirements` row can be
joined directly with no name-matching heuristic in between.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base
from src.domains.skills.models import ProficiencyLevel
from src.shared.db_mixins import TimestampMixin, UUIDPrimaryKeyMixin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, enum.Enum):
    """See `domains/recruiter/service.py` module docstring for the full
    transition table. `EXTRACTING` and `AWAITING_CONFIRMATION` both mean
    "not visible to students yet" — only `PUBLISHED` is matched/listed."""

    DRAFT = "draft"
    EXTRACTING = "extracting"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    PUBLISHED = "published"
    CLOSED = "closed"


class JobType(str, enum.Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    INTERNSHIP = "internship"
    CONTRACT = "contract"


class ExperienceLevel(str, enum.Enum):
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"


class JobPosting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_postings"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    job_type: Mapped[JobType] = mapped_column(SAEnum(JobType, name="job_type", native_enum=True), nullable=False)
    experience_level: Mapped[ExperienceLevel] = mapped_column(
        SAEnum(ExperienceLevel, name="experience_level", native_enum=True), nullable=False
    )
    location: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="job_status", native_enum=True),
        default=JobStatus.DRAFT,
        nullable=False,
        index=True,
    )
    # Set by `jobs/tasks/job_extraction.py` on success; read by the
    # confirmation screen, discarded (left in place, harmless) after confirm.
    extracted_requirements: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Set instead of a status stuck at EXTRACTING forever on a deterministic
    # LLM failure — the job reverts to DRAFT so the recruiter can resubmit.
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The human-confirmed text actually handed to the embedding service —
    # built once at confirm time from title + confirmed requirements, never
    # the raw description and never a pre-confirmation LLM draft.
    embedding_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_reembedding: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    company: Mapped["Company"] = relationship()  # noqa: F821
    requirements: Mapped[list["JobRequirement"]] = relationship(
        back_populates="job_posting", cascade="all, delete-orphan"
    )


class JobRequirement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One required or desirable skill for a job, written only at confirm
    time (`recruiter/service.py::confirm_job`) — never speculatively during
    extraction, matching the same "draft vs. live" separation
    `resume/confirm.py` uses for candidate profiles."""

    __tablename__ = "job_requirements"
    __table_args__ = (UniqueConstraint("job_posting_id", "skill_id", name="uq_job_requirement_skill"),)

    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    min_proficiency: Mapped[ProficiencyLevel] = mapped_column(
        SAEnum(ProficiencyLevel, name="proficiency_level", native_enum=True),
        nullable=False,
    )
    # Recruiter-adjustable importance in ranking (README's "recruiter-reviewable
    # weighting" goal, DATA_MODEL §5) — read by
    # `domains/matching/scoring.py::compute_evidence_score`.
    weight: Mapped[float] = mapped_column(Numeric(5, 4), default=1, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    job_posting: Mapped["JobPosting"] = relationship(back_populates="requirements")
    skill: Mapped["Skill"] = relationship()  # noqa: F821
