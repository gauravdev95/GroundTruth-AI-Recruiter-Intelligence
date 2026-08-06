"""Pydantic schemas for the marketplace loop."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from src.domains.pipeline.models import ApplicationStatus


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ApplyRequest(_StrictModel):
    cover_note: str | None = Field(default=None, max_length=4000)


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_posting_id: uuid.UUID
    candidate_profile_id: uuid.UUID
    status: ApplicationStatus
    cover_note: str | None
    applied_at: datetime
    status_updated_at: datetime
    # Frozen at Smart Apply. Nullable for applications backfilled by migration
    # `b2d5e8f14c73` whose match row had already been pruned.
    score_at_apply: float | None = None


class ScoreDriftResponse(BaseModel):
    """`domains/pipeline/drift.py::ScoreDrift`, verbatim. `points` and the
    `direction`/`is_meaningful` pair are all sent: direction is the sign,
    `is_meaningful` is the `MEANINGFUL_DRIFT_POINTS` magnitude test, and the
    client decides emphasis from the second without losing the first."""

    score_at_apply: float | None
    live_score: float | None
    points: float | None
    direction: str
    is_meaningful: bool


class ApplicationDetailResponse(BaseModel):
    application: ApplicationResponse
    evidence_snapshot: dict
    job_title: str
    company_name: str


class ApplicationListItemResponse(BaseModel):
    application: ApplicationResponse
    job_title: str
    company_name: str


class RecruiterApplicationDetailResponse(BaseModel):
    application: ApplicationResponse
    job_title: str
    company_name: str
    candidate_profile_id: uuid.UUID
    candidate_headline: str | None
    drift: ScoreDriftResponse
    # The rollback affordance, server-derived for the same reason the board's
    # is: `REJECTED`'s target comes from `audit_log`, not from the client.
    can_roll_back: bool
    rollback_target: ApplicationStatus | None


#: Structured close reasons. A closed set rather than free text so the same
#: answer means the same thing across every recruiter and every job — which
#: is what makes it usable as a matching signal at all. `OTHER` exists so the
#: set never forces a wrong answer; the free-text `note` is where the real
#: reason goes in that case.
class CloseReason(str, Enum):
    SKILLS_GAP = "skills_gap"
    EXPERIENCE_MISMATCH = "experience_mismatch"
    ROLE_FILLED = "role_filled"
    OTHER = "other"


class TransitionRequest(_StrictModel):
    to_status: ApplicationStatus
    #: Both optional, always. The rejection modal's Skip button sends the
    #: transition with neither, and that path must stay exactly as fast as it
    #: was before feedback existed — a required reason is a reason recruiters
    #: learn to click past, which produces worse data than no reason at all.
    #:
    #: Only meaningful on a transition to `REJECTED`; the router records them
    #: on the audit entry and ignores them otherwise rather than 422-ing, so
    #: a client that always sends the field is not a client that breaks.
    close_reason: CloseReason | None = None
    close_note: str | None = Field(default=None, max_length=200)


class _CandidateCardFields(BaseModel):
    """The three fields every board card renders below the score, shared by
    both column shapes so the `matched` and applied columns cannot drift into
    describing the same candidate differently.

    `reasoning` is composed from stored evidence by
    `domains/matching/tiers.py::build_reasoning` — never LLM-narrated.
    """

    matched_skills: list[str] = Field(default_factory=list)
    reasoning: str = ""
    #: `candidate_profiles.is_discoverable` — verified evidence *and* a
    #: completed code-grounded interview. See `service.py::_candidate_preview`.
    is_verified: bool = False


class PipelineCandidatePreview(_CandidateCardFields):
    candidate_profile_id: str
    headline: str | None
    match_score: float


class PipelineApplicationPreview(_CandidateCardFields):
    application_id: str
    candidate_profile_id: str
    headline: str | None
    status: str
    applied_at: str
    status_updated_at: str
    # The two scores side by side, plus the drift between them, flattened
    # onto the card rather than nested: the board renders one row per
    # application and a nested object would buy nothing but indirection here.
    # `match_score` is the *live* score and is null when the pair's
    # `match_results` row no longer exists — see `drift.py::ScoreDrift`.
    score_at_apply: float | None
    match_score: float | None
    drift_points: float | None
    drift_direction: str
    drift_is_meaningful: bool
    can_roll_back: bool


class PipelineResponse(BaseModel):
    matched: list[PipelineCandidatePreview]
    applied: list[PipelineApplicationPreview]
    shortlisted: list[PipelineApplicationPreview]
    interview_scheduled: list[PipelineApplicationPreview]
    hired: list[PipelineApplicationPreview]
    rejected: list[PipelineApplicationPreview]


class EvidenceRecordResponse(BaseModel):
    record: dict


class SendMessageRequest(_StrictModel):
    body: str = Field(min_length=1, max_length=4000)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sender_user_id: uuid.UUID | None
    body: str
    created_at: datetime


class ConversationResponse(BaseModel):
    application_id: uuid.UUID
    messages: list[MessageResponse]


class AddNoteRequest(_StrictModel):
    body: str = Field(min_length=1, max_length=4000)


class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    author_user_id: uuid.UUID | None
    body: str
    created_at: datetime


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    payload: dict
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    unread_count: int
