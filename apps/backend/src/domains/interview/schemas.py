"""Pydantic request/response schemas for the live AI interview API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.domains.interview.models import InterviewStage, InterviewStatus


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class InterviewSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    # Null for a profile-grounded interview, which belongs to the candidate
    # rather than to any one repository.
    project_id: uuid.UUID | None
    status: InterviewStatus
    stage: InterviewStage
    question_count: int
    current_question_index: int
    time_limit_seconds: int
    total_score: float | None
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class TurnResponse(BaseModel):
    """One utterance, as the candidate's own transcript shows it.

    `internal_notes` is deliberately absent: the Interviewer's private read on
    an answer is scoring material, and echoing it back mid-interview would tell
    a candidate exactly what to correct.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequence: int
    role: str
    text: str
    question_index: int | None
    spoken_at: datetime


class InterviewStateResponse(BaseModel):
    """Everything the UI needs to render or resume a live session."""

    interview: InterviewSummaryResponse
    transcript: list[TurnResponse]
    #: Seconds left on the session clock, computed server-side. The client
    #: renders a countdown from this rather than owning one, so a paused tab or
    #: a fiddled system clock cannot buy extra time.
    time_remaining_seconds: int
    #: False while the interviewer is speaking or the interview is over — the
    #: client uses it to enable the composer.
    awaiting_candidate: bool


class CandidateMessageRequest(_StrictModel):
    text: str = Field(min_length=1, max_length=8000)


# ---------------------------------------------------------------------------
# Interview integrity
# ---------------------------------------------------------------------------

#: The room's vocabulary for session conditions, and the validation boundary for
#: `interview_integrity_events.event_type`. Kept in lockstep with
#: `models.INTEGRITY_EVENT_TYPES`, which `tests/unit/test_schemas.py` asserts.
IntegrityEventType = Literal[
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
]


class IntegrityEventRequest(_StrictModel):
    """One observation from the interview room.

    `detail` is a small string map on purpose rather than free-form JSON: it
    carries things like which device disappeared, and a candidate-influenced
    blob arriving on an endpoint that writes to the database is a shape worth
    refusing outright. Nothing here is media, and nothing here is transcript —
    see the model docstring for why those stay apart.
    """

    client_sequence: int = Field(ge=0)
    event_type: IntegrityEventType
    elapsed_seconds: int = Field(ge=0, le=86_400)
    duration_seconds: int | None = Field(default=None, ge=0, le=86_400)
    detail: dict[str, str] | None = Field(default=None, max_length=8)


class IntegrityBatchRequest(_StrictModel):
    """A flush from the room. Batched rather than one request per event because
    the noisiest signals (blur/focus on an alt-tab) arrive in pairs within a
    second of each other, and a request each would turn a candidate reaching for
    a second monitor into a burst against their own rate limit."""

    events: list[IntegrityEventRequest] = Field(min_length=1, max_length=50)


class IntegrityEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_type: str
    elapsed_seconds: int
    duration_seconds: int | None
    detail: dict | None
    recorded_at: datetime


class IntegritySummaryResponse(BaseModel):
    """What was observed, counted by kind.

    No verdict field, and no score. The counts are shown as counts — a product
    that turned "tab hidden twice" into a judgement would be asserting something
    the browser never told it, and a candidate whose notification banner stole
    focus deserves to be looked at, not marked.
    """

    interview_id: uuid.UUID
    counts: dict[str, int]
    total: int
    events: list[IntegrityEventResponse]


class DimensionScoreResponse(BaseModel):
    dimension: str
    weight: float
    score: float
    evidence: str | None
    confidence: float


class EvidenceReportResponse(BaseModel):
    """The finished interview, as shown to the candidate and the recruiter.

    Carries the whole transcript rather than a per-question summary: the
    conversation *is* the evidence now, and a report that showed scores without
    what was actually said would be exactly the unfalsifiable output this
    product exists to replace.
    """

    interview_id: uuid.UUID
    project_id: uuid.UUID | None
    total_score: float
    rubric_weights: dict[str, float]
    dimensions: list[DimensionScoreResponse]
    transcript: list[TurnResponse]
    verified_claims: list[str]
    contradicted_claims: list[str]
    unsupported_claims: list[str]
    strengths: list[str]
    concerns: list[str]
    summary: str
    completed_at: datetime
