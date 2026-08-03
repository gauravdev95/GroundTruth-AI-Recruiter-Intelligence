"""Pydantic request/response schemas for recruiter job postings."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from src.domains.recruiter.models import ExperienceLevel, JobStatus, JobType

MAX_TITLE = 200
MAX_DESCRIPTION = 20_000
MAX_SKILLS_PER_JOB = 30


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# Create / edit (draft fields — the recruiter-authored half)
# --------------------------------------------------------------------------


class JobCreateRequest(_StrictModel):
    title: str = Field(min_length=3, max_length=MAX_TITLE)
    description: str = Field(min_length=20, max_length=MAX_DESCRIPTION)
    job_type: JobType
    experience_level: ExperienceLevel
    location: str | None = Field(default=None, max_length=200)
    is_remote: bool = False
    deadline: date | None = None


class JobUpdateRequest(JobCreateRequest):
    """Same shape as create — a PUT replaces the recruiter-authored fields.
    Only legal while the job hasn't been published (see
    `recruiter/service.py::update_job`); a published job's *content* is
    edited through `JobRequirementsConfirmRequest` instead, which is what
    re-triggers confirmation."""


# --------------------------------------------------------------------------
# Extraction draft (LLM output) + confirmation (human-edited, persisted)
# --------------------------------------------------------------------------


class ExtractedSkillResponse(BaseModel):
    name: str
    min_proficiency: str


class ExtractedRequirementsResponse(BaseModel):
    must_have_skills: list[ExtractedSkillResponse]
    desirable_skills: list[ExtractedSkillResponse]
    seniority: str
    role_type: str | None
    is_remote: bool
    location_constraints: str | None


class RequirementSkillRequest(_StrictModel):
    """One row of the editable confirmation screen."""

    skill_name: str = Field(min_length=1, max_length=100)
    min_proficiency: str = Field(pattern="^(novice|intermediate|advanced|expert)$")
    is_required: bool = True
    weight: float = Field(default=1.0, ge=0, le=1)


class JobRequirementsConfirmRequest(_StrictModel):
    """The mandatory confirmation screen's payload — every field the LLM
    extracted, presented back editable. Confirming (whether the recruiter
    changed anything or accepted it verbatim) is what moves a job out of
    `AWAITING_CONFIRMATION`."""

    skills: list[RequirementSkillRequest] = Field(min_length=1, max_length=MAX_SKILLS_PER_JOB)
    seniority: str = Field(pattern="^(entry|mid|senior)$")


class JobRequirementResponse(_ResponseModel):
    id: uuid.UUID
    skill_id: uuid.UUID
    skill_name: str
    min_proficiency: str
    is_required: bool
    weight: float


class JobResponse(_ResponseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    title: str
    description: str
    job_type: JobType
    experience_level: ExperienceLevel
    location: str | None
    is_remote: bool
    deadline: date | None
    status: JobStatus
    extraction_error: str | None
    needs_reembedding: bool
    published_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobDetailResponse(BaseModel):
    job: JobResponse
    extracted_requirements: ExtractedRequirementsResponse | None
    requirements: list[JobRequirementResponse]


class JobListResponse(BaseModel):
    jobs: list[JobResponse]


class JobSubmitAcceptedResponse(BaseModel):
    job: JobResponse
    async_job_id: uuid.UUID
