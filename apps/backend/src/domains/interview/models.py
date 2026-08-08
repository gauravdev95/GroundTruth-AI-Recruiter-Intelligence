"""SQLAlchemy models for the live code-grounded AI interview.

Deliberately smaller than `docs/DATA_MODEL.md` §4's design: that design scopes
an interview to an `applications` row, which does not exist yet (no job
postings, no application pipeline). This interview is scoped to a `Project`
instead — specifically a verified GitHub repository — because the whole point
is that every question traces back to that repository's stored analysis, not
to a job requisition.

**This replaces the typed one-question-at-a-time interview.** What changed, and
why the shape had to change with it:

* An interview is now a *conversation*, so the record is a linear list of
  `InterviewTurn` rows rather than a question with one answer hanging off it.
  A follow-up is just another interviewer turn pointing at the same question
  index, which is what makes "two follow-ups then move on" expressible at all.
* Verification is continuous, so `InterviewVerificationFlag` rows accumulate
  during the session rather than being derived at the end.
* Scoring is per *interview*, not per answer (`InterviewDimensionScore`), for
  the reason spelled out in `domains/ai/llm.py::InterviewScorer`: in a
  conversation a candidate can correct themselves three turns later, so
  scoring each answer in isolation would misread exactly the exchanges this
  design exists to allow.

One interview per `(candidate_profile_id, project_id)` is enforced by
`domains/interview/service.py`, not a DB unique constraint: a `FAILED` attempt
must not block a retry, so the constraint is "no *non-terminal-failure* attempt
already exists" — a rule with an exception, which belongs in code, not in the
schema. Every row that is written, though, is written once and never edited: a
turn cannot be retracted, a flag cannot be softened, a score cannot be revised.
The mutable session bookkeeping (`stage`, `current_question_index`,
`follow_up_count`) lives on the `interviews` row precisely so the append-only
tables stay append-only.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.config.config import get_interview_settings
from src.db.database import Base
from src.shared.db_mixins import TimestampMixin, UUIDPrimaryKeyMixin

#: The v1 rubric, kept verbatim so interviews scored under it remain readable.
#: Never used to score a new interview. An evidence report is written once and
#: never edited, so a v1 interview keeps its v1 dimensions forever rather than
#: being retroactively re-judged against a rubric the candidate never sat.
RUBRIC_WEIGHTS_V1: dict[str, float] = {
    "technical_accuracy": 0.40,
    "depth_of_reasoning": 0.25,
    "codebase_specificity": 0.20,
    "repository_consistency": 0.15,
}

#: The v2 rubric — the typed interview's five dimensions. Frozen here for the
#: same reason v1 is: v2 interviews were really sat under these weights, and
#: the configured weights now describe v3.
RUBRIC_WEIGHTS_V2: dict[str, float] = {
    "technical_accuracy": 0.30,
    "code_understanding": 0.25,
    "problem_solving": 0.20,
    "repository_knowledge": 0.15,
    "communication": 0.10,
}

#: How a v1 dimension maps onto its v2 successor, for rendering a mixed history
#: under one vocabulary. Presentation only — no stored row is rewritten.
RUBRIC_V1_TO_V2: dict[str, str] = {
    "technical_accuracy": "technical_accuracy",
    "depth_of_reasoning": "problem_solving",
    "codebase_specificity": "repository_knowledge",
    "repository_consistency": "code_understanding",
}

#: v3 drops `repository_knowledge` as a separate axis and folds it into
#: `code_understanding`, which is where the live Scorer judges it — "do they
#: know their own codebase" is now assessed continuously by the Verifier rather
#: than scored once per answer. Presentation only, as above.
RUBRIC_V2_TO_V3: dict[str, str] = {
    "technical_accuracy": "technical_accuracy",
    "code_understanding": "code_understanding",
    "problem_solving": "problem_solving",
    "repository_knowledge": "code_understanding",
    "communication": "communication",
}

RUBRIC_VERSION_V1 = 1
RUBRIC_VERSION_V2 = 2


def get_rubric_weights(version: int | None = None) -> dict[str, float]:
    """Weights for `version`, defaulting to the configured current rubric.

    `interview_dimension_scores.dimension` values are validated against the
    returned key set — a score row naming a dimension outside its own
    interview's rubric is a bug, not a new feature. Reading through a function
    rather than a module constant is what lets the weights be configurable
    (`InterviewSettings.rubric_weights`) without freezing them at import.
    """
    if version == RUBRIC_VERSION_V1:
        return dict(RUBRIC_WEIGHTS_V1)
    if version == RUBRIC_VERSION_V2:
        return dict(RUBRIC_WEIGHTS_V2)
    return get_interview_settings().rubric_weights


def get_current_rubric_version() -> int:
    return get_interview_settings().interview_rubric_version


MIN_QUESTIONS = 5
MAX_QUESTIONS = 7


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InterviewStatus(str, enum.Enum):
    """`PENDING` = question generation running, before the candidate can
    connect. `IN_PROGRESS` = a live session may be held. `EVALUATING` = the
    conversation is over and the Scorer is running. `FAILED` covers a failed
    generation and a failed scoring alike; `error` on the row says which."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"


class InterviewStage(str, enum.Enum):
    """Where in the conversation the session is.

    Distinct from `InterviewStatus`: status is the lifecycle of the *record*
    (does a result exist yet), stage is the shape of the *conversation* (what
    kind of turn comes next). An interview is `IN_PROGRESS` for the whole of
    warmup, main and wrapup.
    """

    WARMUP = "warmup"
    MAIN = "main"
    WRAPUP = "wrapup"
    DONE = "done"


class TurnRole(str, enum.Enum):
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


class CandidateComfort(str, enum.Enum):
    """The Interviewer's running read on how the candidate is holding up, used
    to soften phrasing. Never scored, and deliberately not shown to the
    candidate or the recruiter: it is a delivery hint, not a finding, and
    "seemed nervous" is precisely the kind of thing a hiring decision must not
    turn on.
    """

    CONFIDENT = "confident"
    NEUTRAL = "neutral"
    NERVOUS = "nervous"


class InterviewGrounding(str, enum.Enum):
    """What an interview's questions are generated from.

    `REPOSITORY` is the original, strongest form: every question traces to a
    specific file in one verified repository's stored analysis.

    `PROFILE` is the candidate-level interview, grounded in the union of their
    verified evidence — repositories, coding-profile competencies, confirmed
    resume content, certificates and experience. It exists so that a candidate
    with no verifiable repository still has a route to a completed interview,
    which discoverability now requires; without it, anyone GitHub cannot
    verify would be permanently undiscoverable with no action available to
    them. It is deliberately the weaker of the two: it draws on evidence that
    is broader but less specific than a single codebase.
    """

    REPOSITORY = "repository"
    PROFILE = "profile"


class Interview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One attempt at a live AI interview — repository- or profile-grounded."""

    __tablename__ = "interviews"

    candidate_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nullable **only** for `grounding=PROFILE`, which is scoped to the
    # candidate rather than to one repository. A REPOSITORY interview without a
    # project is meaningless, so that pairing is enforced in
    # `service.py::start_interview` rather than by a CHECK constraint — the
    # rule reports as a domain error there, not an opaque DB failure.
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    grounding: Mapped[InterviewGrounding] = mapped_column(
        SAEnum(InterviewGrounding, name="interview_grounding", native_enum=True),
        default=InterviewGrounding.REPOSITORY,
        nullable=False,
        index=True,
    )
    # Which rubric this attempt was scored under. Stored per row because the
    # weights are configurable and an evidence report is never rewritten — see
    # `get_rubric_weights`.
    rubric_version: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    status: Mapped[InterviewStatus] = mapped_column(
        SAEnum(InterviewStatus, name="interview_status", native_enum=True),
        default=InterviewStatus.PENDING,
        nullable=False,
        index=True,
    )
    stage: Mapped[InterviewStage] = mapped_column(
        SAEnum(InterviewStage, name="interview_stage", native_enum=True),
        default=InterviewStage.WARMUP,
        nullable=False,
    )
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Which pre-generated question the conversation is on. Advanced by the
    # graph, never by the client — a client that could set it could skip the
    # questions it did not like.
    current_question_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Follow-ups spent on the *current* question. Reset on every advance, which
    # is why it is one counter and not a per-question tally.
    follow_up_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # The session clock, in seconds, fixed when the interview row is created.
    # Stored rather than read from config at each turn so that changing the
    # configured limit cannot shorten an interview somebody is already sitting.
    time_limit_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_comfort: Mapped[CandidateComfort] = mapped_column(
        SAEnum(CandidateComfort, name="candidate_comfort", native_enum=True),
        default=CandidateComfort.NEUTRAL,
        nullable=False,
    )
    # Weighted total across the rubric, 0-100. Set only once EVALUATING
    # finishes; `evidence_report` is the full breakdown that number summarizes.
    total_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    evidence_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    questions: Mapped[list["InterviewQuestion"]] = relationship(
        back_populates="interview", cascade="all, delete-orphan", order_by="InterviewQuestion.sequence"
    )
    turns: Mapped[list["InterviewTurn"]] = relationship(
        back_populates="interview", cascade="all, delete-orphan", order_by="InterviewTurn.sequence"
    )
    verification_flags: Mapped[list["InterviewVerificationFlag"]] = relationship(
        back_populates="interview", cascade="all, delete-orphan"
    )
    dimension_scores: Mapped[list["InterviewDimensionScore"]] = relationship(
        back_populates="interview", cascade="all, delete-orphan"
    )
    integrity_events: Mapped[list["InterviewIntegrityEvent"]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="InterviewIntegrityEvent.client_sequence",
    )

    def elapsed_seconds(self, *, now: datetime | None = None) -> float:
        """Wall-clock seconds since the conversation opened.

        Wall clock, not summed turn durations: a candidate who walks away for
        five minutes has spent five minutes of a ten-minute interview, and the
        alternative would let an idle session run indefinitely.
        """
        if self.started_at is None:
            return 0.0
        return ((now or _utcnow()) - self.started_at).total_seconds()

    def time_remaining_seconds(self, *, now: datetime | None = None) -> int:
        return max(0, int(self.time_limit_seconds - self.elapsed_seconds(now=now)))


class InterviewQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One pre-generated question, grounded in a slice of the analysis.

    Still generated up front, even though the interview is now live: the
    grounding work needs the whole stored analysis and takes seconds, which is
    fine before the candidate connects and is not fine between two turns of a
    conversation. What changed is that the Interviewer rephrases these rather
    than reading them, so `prompt` is now the *intent* of a question rather
    than its literal wording.
    """

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
    # What a strong answer would contain. Read by the Interviewer to judge
    # whether an answer is thin enough to probe, and by the Scorer as the
    # baseline it credits against.
    expected_signals: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    interview: Mapped["Interview"] = relationship(back_populates="questions")


class InterviewTurn(UUIDPrimaryKeyMixin, Base):
    """One utterance. Immutable once written — no `updated_at`, no edit path.

    Both sides of the conversation live in one table rather than in separate
    interviewer/candidate tables, because the ordering *between* them is the
    thing that has to be reconstructible: a transcript is only meaningful in
    sequence, and two tables would make "what was said next" a merge.
    """

    __tablename__ = "interview_turns"
    __table_args__ = (UniqueConstraint("interview_id", "sequence", name="uq_interview_turn_sequence"),)

    interview_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[TurnRole] = mapped_column(
        SAEnum(TurnRole, name="interview_turn_role", native_enum=True), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # The Interviewer's declared intent for this turn (ASK_QUESTION,
    # ASK_FOLLOWUP, BRIDGE_NEXT, WRAPUP). Null on candidate turns. Stored so a
    # transcript can be replayed without re-deriving intent from prose.
    action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Which pre-generated question this turn belongs to. Null during warmup and
    # wrapup, which belong to no question.
    question_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The Interviewer's private observation about the answer it just heard.
    # Never rendered to the candidate; read by the Scorer.
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    spoken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    interview: Mapped["Interview"] = relationship(back_populates="turns")


class InterviewVerificationFlag(UUIDPrimaryKeyMixin, Base):
    """One claim the Verifier checked against the repository analysis.

    Kept even when `status="supported"`: a scorecard that only records what the
    candidate got wrong cannot show a recruiter what they got right, and
    "verified claims" is the more useful half of the evidence.
    """

    __tablename__ = "interview_verification_flags"

    interview_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The candidate turn that produced the claim. Nullable so a flag survives
    # nothing — it is always set in practice, but the relationship is
    # `ondelete=SET NULL` rather than CASCADE so that a turn could never take
    # verification history with it.
    turn_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("interview_turns.id", ondelete="SET NULL"), nullable=True
    )
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    interview: Mapped["Interview"] = relationship(back_populates="verification_flags")


#: The closed set of integrity signals the interview room may report.
#:
#: Stored as a plain string column rather than a native enum, matching
#: `InterviewVerificationFlag.status`: the set is expected to grow as the room
#: learns to notice more things, and a growing native enum costs a migration per
#: addition for a column nothing joins on. The Pydantic layer
#: (`schemas.py::IntegrityEventType`) is what rejects an unknown value, so an
#: unrecognised signal is a 422 rather than a silently-stored typo.
#:
#: Every name here describes an *observation*, never a conclusion. There is no
#: `cheating_detected` and there will not be one — a browser can see that a tab
#: lost focus, and cannot see why.
INTEGRITY_EVENT_TYPES: tuple[str, ...] = (
    "tab_hidden",
    "window_blur",
    "fullscreen_exit",
    "camera_disabled",
    "camera_unavailable",
    "camera_obscured",
    "microphone_disabled",
    "microphone_unavailable",
    "no_speech_detected",
    "inactivity",
    "connection_lost",
)


class InterviewIntegrityEvent(UUIDPrimaryKeyMixin, Base):
    """One thing the interview room noticed about the session's conditions.

    **Deliberately its own table, not a column on `interview_turns`.** These are
    observations about the *environment* an interview was taken in; a turn is a
    record of what was said. Keeping them apart is what lets the scoring path
    stay exactly what it was — the Scorer reads turns and flags, and cannot see
    this table at all, so a candidate whose laptop camera died does not get a
    lower `technical_accuracy` for it.

    Append-only, like every other record of an attempt.

    `client_sequence` exists for idempotency, not ordering. The room batches
    these and flushes on a timer, on `visibilitychange`, and on unload — the
    last of which can genuinely fire twice — so the write is an upsert keyed on
    `(interview_id, client_sequence)` and a replayed batch lands as zero new
    rows rather than doubling somebody's tab-switch count.
    """

    __tablename__ = "interview_integrity_events"
    __table_args__ = (
        UniqueConstraint("interview_id", "client_sequence", name="uq_interview_integrity_sequence"),
    )

    interview_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Monotonic per-session counter assigned by the room. See the class
    #: docstring — this is a dedupe key, and gaps in it are expected and fine.
    client_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    #: Seconds into the session, **as the client measured it**. Advisory: the
    #: authoritative clock is `Interview.elapsed_seconds()`, and this column
    #: exists so a reviewer can see *when* in the conversation something
    #: happened without the server having to have been told in real time.
    elapsed_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: How long the condition lasted, where it has a duration (a tab left
    #: hidden, a stretch of silence). Null for instantaneous events.
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Room-supplied context — never free text from the candidate, and never
    #: media. See `schemas.py::IntegrityEventRequest` for what may go in here.
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    #: When the server received it, which is not when it happened. Both are
    #: kept because the gap between them is itself informative: a batch that
    #: arrives ninety seconds late is a connection that was down.
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    interview: Mapped["Interview"] = relationship(back_populates="integrity_events")


class InterviewDimensionScore(UUIDPrimaryKeyMixin, Base):
    """One rubric-dimension score for the interview as a whole.

    Hangs off the interview, not off an answer — see this module's docstring.
    Append-only, like every other record of the attempt.
    """

    __tablename__ = "interview_dimension_scores"
    __table_args__ = (
        UniqueConstraint("interview_id", "dimension", name="uq_interview_dimension_score"),
    )

    interview_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension: Mapped[str] = mapped_column(String(50), nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The Scorer's own confidence, 0-100 — the same scale as `score`, and
    # stored beside it rather than folded into it: "70, and we are sure" and
    # "70, and we are guessing" are different things to show a recruiter. See
    # `ai/interview_schema.py::DimensionScore.confidence` for why one scale is
    # load-bearing and not merely tidy.
    confidence: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    interview: Mapped["Interview"] = relationship(back_populates="dimension_scores")
