"""Pydantic request/response schemas for the student profile builder.

Every request model sets `extra="forbid"`, so an unknown key is a 422 rather
than a silently dropped field. That is what stops a client from smuggling
`profile_strength` or `is_discoverable` into a section save: those fields are
not declared on any request model, so sending them is rejected outright
instead of ignored.

The frontend mirrors these rules in zod for UX only — the server never
trusts the client.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timezone
from typing import Generic, TypeVar
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.domains.auth.models import Branch, DegreeType, OnboardingChoice, TargetRole
from src.domains.resume.models import ResumeDraftStatus
from src.domains.student.models import (
    CodingPlatform,
    EmploymentType,
    ProjectKind,
    VerificationStageKind,
    VerificationStageStatus,
    VerificationStatus,
)
from src.domains.student.setup_state import ResumeParseState, SetupStepStatus

MAX_PROJECTS = 3
MAX_CERTIFICATES = 10
MAX_EXPERIENCES = 10
MAX_TECHNOLOGIES = 15

# Graduation year is bounded rather than free: a filterable dropdown on the
# client should not be able to persist a year no recruiter would ever query.
MIN_GRADUATION_YEAR = 1970
MAX_GRADUATION_YEAR = 2100

_GITHUB_USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
_HANDLE_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")

def _utc_today() -> date:
    """UTC-based "today" so a future-date check can't flip with server locale."""
    return datetime.now(timezone.utc).date()


_PLATFORM_PROFILE_URL = {
    CodingPlatform.LEETCODE: "https://leetcode.com/u/{handle}/",
    CodingPlatform.CODEFORCES: "https://codeforces.com/profile/{handle}",
    CodingPlatform.HACKERRANK: "https://www.hackerrank.com/profile/{handle}",
}


class _StrictModel(BaseModel):
    """Base for every request body: unknown keys are an error, not noise."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _require_https_url(value: str, *, field: str) -> str:
    """Reject anything that isn't an absolute http(s) URL.

    `HttpUrl` alone would accept schemes we never want to hand to a
    background fetcher, so the scheme allow-list is explicit.
    """
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"{field} must be an absolute http(s) URL")
    if len(value) > 500:
        raise ValueError(f"{field} must be at most 500 characters")
    return value


def _normalize_technologies(values: list[str]) -> list[str]:
    """Trim, drop blanks, and de-duplicate case-insensitively, preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        cleaned = raw.strip()
        if not cleaned:
            continue
        if len(cleaned) > 60:
            raise ValueError("Each technology must be at most 60 characters")
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    if len(result) > MAX_TECHNOLOGIES:
        raise ValueError(f"At most {MAX_TECHNOLOGIES} technologies are allowed")
    return result


# --------------------------------------------------------------------------
# Section 1 — Basic Information
# --------------------------------------------------------------------------


class BasicInfoRequest(_StrictModel):
    """All fields required: section 1 is mandatory and saved as a unit."""

    headline: str = Field(min_length=3, max_length=200)
    college: str = Field(min_length=2, max_length=200)
    degree: DegreeType
    branch: Branch
    graduation_year: int = Field(ge=MIN_GRADUATION_YEAR, le=MAX_GRADUATION_YEAR)
    location: str = Field(min_length=2, max_length=120)
    target_role: TargetRole


class BasicInfoResponse(_ResponseModel):
    headline: str | None
    college: str | None
    degree: DegreeType | None
    branch: Branch | None
    graduation_year: int | None
    location: str | None
    target_role: TargetRole | None


# --------------------------------------------------------------------------
# Section 2 — Technical Verification
# --------------------------------------------------------------------------


class CodingPlatformItem(_StrictModel):
    platform: CodingPlatform
    handle: str = Field(min_length=1, max_length=100)

    @field_validator("handle")
    @classmethod
    def validate_handle(cls, v: str) -> str:
        if not _HANDLE_RE.match(v):
            raise ValueError("Handle may only contain letters, numbers, dots, hyphens and underscores")
        return v


class TechnicalRequest(_StrictModel):
    """GitHub identity plus at least one competitive-programming profile.

    `github_username` accepts either a bare username or a full GitHub profile
    URL; both normalize to a username, from which the canonical profile URL is
    derived server-side. The client never supplies the stored URL.
    """

    github_username: str = Field(min_length=1, max_length=200)
    coding_profiles: list[CodingPlatformItem] = Field(min_length=1, max_length=len(CodingPlatform))

    @field_validator("github_username")
    @classmethod
    def normalize_github_username(cls, v: str) -> str:
        candidate = v.strip()
        if "/" in candidate or candidate.startswith("http"):
            parsed = urlparse(candidate if candidate.startswith("http") else f"https://{candidate}")
            if parsed.netloc and parsed.netloc.lower().removeprefix("www.") != "github.com":
                raise ValueError("Enter a github.com profile URL or a bare username")
            segments = [segment for segment in parsed.path.split("/") if segment]
            if len(segments) != 1:
                raise ValueError("Enter a GitHub profile URL of the form https://github.com/<username>")
            candidate = segments[0]
        if not _GITHUB_USERNAME_RE.match(candidate):
            raise ValueError("Enter a valid GitHub username")
        return candidate

    @model_validator(mode="after")
    def reject_duplicate_platforms(self) -> "TechnicalRequest":
        platforms = [item.platform for item in self.coding_profiles]
        if len(platforms) != len(set(platforms)):
            raise ValueError("Each coding platform may only be listed once")
        return self


class GithubAccountResponse(_ResponseModel):
    id: uuid.UUID
    github_username: str
    profile_url: str
    verification_status: VerificationStatus
    verified_at: datetime | None
    verification_score: float | None = None
    verification_source: str | None = None


class CodingPlatformAccountResponse(_ResponseModel):
    id: uuid.UUID
    platform: CodingPlatform
    handle: str
    profile_url: str
    verification_status: VerificationStatus
    verified_at: datetime | None
    verification_score: float | None = None
    verification_source: str | None = None


class TechnicalResponse(BaseModel):
    github_account: GithubAccountResponse | None
    coding_profiles: list[CodingPlatformAccountResponse]


def build_coding_platform_url(platform: CodingPlatform, handle: str) -> str:
    return _PLATFORM_PROFILE_URL[platform].format(handle=handle)


def build_github_profile_url(username: str) -> str:
    return f"https://github.com/{username}"


# --------------------------------------------------------------------------
# Section 3 — Skills & Projects
# --------------------------------------------------------------------------


class ProjectItem(_StrictModel):
    kind: ProjectKind
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    repo_url: str | None = Field(default=None, max_length=500)
    technologies: list[str] = Field(default_factory=list)

    @field_validator("technologies")
    @classmethod
    def clean_technologies(cls, v: list[str]) -> list[str]:
        return _normalize_technologies(v)

    @model_validator(mode="after")
    def enforce_kind_shape(self) -> "ProjectItem":
        """A repository needs a URL; a described project needs prose.

        Enforced here rather than as a DB CHECK so the client gets a
        field-level 422 it can attach to the right input.
        """
        if self.kind is ProjectKind.REPOSITORY:
            if not self.repo_url:
                raise ValueError("repo_url is required for a repository project")
            _require_https_url(self.repo_url, field="repo_url")
        else:
            if self.repo_url:
                raise ValueError("repo_url is only allowed when kind is 'repository'")
            if not self.description or not self.description.strip():
                raise ValueError("description is required for a described project")
        return self


class ProjectsRequest(_StrictModel):
    projects: list[ProjectItem] = Field(default_factory=list, max_length=MAX_PROJECTS)

    @model_validator(mode="after")
    def reject_duplicate_projects(self) -> "ProjectsRequest":
        """Reject items that would collide on the service layer's natural key.

        `service._project_key` identifies a repository by URL and a described
        project by title, and reconciles against existing rows on that key.
        Two items sharing a key would silently merge into one row, so they are
        rejected here instead.
        """
        urls = [p.repo_url.casefold() for p in self.projects if p.repo_url]
        if len(urls) != len(set(urls)):
            raise ValueError("The same repository URL may not be listed twice")

        described = [p.title.casefold() for p in self.projects if not p.repo_url]
        if len(described) != len(set(described)):
            raise ValueError("Two described projects may not share the same title")
        return self


class VerificationStageResponse(_ResponseModel):
    """One stage of the repository verification pipeline. Defined above
    `ProjectResponse` because that model embeds a list of these."""

    stage: VerificationStageKind
    status: VerificationStageStatus
    sequence: int
    result: dict | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ProjectResponse(_ResponseModel):
    id: uuid.UUID
    kind: ProjectKind
    title: str
    description: str | None
    repo_url: str | None
    technologies: list[str]
    verification_status: VerificationStatus
    verified_at: datetime | None
    verification_score: float | None = None
    verification_source: str | None = None
    # Contribution analysis etc., written by `verify_repository_task` —
    # already surfaced to recruiters via `pipeline/evidence.py`; a candidate
    # seeing the same analysis of their own repository is not a new
    # disclosure, just the dashboard finally reading a column that already existed.
    verification_payload: dict | None = None
    # Per-stage progress through the seven-stage pipeline. A single
    # `verification_status` says only where a repository ended up; these say
    # how far it got and which stage stopped it, which is the difference
    # between "unverified" and "unverified because the authorship check
    # rejected it".
    verification_stages: list[VerificationStageResponse] = []


class ProjectsResponse(BaseModel):
    projects: list[ProjectResponse]


# --------------------------------------------------------------------------
# Section 4 — Certificates & Achievements
# --------------------------------------------------------------------------


class CertificateItem(_StrictModel):
    title: str = Field(min_length=2, max_length=200)
    issuer: str = Field(min_length=2, max_length=200)
    issued_at: date | None = None
    credential_url: str | None = Field(default=None, max_length=500)

    @field_validator("credential_url")
    @classmethod
    def validate_credential_url(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        return _require_https_url(v, field="credential_url")

    @field_validator("issued_at")
    @classmethod
    def reject_future_issue_date(cls, v: date | None) -> date | None:
        if v is not None and v > _utc_today():
            raise ValueError("issued_at cannot be in the future")
        return v


class CertificatesRequest(_StrictModel):
    certificates: list[CertificateItem] = Field(default_factory=list, max_length=MAX_CERTIFICATES)

    @model_validator(mode="after")
    def reject_duplicate_certificates(self) -> "CertificatesRequest":
        """Same reasoning as `ProjectsRequest`: colliding natural keys would
        merge into one row during reconciliation."""
        urls = [c.credential_url.casefold() for c in self.certificates if c.credential_url]
        if len(urls) != len(set(urls)):
            raise ValueError("The same credential URL may not be listed twice")

        unlinked = [
            (c.title.casefold(), c.issuer.casefold()) for c in self.certificates if not c.credential_url
        ]
        if len(unlinked) != len(set(unlinked)):
            raise ValueError("Two certificates may not share the same title and issuer")
        return self


class CertificateResponse(_ResponseModel):
    id: uuid.UUID
    title: str
    issuer: str
    issued_at: date | None
    credential_url: str | None
    verification_status: VerificationStatus
    verified_at: datetime | None
    verification_score: float | None = None
    verification_source: str | None = None


class CertificatesResponse(BaseModel):
    certificates: list[CertificateResponse]


# --------------------------------------------------------------------------
# Section 5 — Experience
# --------------------------------------------------------------------------


class ExperienceItem(_StrictModel):
    company_name: str = Field(min_length=2, max_length=200)
    title: str = Field(min_length=2, max_length=200)
    employment_type: EmploymentType
    start_date: date
    end_date: date | None = None
    description: str | None = Field(default=None, max_length=4000)
    technologies: list[str] = Field(default_factory=list)

    @field_validator("technologies")
    @classmethod
    def clean_technologies(cls, v: list[str]) -> list[str]:
        return _normalize_technologies(v)

    @model_validator(mode="after")
    def validate_dates(self) -> "ExperienceItem":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        if self.start_date > _utc_today():
            raise ValueError("start_date cannot be in the future")
        return self


class ExperiencesRequest(_StrictModel):
    experiences: list[ExperienceItem] = Field(default_factory=list, max_length=MAX_EXPERIENCES)


class ExperienceResponse(_ResponseModel):
    id: uuid.UUID
    company_name: str
    title: str
    employment_type: EmploymentType
    start_date: date
    end_date: date | None
    description: str | None
    technologies: list[str]
    verification_status: VerificationStatus
    verified_at: datetime | None
    verification_score: float | None = None
    verification_source: str | None = None


class ExperiencesResponse(BaseModel):
    experiences: list[ExperienceResponse]


# --------------------------------------------------------------------------
# Cross-section completeness envelope
# --------------------------------------------------------------------------


class SectionStatus(BaseModel):
    """Per-section state driving the stepper UI.

    `is_filled` and `verification` are deliberately separate: a section can be
    fully filled and still entirely unverified. The UI renders them as two
    distinct badges and must never collapse them into one.
    """

    key: str
    is_complete: bool
    is_filled: bool
    is_mandatory: bool
    filled_count: int
    required_count: int
    points_earned: int
    points_possible: int
    verification: VerificationStatus | None
    missing: list[str]


class ProfileCompletenessResponse(BaseModel):
    profile_strength: int
    # Sections 1-2 done. `meets_section_requirements && !is_discoverable` is
    # the "indexing in progress" window — everything the student can do is
    # done, and the embedding worker has not finished yet. The UI needs both
    # flags to tell that apart from "still missing a required field", which
    # looks identical if you only have `is_discoverable`.
    meets_section_requirements: bool
    is_discoverable: bool
    sections: list[SectionStatus]
    blocking: list[str]
    # `null` until the student answers the onboarding fork. The client uses
    # this, not `profile_strength == 0`, to decide whether to show it —
    # choosing "build manually" writes no section data, so strength alone
    # cannot distinguish "hasn't chosen" from "chose and hasn't saved yet".
    onboarding_choice: OnboardingChoice | None = None


class OnboardingChoiceRequest(BaseModel):
    """Records which lane the student picked at the setup fork.

    A telemetry hint only. It records *that* a student picked a lane; it never
    decides where they may go. Both `/student/profile/setup/resume` and
    `.../manual` stay open regardless of its value, and the setup screen's own
    gate reads `meets_section_requirements` instead — so a student who chose
    "resume" yesterday can still switch to manual today with nothing cleared.

    Write-once in effect: `set_onboarding_choice` ignores a second call.
    """

    model_config = ConfigDict(extra="forbid")

    choice: OnboardingChoice


# --------------------------------------------------------------------------
# Profile setup entry screen
# --------------------------------------------------------------------------


class SetupStepResponse(BaseModel):
    """One circle in the stepper.

    `status` keeps `saved` and `verified` distinct for the same reason
    `SectionStatus` keeps `is_filled` and `verification` distinct — filled is
    not verified, and the UI must not collapse the two.
    """

    key: str
    index: int
    title: str
    subtitle: str
    status: SetupStepStatus
    is_mandatory: bool
    # Which circle is filled violet and carries the "Current Step" pill. A
    # display hint: every step stays navigable regardless.
    is_current: bool
    filled_count: int
    required_count: int


class ResumeSetupStateResponse(BaseModel):
    """The newest resume attempt, so a returning student resumes where they were.

    `status == parsing` lands on the analyzing state; `parsed` with a
    `pending_review` draft lands on the review screen; `failed` lands on the
    error state with the manual path still offered.
    """

    has_upload: bool
    upload_id: uuid.UUID | None = None
    status: ResumeParseState | None = None
    async_job_id: uuid.UUID | None = None
    draft_id: uuid.UUID | None = None
    draft_status: ResumeDraftStatus | None = None
    original_filename: str | None = None
    error: str | None = None


class SetupStateResponse(BaseModel):
    """Everything `/student/profile/setup` renders, in one request.

    Derived entirely from persisted rows — `completeness.py` for the sections,
    `resume_uploads` for the resume. No field here is stored, and none is ever
    accepted from a client.
    """

    completion_percentage: int
    current_step_index: int
    meets_section_requirements: bool
    is_discoverable: bool
    blocking: list[str]
    steps: list[SetupStepResponse]
    resume: ResumeSetupStateResponse


SectionData = TypeVar("SectionData")


class SectionEnvelope(BaseModel, Generic[SectionData]):
    """Uniform shape for every section GET and PUT.

    Bundling `completeness` with the section payload means a save refreshes
    the stepper's strength meter and discoverability banner in one round trip,
    with no follow-up fetch that could render a stale score.
    """

    data: SectionData
    completeness: ProfileCompletenessResponse
