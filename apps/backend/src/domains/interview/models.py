"""SQLAlchemy models for the code-grounded AI interview.

Deliberately smaller than `docs/DATA_MODEL.md` §4's design: that design scopes
an interview to an `applications` row, which does not exist yet (no job
postings, no application pipeline). This interview is scoped to a `Project`
instead — specifically a verified GitHub repository — because the whole point
is that every question traces back to that repository's stored analysis, not
to a job requisition.

One interview per `(candidate_profile_id, project_id)` is enforced by
`domains/interview/service.py`, not a DB unique constraint: a `FAILED`
attempt (question generation or evaluation blew up) must not block a retry,
so the constraint is "no *non-terminal-failure* attempt already exists" —
a rule with an exception, which belongs in code, not in the schema. Every
row that is written, though, is written once and never edited — an answer
cannot be resubmitted, a question's prompt cannot change after generation —
which is what "store attempt history, never overwrite" means in practice
here: there is only ever one attempt per repository, and that attempt's
record is append-only.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base
from src.shared.db_mixins import TimestampMixin, UUIDPrimaryKeyMixin

# Fixed rubric weights (§6 of the task): technical accuracy 40%, depth of
# reasoning 25%, specificity to the candidate's own codebase 20%, consistency
# with the stored repository analysis 15%. Defined here (not just in the AI
# provider) because `interview_scores.dimension` values are validated against
# this set — a scoring row for a dimension outside the rubric is a bug, not a
# new feature.
RUBRIC_WEIGHTS: dict[str, float] = {
    "technical_accuracy": 0.40,
    "depth_of_reasoning": 0.25,
    "codebase_specificity": 0.20,
    "repository_consistency": 0.15,
}

DEFAULT_QUESTION_TIME_LIMIT_SECONDS = 300
MIN_QUESTIONS = 5
MAX_QUESTIONS = 7


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InterviewStatus(str, enum.Enum):
    """`PENDING` = question generation running. `FAILED` covers both a failed
    generation and a failed evaluation; `error` on the row says which."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"


class Interview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One attempt at the code-grounded interview for one verified repository."""

    __tablename__ = "interviews"

    candidate_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[InterviewStatus] = mapped_column(
        SAEnum(InterviewStatus, name="interview_status", native_enum=True),
        default=InterviewStatus.PENDING,
        nullable=False,
        index=True,
    )
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Weighted total across the fixed rubric, 0-100. Set only once EVALUATING
    # finishes; `evidence_report` is the full per-question, per-criterion
    # breakdown that number summarizes.
    total_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    evidence_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    questions: Mapped[list["InterviewQuestion"]] = relationship(
        back_populates="interview", cascade="all, delete-orphan", order_by="InterviewQuestion.sequence"
    )


class InterviewQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One generated question, grounded in a slice of the repository analysis."""

    __tablename__ = "interview_questions"
    __table_args__ = (UniqueConstraint("interview_id", "sequence", name="uq_interview_question_sequence"),)

    interview_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    # What in the stored analysis this question is grounded in (e.g. a file
    # path + detected technology + quality signal) — the trace that makes
    # "no generic question bank" auditable rather than an unverifiable claim.
    grounded_in: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    time_limit_seconds: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_QUESTION_TIME_LIMIT_SECONDS, nullable=False
    )
    # Set the first time the question is fetched for answering — the anchor
    # `time_taken_seconds` is measured from, and what makes a resume-after-
    # disconnect show the same remaining time rather than a fresh clock.
    presented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    interview: Mapped["Interview"] = relationship(back_populates="questions")
    answer: Mapped["InterviewAnswer | None"] = relationship(
        back_populates="question", uselist=False, cascade="all, delete-orphan"
    )


class InterviewAnswer(UUIDPrimaryKeyMixin, Base):
    """A submitted answer. Immutable once written — no `updated_at`, no edit path."""

    __tablename__ = "interview_answers"

    interview_question_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("interview_questions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    time_taken_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exceeded_time_limit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    question: Mapped["InterviewQuestion"] = relationship(back_populates="answer")
    scores: Mapped[list["InterviewScore"]] = relationship(back_populates="answer", cascade="all, delete-orphan")


class InterviewScore(UUIDPrimaryKeyMixin, Base):
    """One rubric-dimension score for one answer. Append-only, like the answer it scores."""

    __tablename__ = "interview_scores"

    interview_answer_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("interview_answers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension: Mapped[str] = mapped_column(String(50), nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    answer: Mapped["InterviewAnswer"] = relationship(back_populates="scores")
