"""Pydantic schemas for the marketplace loop."""

from __future__ import annotations

import uuid
from datetime import datetime

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


class TransitionRequest(_StrictModel):
    to_status: ApplicationStatus


class PipelineCandidatePreview(BaseModel):
    candidate_profile_id: str
    headline: str | None
    match_score: float


class PipelineApplicationPreview(BaseModel):
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
