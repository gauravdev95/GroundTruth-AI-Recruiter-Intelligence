"""SQLAlchemy models for the marketplace loop: applications, the recruiter
Kanban pipeline, in-platform messaging, notifications, and private
recruiter notes.

Deliberately does **not** add a domain-specific `application_events` table
even though `docs/DATA_MODEL.md` §5 designed one alongside `applications` —
`audit_log` (`core/audit.py`, activated alongside this module) already
writes one row per status transition with before/after state, and a second,
narrower audit trail recording the same fact would be duplicated bookkeeping
with no reader. If a genuine need for `application_events`-shaped queries
(e.g. "history of this one application" rendered as a timeline) shows up
later, it can read `audit_log` filtered by `entity_type='application'`
instead of a new table.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base
from src.shared.db_mixins import TimestampMixin, UUIDPrimaryKeyMixin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApplicationStatus(str, enum.Enum):
    APPLIED = "applied"
    SHORTLISTED = "shortlisted"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    HIRED = "hired"
    REJECTED = "rejected"


# Server-validated stage transitions — no arbitrary jumps (task constraint).
# `HIRED`/`REJECTED` are terminal: nothing transitions out of them. `REJECTED`
# is reachable from every non-terminal state (a recruiter can reject at any
# stage); the *forward* path is strictly linear.
ALLOWED_TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    ApplicationStatus.APPLIED: frozenset({ApplicationStatus.SHORTLISTED, ApplicationStatus.REJECTED}),
    ApplicationStatus.SHORTLISTED: frozenset(
        {ApplicationStatus.INTERVIEW_SCHEDULED, ApplicationStatus.REJECTED}
    ),
    ApplicationStatus.INTERVIEW_SCHEDULED: frozenset(
        {ApplicationStatus.HIRED, ApplicationStatus.REJECTED}
    ),
    ApplicationStatus.HIRED: frozenset(),
    ApplicationStatus.REJECTED: frozenset(),
}


#: Backwards moves, exposed as their own action rather than as extra entries
#: in `ALLOWED_TRANSITIONS`.
#:
#: Rollback and forward transition are different operations with different
#: meanings, and merging them would have made `ALLOWED_TRANSITIONS` cyclic —
#: at which point "no arbitrary jumps" stops being checkable by reading the
#: map, and the audit trail loses the distinction between *advancing* a
#: candidate and *undoing* having advanced them. `pipeline/service.py`
#: therefore writes `application.rolled_back`, never
#: `application.status_changed`, which is also what keeps
#: `analytics.py::recruiter_funnel`'s time-to-first-response honest: an undo
#: is not a response to a candidate.
#:
#: The map is the reverse of the linear forward path, one step at a time:
#:
#: * `SHORTLISTED -> APPLIED` and `INTERVIEW_SCHEDULED -> SHORTLISTED` —
#:   a mis-click, or a decision reconsidered before it was acted on.
#: * `REJECTED` is absent here **only because its target is not static**: it
#:   is reachable from three different stages, so the stage to restore is
#:   read back from the `audit_log` row that recorded the rejection rather
#:   than guessed. Un-rejecting is legal; see
#:   `service.py::resolve_rollback_target`.
#: * `APPLIED` rolls back to nothing. It is the entry state — there is no
#:   earlier stage, and withdrawing an application is the candidate's action,
#:   not the recruiter's.
#: * `HIRED` rolls back to nothing, and this is a deliberate policy choice
#:   rather than an oversight. Every other status is an internal opinion
#:   about a candidate; a hire is the one with an external counterpart (an
#:   offer that was made and accepted). Letting it un-happen would make
#:   "hired" non-monotonic, which `recruiter_funnel`'s cumulative conversion
#:   arithmetic assumes it is not. A hire recorded in error is a
#:   data-correction problem, not a board action.
ALLOWED_ROLLBACKS: dict[ApplicationStatus, ApplicationStatus] = {
    ApplicationStatus.SHORTLISTED: ApplicationStatus.APPLIED,
    ApplicationStatus.INTERVIEW_SCHEDULED: ApplicationStatus.SHORTLISTED,
}

#: Where a `REJECTED` application may be restored to when `audit_log` has no
#: usable record of where it was rejected from — applications created before
#: stage transitions were audited at all. `APPLIED` rather than a refusal:
#: every application passed through `APPLIED`, so restoring it there is the
#: one target that is certainly true, even if it under-restores.
ROLLBACK_FALLBACK_FROM_REJECTED = ApplicationStatus.APPLIED


class Application(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Smart Apply's output. `evidence_snapshot` is built once, at apply
    time, from the candidate's *current* verified state
    (`pipeline/service.py::build_evidence_snapshot`) — the whole point of
    Smart Apply is that the student re-enters nothing, so this is what
    "attaches all scores and the interview report" means concretely: a
    frozen copy taken at the moment of applying, not a live join recomputed
    on every read (a candidate's profile can keep changing after they
    applied; what the recruiter sees for *this* application is what existed
    when it was submitted)."""

    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("job_posting_id", "candidate_profile_id", name="uq_application_pair"),)

    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        SAEnum(ApplicationStatus, name="application_status", native_enum=True),
        default=ApplicationStatus.APPLIED,
        nullable=False,
        index=True,
    )
    cover_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # The match this application came from, and the score frozen off it at
    # apply time. `match_id` is nullable and `ondelete="SET NULL"`: a match row
    # can legitimately disappear (its job closed) long after someone applied
    # through it, and losing the link must never cascade into losing the
    # application. `score_at_apply` therefore survives independently — it is
    # the number the recruiter's shortlisting decision was actually made
    # against, and a later re-verification that moves the live score must not
    # rewrite the record of that decision.
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("match_results.id", ondelete="SET NULL"), nullable=True, index=True
    )
    score_at_apply: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    # A citable identity for the frozen `evidence_snapshot` above, so an audit
    # entry can name the exact snapshot a decision was made against. Not a
    # foreign key: the snapshot is stored inline (it is read only ever
    # alongside its own application, so a separate table would be a join with
    # no second reader) and this identifies that document, not another row.
    evidence_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    status_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    conversation: Mapped["Conversation | None"] = relationship(
        back_populates="application", uselist=False, cascade="all, delete-orphan"
    )
    notes: Mapped[list["RecruiterNote"]] = relationship(back_populates="application", cascade="all, delete-orphan")


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One per application — messaging is restricted to pairs with an
    existing pipeline relationship (task constraint), which this FK *is*:
    there is no way to create a conversation without an application, and no
    way to reach one without being either the candidate or the job's owner
    (`pipeline/dependencies.py`)."""

    __tablename__ = "conversations"

    application_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    application: Mapped["Application"] = relationship(back_populates="conversation")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(UUIDPrimaryKeyMixin, Base):
    """Immutable once sent — no `updated_at`, matching every other
    append-only table in this codebase (`InterviewAnswer`, `AuditLog`)."""

    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class NotificationType(str, enum.Enum):
    STAGE_CHANGE = "stage_change"
    NEW_MESSAGE = "new_message"
    # Written by the matching worker for each *newly* matched candidate — never
    # for a rescore of a pair the student has already been told about.
    NEW_MATCH = "new_match"


class Notification(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, name="notification_type", native_enum=True), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class RecruiterNote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Private to the hiring company. Never exposed on any candidate-facing
    route (`pipeline/router.py` mounts no student-reachable path for this
    model at all) *and* every recruiter-side query additionally filters by
    `company_id` (`pipeline/service.py::list_notes`) — belt and suspenders,
    but the query-layer filter is the one that actually matters per the
    task's own wording ("enforce exclusion at the query layer, never by UI
    filtering")."""

    __tablename__ = "recruiter_notes"

    application_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    application: Mapped["Application"] = relationship(back_populates="notes")
