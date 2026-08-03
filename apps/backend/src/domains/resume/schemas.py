"""Request/response schemas for the resume import flow.

The confirm request reuses the **section request schemas verbatim** rather than
defining parallel ones. That is what makes "reusing the existing section PUT
logic" true at the validation layer too: a confirmed payload is subject to
exactly the rules a hand-typed one is, including `extra="forbid"` — so a draft
cannot smuggle `profile_strength` into the profile any more than a direct PUT
can.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domains.resume.models import ResumeDraftStatus, ResumeUploadStatus
from src.domains.student.schemas import (
    BasicInfoRequest,
    CertificatesRequest,
    ExperiencesRequest,
    ProfileCompletenessResponse,
    ProjectsRequest,
    TechnicalRequest,
)
from src.platform.models import AsyncJobStatus


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class JobStatusResponse(_ResponseModel):
    """What the UI polls while a background job runs.

    `attempts` and `is_dead_lettered` are exposed so the UI can distinguish
    "still retrying, hold on" from "this is over" — without them a failed job
    and a mid-backoff job look identical.
    """

    id: uuid.UUID
    job_type: str
    status: AsyncJobStatus
    attempts: int
    error: str | None
    result: dict[str, Any] | None
    is_dead_lettered: bool
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class ResumeUploadResponse(_ResponseModel):
    id: uuid.UUID
    original_filename: str
    content_type: str
    size_bytes: int
    status: ResumeUploadStatus
    async_job_id: uuid.UUID | None
    error: str | None
    created_at: datetime


class ResumeUploadAcceptedResponse(BaseModel):
    """202 body: the work is queued, not done.

    No user request blocks on parsing or an LLM call, so the response carries
    the job id to poll rather than a result.
    """

    upload: ResumeUploadResponse
    async_job_id: uuid.UUID


class DraftSuggestionsResponse(BaseModel):
    """Server-mapped, section-shaped suggestions for the review UI."""

    basic: dict[str, Any]
    technical: dict[str, Any]
    projects: list[dict[str, Any]]
    certificates: list[dict[str, Any]]
    experience: list[dict[str, Any]]
    unmapped: list[str]


class ResumeDraftResponse(_ResponseModel):
    id: uuid.UUID
    resume_upload_id: uuid.UUID
    status: ResumeDraftStatus
    provider: str
    model: str
    payload: dict[str, Any]
    confirmed_at: datetime | None
    created_at: datetime


class ResumeDraftDetailResponse(BaseModel):
    draft: ResumeDraftResponse
    suggestions: DraftSuggestionsResponse


class ConfirmDraftRequest(_StrictModel):
    """The sections the student accepted, each in its own section's request shape.

    Every field is optional: a student may confirm only the experience they
    trusted and leave the rest. Omitting a section leaves it untouched —
    confirming is additive review, not a profile reset.
    """

    basic: BasicInfoRequest | None = None
    technical: TechnicalRequest | None = None
    projects: ProjectsRequest | None = None
    certificates: CertificatesRequest | None = None
    experience: ExperiencesRequest | None = None

    @model_validator(mode="after")
    def require_at_least_one_section(self) -> "ConfirmDraftRequest":
        if not any(
            value is not None
            for value in (self.basic, self.technical, self.projects, self.certificates, self.experience)
        ):
            raise ValueError("Confirm at least one section, or discard the draft instead")
        return self


class ConfirmDraftResponse(BaseModel):
    draft: ResumeDraftResponse
    completeness: ProfileCompletenessResponse


class ResumeUploadListResponse(BaseModel):
    uploads: list[ResumeUploadResponse] = Field(default_factory=list)
