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

import enum
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
from src.domains.student.activity import StageKey as ActivityStageKey
from src.domains.student.activity import StageState as ActivityStageState
from src.domains.student.setup_state import ResumeParseState, SetupStepStatus

MAX_PROJECTS = 3
MAX_CERTIFICATES = 5
MAX_EXPERIENCES = 5
MAX_TECHNOLOGIES = 15

#: One to three, per the onboarding flow. A cap rather than a single value
#: because a student targeting backend *and* ML is stating a real preference,
#: and forcing the choice loses information the matcher can use. Capped at
#: three because a candidate who selects seven roles has told the matcher
#: nothing.
MAX_TARGET_ROLES = 3
#: Max tags on one experience entry.
MAX_EXPERIENCE_TECHNOLOGIES = 8

#: Moved here from `auth/schemas.py` when phone collection moved off signup.
#: E.164-ish: optional +, no leading zero, 8-15 digits.
_PHONE_RE = re.compile(r"^\+?[1-9]\d{7,14}$")

# Graduation year is bounded rather than free: a filterable dropdown on the
# client should not be able to persist a year no recruiter would ever query.
MIN_GRADUATION_YEAR = 1970
MAX_GRADUATION_YEAR = 2100

_GITHUB_USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
_HANDLE_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")

def _utc_today() -> date:
    """UTC-based "today" so a future-date check can't flip with server locale."""
    return datetime.now(timezone.utc).date()


#: Must cover every `CodingPlatform` member **except** `OTHER` — a missing
#: entry would raise a KeyError while saving section 2. `test_schemas.py`
#: asserts exhaustiveness so adding a platform without its URL template fails a
#: test rather than a save.
#:
#: `OTHER` is absent by design: it names a platform this codebase has no
#: template and no checker for, so the student supplies the full profile URL
#: instead. `build_coding_platform_url` refuses to guess one.
_PLATFORM_PROFILE_URL = {
    CodingPlatform.LEETCODE: "https://leetcode.com/u/{handle}/",
    CodingPlatform.CODEFORCES: "https://codeforces.com/profile/{handle}",
    CodingPlatform.HACKERRANK: "https://www.hackerrank.com/profile/{handle}",
    CodingPlatform.CODECHEF: "https://www.codechef.com/users/{handle}",
    CodingPlatform.ATCODER: "https://atcoder.jp/users/{handle}",
    CodingPlatform.GEEKSFORGEEKS: "https://www.geeksforgeeks.org/user/{handle}/",
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


def normalize_github_username(value: str) -> str:
    """Accept a bare username or a github.com profile URL; return the username.

    Module-level rather than a method so `TechnicalRequest` (the save) and
    `VerifyGithubRequest` (the Verify button) share one definition. Two copies
    would eventually disagree, and the failure mode is the worst kind: a value
    the button accepts and the save rejects, on the same screen.
    """
    candidate = value.strip()
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
    """Section 1 is mandatory and saved as a unit — every field below is
    required **except** `about`.

    `about` is optional because it contributes no completeness points (see
    `CandidateProfile.about` for why the scored field tuple is fixed at seven),
    and a field that cannot affect whether the section is complete must not be
    able to reject the save. It still reaches the profile embedding, so filling
    it in improves matching without being a gate.
    """

    #: Moved here from signup, which now takes an email and a password only.
    #:
    #: Required to save the section, but deliberately NOT added to
    #: `completeness.py::_BASIC_FIELDS`. That tuple has exactly seven entries
    #: worth five points each, summing to the 35 this section contributes;
    #: adding an eighth would either change the section's total or change
    #: every existing student's strength retroactively for a field they had
    #: no chance to fill. `about` already establishes the pattern of a field
    #: that lives in this request without being scored.
    #:
    #: Writes through to `User.full_name` rather than to the profile — the
    #: name belongs to the account, and duplicating it onto the profile would
    #: create two answers to what a person is called.
    full_name: str = Field(min_length=2, max_length=200)

    #: Also moved off signup. Optional here, unlike the name: a phone number
    #: is useful to a recruiter but is not needed to build or score a
    #: profile, and requiring one at the first section would reintroduce
    #: exactly the friction removing it from signup was meant to eliminate.
    #: Validated only when supplied — an empty string clears it, matching
    #: how `""` already represents "no phone number" on profiles created via
    #: OAuth.
    phone_number: str | None = Field(default=None, max_length=20)
    headline: str = Field(min_length=3, max_length=200)
    college: str = Field(min_length=2, max_length=200)
    degree: DegreeType
    branch: Branch
    graduation_year: int = Field(ge=MIN_GRADUATION_YEAR, le=MAX_GRADUATION_YEAR)
    location: str = Field(min_length=2, max_length=120)
    #: One to three roles, in the student's order of preference. The first is
    #: stored additionally as the scalar `CandidateProfile.target_role`, which
    #: is what the matcher indexes — see that column for why both exist.
    #:
    #: The scalar is deliberately **not** accepted here. It is derived, and a
    #: request that could set it independently could put it out of step with
    #: the array it is supposed to mirror.
    target_roles: list[TargetRole] = Field(min_length=1, max_length=MAX_TARGET_ROLES)
    about: str | None = Field(default=None, max_length=2000)

    @field_validator("target_roles")
    @classmethod
    def reject_duplicate_roles(cls, v: list[TargetRole]) -> list[TargetRole]:
        """Order carries meaning (the first is primary), so this deduplicates
        by rejecting rather than by collapsing — silently dropping a repeat
        would change which role ends up primary without telling anyone."""
        if len(v) != len(set(v)):
            raise ValueError("Each target role may only be selected once")
        return v

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """Same rule the signup form used to enforce, relocated.

        `None` and `""` both mean "not supplied" and pass through as `""`,
        which is the representation profiles already use. Anything else must
        be a real number — a half-typed one is worse than none, because a
        recruiter would dial it.
        """
        if v is None:
            return None
        cleaned = v.strip().replace(" ", "").replace("-", "")
        if not cleaned:
            return ""
        if not _PHONE_RE.match(cleaned):
            raise ValueError("Enter a valid phone number (8-15 digits, optional leading +)")
        return cleaned


class BasicInfoResponse(_ResponseModel):
    #: Read from `User.full_name`, which is NULL between signup and the first
    #: save of this section. The client renders the field empty in that
    #: window rather than pre-filling a guess.
    full_name: str | None
    phone_number: str | None
    headline: str | None
    college: str | None
    degree: DegreeType | None
    branch: Branch | None
    graduation_year: int | None
    location: str | None
    #: The primary role. Kept in the response beside the array because the
    #: recruiter-facing surfaces read this one, and a client that renders a
    #: single role should render the same one the matcher used.
    target_role: TargetRole | None
    #: NULL for a profile that has never saved this section — distinct from
    #: `[]`, which this column never holds.
    target_roles: list[TargetRole] | None
    about: str | None
    #: Whether a photo is stored. The image itself comes from
    #: `GET /student/profile/photo`, which mints a short-lived link — the same
    #: split certificates use, so an object key never reaches a client.
    has_profile_photo: bool = False


# --------------------------------------------------------------------------
# Section 2 — Technical Verification
# --------------------------------------------------------------------------


class CodingPlatformItem(_StrictModel):
    """One claimed competitive-programming handle.

    `custom_platform_name` and `profile_url` are meaningful only when
    `platform is OTHER` — that member exists precisely because the platform is
    one this codebase has no URL template for, so the student supplies both the
    name and the link. Sending either for a known platform is rejected rather
    than ignored: a stored `profile_url` that disagrees with the template would
    be the URL the verification worker actually fetches.
    """

    platform: CodingPlatform
    handle: str = Field(min_length=1, max_length=100)
    custom_platform_name: str | None = Field(default=None, max_length=60)
    profile_url: str | None = Field(default=None, max_length=500)

    @field_validator("handle")
    @classmethod
    def validate_handle(cls, v: str) -> str:
        if not _HANDLE_RE.match(v):
            raise ValueError("Handle may only contain letters, numbers, dots, hyphens and underscores")
        return v

    @model_validator(mode="after")
    def enforce_other_shape(self) -> "CodingPlatformItem":
        if self.platform is CodingPlatform.OTHER:
            if not self.custom_platform_name:
                raise ValueError("Name the platform when choosing 'Other'")
            if not self.profile_url:
                raise ValueError("A profile URL is required when choosing 'Other'")
            _require_https_url(self.profile_url, field="profile_url")
        else:
            if self.custom_platform_name:
                raise ValueError("custom_platform_name is only allowed when platform is 'other'")
            if self.profile_url:
                raise ValueError("profile_url is only allowed when platform is 'other'")
        return self


def _reject_duplicate_platforms(items: list[CodingPlatformItem]) -> list[CodingPlatformItem]:
    """Shared by both requests that carry coding profiles. One row per platform:
    two Codeforces handles on one profile is a data-entry mistake, not a claim
    the verifier could resolve."""
    platforms = [item.platform for item in items]
    if len(platforms) != len(set(platforms)):
        raise ValueError("Each coding platform may only be listed once")
    return items


class TechnicalRequest(_StrictModel):
    """GitHub identity plus any competitive-programming profiles.

    `github_username` accepts either a bare username or a full GitHub profile
    URL; both normalize to a username, from which the canonical profile URL is
    derived server-side. The client never supplies the stored URL.

    **`coding_profiles` may now be empty.** It used to require at least one,
    back when GitHub and coding profiles were a single mandatory section. They
    are separate sections now and only GitHub is required, so demanding a
    handle here would reintroduce the gate that split was meant to remove — and
    would 422 the resume-import path for every resume that mentions a GitHub
    account and no Codeforces handle.

    Onboarding does not use this endpoint: the GitHub step connects via OAuth
    and the coding step posts `CodingProfilesRequest`. It remains the way the
    resume-confirm path writes both at once, and the way the profile editor
    saves them together after onboarding.
    """

    github_username: str = Field(min_length=1, max_length=200)
    coding_profiles: list[CodingPlatformItem] = Field(
        default_factory=list, max_length=len(CodingPlatform)
    )

    @field_validator("github_username")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        return normalize_github_username(v)

    @model_validator(mode="after")
    def reject_duplicate_platforms(self) -> "TechnicalRequest":
        _reject_duplicate_platforms(self.coding_profiles)
        return self


class CodingProfilesRequest(_StrictModel):
    """Onboarding stage 4, on its own.

    An empty list is a valid, meaningful body: it is what "Skip for now" sends,
    and what an edit that removes every handle sends. The section is optional
    and clearing it must be expressible — a save that cannot say "none" would
    make the first handle a student entered permanent.

    Carries no `github_username`, which is what keeps this endpoint from being
    able to disturb the mandatory section next door.
    """

    coding_profiles: list[CodingPlatformItem] = Field(
        default_factory=list, max_length=len(CodingPlatform)
    )

    @model_validator(mode="after")
    def reject_duplicate_platforms(self) -> "CodingProfilesRequest":
        _reject_duplicate_platforms(self.coding_profiles)
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
    custom_platform_name: str | None = None
    verification_status: VerificationStatus
    verified_at: datetime | None
    verification_score: float | None = None
    verification_source: str | None = None


class TechnicalResponse(BaseModel):
    github_account: GithubAccountResponse | None
    coding_profiles: list[CodingPlatformAccountResponse]


def build_coding_platform_url(platform: CodingPlatform, handle: str, *, custom_url: str | None = None) -> str:
    """The canonical profile URL for a claimed handle.

    `custom_url` is required for — and only accepted from — `OTHER`. Falling
    back to a guessed template there would hand the verification worker a URL
    nobody supplied, and a 404 on a URL we invented would be recorded as the
    candidate's claim failing.
    """
    if platform is CodingPlatform.OTHER:
        if not custom_url:
            raise ValueError("A profile URL is required for the 'other' platform")
        return custom_url
    return _PLATFORM_PROFILE_URL[platform].format(handle=handle)


def build_github_profile_url(username: str) -> str:
    return f"https://github.com/{username}"


# --------------------------------------------------------------------------
# Section 3 — Skills & Projects
# --------------------------------------------------------------------------


class ProjectItem(_StrictModel):
    """A project claim.

    Note the field name: **`claimed_technologies`**, not `technologies`. The
    two are different facts and this model refuses to let them share a word.
    `Project.technologies` is written by the verification worker from the
    repository's own dependency manifests (`domains/verification/manifests.py`)
    and is the list `domains/verification/skills.py` turns into verified
    skills — the only write site for a skill in this codebase. A candidate
    cannot write to it, before or after this change, because a self-declared
    stack rendered identically to a detected one is the exact problem this
    platform exists to remove.

    What the student types lands in `claimed_technologies` instead: a claim
    submitted for corroboration, exactly the role `ExperienceItem.technologies`
    already plays. (That model gets the shorter name because `experiences` has
    no detected list to be confused with.) It never reaches `candidate_skills`
    and never renders as verified.
    """

    kind: ProjectKind
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    repo_url: str | None = Field(default=None, max_length=500)
    live_demo_url: str | None = Field(default=None, max_length=500)
    claimed_technologies: list[str] = Field(default_factory=list)
    # The student's nomination of their strongest project. Enforced as
    # at-most-one across the section by `ProjectsRequest` below.
    is_primary: bool = False

    @field_validator("claimed_technologies")
    @classmethod
    def clean_claimed_technologies(cls, v: list[str]) -> list[str]:
        return _normalize_technologies(v)

    @field_validator("live_demo_url")
    @classmethod
    def validate_live_demo_url(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        return _require_https_url(v, field="live_demo_url")

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

    @model_validator(mode="after")
    def reject_multiple_primaries(self) -> "ProjectsRequest":
        """"Main project" is a nomination, so exactly one can hold it.

        Rejected rather than silently keeping the first: two flags mean the
        client's state is wrong, and quietly picking one would ship a project
        card labelled "main" that the student never chose.
        """
        if sum(1 for p in self.projects if p.is_primary) > 1:
            raise ValueError("Only one project can be marked as the main project")
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
    live_demo_url: str | None = None
    is_primary: bool = False
    # Detected by the verification worker. Read-only for the candidate.
    technologies: list[str]
    # What the candidate said. Returned alongside rather than merged, so a UI
    # can render the difference — which is the whole point of storing them
    # apart. See `ProjectItem`.
    claimed_technologies: list[str] = []
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
    """A certificate claim, optionally with an uploaded copy.

    `file_object_key` is not a free-form string the client may invent: it must
    be a key this candidate's own upload endpoint minted, and
    `service.replace_certificates` re-checks the prefix against their profile
    id before storing it. Without that check, a caller could attach another
    candidate's uploaded file to their own certificate by guessing a key.
    """

    title: str = Field(min_length=2, max_length=200)
    issuer: str = Field(min_length=2, max_length=200)
    issued_at: date | None = None
    credential_url: str | None = Field(default=None, max_length=500)
    # Returned by `POST /certificates/uploads`; echoed back here to attach the
    # stored object to the certificate the student was filling in.
    file_object_key: str | None = Field(default=None, max_length=500)
    file_name: str | None = Field(default=None, max_length=255)
    file_content_type: str | None = Field(default=None, max_length=100)
    file_size_bytes: int | None = Field(default=None, ge=0)
    # Detaching is explicit, because *omitting* the key cannot mean "remove":
    # the response never returns the key, so every ordinary re-save of an
    # unchanged certificate arrives without one. See
    # `service.replace_certificates`.
    remove_file: bool = False

    @model_validator(mode="after")
    def enforce_file_shape(self) -> "CertificateItem":
        """The file columns move together or not at all — a key with no name
        would render as an unlabelled download, and a name with no key as a
        broken one."""
        if self.file_object_key and not self.file_name:
            raise ValueError("file_name is required when a certificate file is attached")
        if self.file_name and not self.file_object_key:
            raise ValueError("file_object_key is required when a certificate file is attached")
        if self.remove_file and self.file_object_key:
            raise ValueError("Cannot attach and remove a certificate file in the same request")
        return self

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
    # The object key is deliberately absent: the bucket is private and the only
    # read path is `GET /certificates/{id}/file`, which mints a short-lived
    # presigned URL. Returning the key would leak the object layout and tempt a
    # client into building its own URLs.
    #
    # Its absence also means a client cannot echo it back on the next PUT,
    # which is why `service.replace_certificates` *preserves* an existing
    # attachment when an item arrives without one rather than treating the
    # omission as a delete.
    file_name: str | None = None
    file_size_bytes: int | None = None
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
    """Unlike `ProjectItem`, this **does** accept `technologies` — and the
    distinction is deliberate rather than an inconsistency.

    Here the list is a *claim submitted for corroboration*, never a skill.
    `jobs/tasks/verification.py::verify_experience_task` checks it against the
    technologies already verified from the candidate's repositories
    (`domains/verification/experience.py`); overlap raises confidence in the
    experience, and no overlap lowers it. It is the only corroboration signal
    an experience has, since no third-party source of truth exists for "worked
    at X".

    It never reaches `candidate_skills`, never appears as a verified skill, and
    an experience can never reach `VERIFIED` on the strength of it — the
    ceiling is `FLAGGED`.
    """

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
    # Onboarding finished. Carried on every section response so a save that
    # completes the flow tells the client immediately, rather than leaving the
    # dashboard gate to a follow-up request that has not landed yet.
    is_onboarding_submitted: bool = False


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
    # Onboarding is finished. The dashboard gate — see
    # `CandidateProfile.onboarding_submitted_at`.
    is_submitted: bool = False
    # Whether Submit would succeed right now.
    can_submit: bool = False


class ActivityStageResponse(BaseModel):
    """One background stage, as the analysis feed renders it.

    Deliberately carries no percentage. Every stage here is a third-party
    call whose duration is unknown until it returns, so a percentage could
    only be invented — and this product does not invent progress any more
    than it invents evidence. See `domains/student/activity.py`.

    `total` and `settled` are returned raw rather than as a pre-rendered
    sentence so the client owns its own copy and tense ("Analyzing 2 of 3
    repositories" vs "Analyzed 3 repositories").
    """

    key: ActivityStageKey
    label: str
    state: ActivityStageState
    total: int
    settled: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    #: Student-facing explanation, present only on `failed`. Never a trace.
    detail: str | None = None


class ActivityFeedResponse(BaseModel):
    """The live analysis feed.

    `is_running` is the client's polling gate: it stops when this is false,
    so "finished" has exactly one definition and lives on the server.
    """

    stages: list[ActivityStageResponse]
    is_running: bool
    #: Snapshot time. The client renders elapsed durations against this
    #: rather than its own clock, so a device with a skewed clock cannot
    #: display a negative or wildly wrong duration.
    as_of: datetime


class ProfileSubmitRequest(_StrictModel):
    """The review step's consent, carried on the submission itself.

    `consent` must be `true`; `false` is rejected rather than treated as
    "submit without consenting", because there is no such submission — the
    repository analysis and interview generation this flow exists to start are
    exactly what is being consented to.

    It is a field on the submit request rather than a separate
    `POST /consent` endpoint so that consent and submission are one
    transaction. Two calls could leave a profile consented but unsubmitted, or
    — far worse — submitted while the consent write failed, which is a profile
    being analysed on a consent record that does not exist.
    """

    consent: bool

    @field_validator("consent")
    @classmethod
    def require_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "Consent is required to analyse your repositories and generate interview questions"
            )
        return v


class ProfileSubmitResponse(BaseModel):
    """The result of pressing Submit on the review step.

    `queued_verifications` is a count, not a list of ids: the student is told
    that checks are running, and the ids are internal job identity they have no
    endpoint for. It is surfaced at all because "we're checking N things in the
    background" is the honest version of the spinner-free hand-off — the
    student is not waiting on any of it.
    """

    is_submitted: bool
    submitted_at: datetime
    queued_verifications: int
    completeness: ProfileCompletenessResponse


# --------------------------------------------------------------------------
# Synchronous verification — the "Verify" buttons on step 3
# --------------------------------------------------------------------------


class VerifyOutcome(str, enum.Enum):
    """What a *synchronous* check concluded.

    Deliberately not `VerificationStatus`: that enum is the durable state of a
    stored claim, written only by the background workers, and reusing it here
    would let a button appear to write one. These three values describe a
    single live probe and are never persisted.

    * `verified` — the account provably exists (and, for GitHub OAuth, is
      provably the student's).
    * `unconfirmed` — the platform exposes no way to check, but the profile URL
      resolves. Enough to save; not enough to claim as proof.
    * `failed` — the check ran and found nothing, or the platform was
      unreachable. The message says which.
    """

    VERIFIED = "verified"
    UNCONFIRMED = "unconfirmed"
    FAILED = "failed"


class VerifyGithubRequest(_StrictModel):
    """Accepts the same bare-username-or-URL shapes `TechnicalRequest` does,
    normalised by the same validator so the two cannot disagree about what
    counts as a valid GitHub identity."""

    github_username: str = Field(min_length=1, max_length=200)

    @field_validator("github_username")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        return normalize_github_username(v)


class VerifyGithubResponse(BaseModel):
    outcome: VerifyOutcome
    message: str
    github_username: str
    profile_url: str
    avatar_url: str | None = None
    public_repos: int | None = None
    # True when the account is already OAuth-connected, which is stronger than
    # anything this endpoint can establish — the UI stops offering to verify.
    is_oauth_connected: bool = False


class VerifyCodingProfileRequest(_StrictModel):
    platform: CodingPlatform
    handle: str = Field(min_length=1, max_length=100)
    profile_url: str | None = Field(default=None, max_length=500)

    @field_validator("handle")
    @classmethod
    def validate_handle(cls, v: str) -> str:
        if not _HANDLE_RE.match(v):
            raise ValueError("Handle may only contain letters, numbers, dots, hyphens and underscores")
        return v

    @model_validator(mode="after")
    def require_url_for_other(self) -> "VerifyCodingProfileRequest":
        if self.platform is CodingPlatform.OTHER:
            if not self.profile_url:
                raise ValueError("A profile URL is required when checking the 'other' platform")
            _require_https_url(self.profile_url, field="profile_url")
        return self


class VerifyCodingProfileResponse(BaseModel):
    outcome: VerifyOutcome
    message: str
    platform: CodingPlatform
    handle: str
    profile_url: str
    # Whatever the check could read — solved count, rating, rank. Shape varies
    # by platform, so it is passed through for display rather than modelled;
    # nothing branches on it.
    details: dict = {}


# --------------------------------------------------------------------------
# Certificate file upload
# --------------------------------------------------------------------------


class CertificateUploadResponse(BaseModel):
    """What the student echoes back on the certificates PUT to attach the file.

    The object key is returned here — and *only* here — because the client has
    to name the object it just uploaded. It is re-checked against the caller's
    own profile prefix on save (`service.replace_certificates`), so possessing
    a key is not authority to attach it.
    """

    file_object_key: str
    file_name: str
    file_content_type: str
    file_size_bytes: int


class CertificateFileUrlResponse(BaseModel):
    """A short-lived presigned link. The bucket stays private."""

    url: str
    file_name: str
    expires_in_seconds: int


class ProfilePhotoResponse(BaseModel):
    """A short-lived presigned link to the student's photo.

    Unlike a certificate upload, this returns no object key. A certificate is
    one row of a list the client has to re-send on the next section save, so it
    must be able to name the object it uploaded; a photo is singular and is
    attached to the profile by the upload call itself, so the key never needs
    to leave the server.

    `url` is null when no photo is stored, rather than the endpoint 404ing:
    "this student has no photo" is an ordinary answer the avatar component
    renders initials for, not an error.
    """

    url: str | None
    content_type: str | None
    expires_in_seconds: int | None


SectionData = TypeVar("SectionData")


class SectionEnvelope(BaseModel, Generic[SectionData]):
    """Uniform shape for every section GET and PUT.

    Bundling `completeness` with the section payload means a save refreshes
    the stepper's strength meter and discoverability banner in one round trip,
    with no follow-up fetch that could render a stale score.
    """

    data: SectionData
    completeness: ProfileCompletenessResponse
