"""Pydantic request/response schemas for the AI interview API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.domains.interview.models import InterviewStatus


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class InterviewSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    status: InterviewStatus
    question_count: int
    total_score: float | None
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class InterviewQuestionResponse(BaseModel):
    id: uuid.UUID
    sequence: int
    prompt: str
    time_limit_seconds: int
    presented_at: datetime | None
    is_answered: bool


class InterviewStateResponse(BaseModel):
    """Everything the UI needs to render "resume where you left off":
    the interview's own status plus the one question still open, if any."""

    interview: InterviewSummaryResponse
    current_question: InterviewQuestionResponse | None
    answered_count: int


class SubmitAnswerRequest(_StrictModel):
    transcript: str = Field(min_length=0, max_length=8000)
    time_taken_seconds: int = Field(ge=0, le=3600)


class DimensionScoreResponse(BaseModel):
    dimension: str
    weight: float
    score: float
    rationale: str | None


class AnsweredQuestionReport(BaseModel):
    sequence: int
    prompt: str
    grounded_in: dict | None
    transcript: str
    time_taken_seconds: int | None
    exceeded_time_limit: bool
    scores: list[DimensionScoreResponse]
    weighted_score: float


class EvidenceReportResponse(BaseModel):
    interview_id: uuid.UUID
    project_id: uuid.UUID
    total_score: float
    rubric_weights: dict[str, float]
    questions: list[AnsweredQuestionReport]
    completed_at: datetime
