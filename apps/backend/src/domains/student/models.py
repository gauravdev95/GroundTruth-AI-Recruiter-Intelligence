"""SQLAlchemy models backing the student profile builder.

Scope note — this module deliberately implements *less* than
`docs/DATA_MODEL.md` §3 designs, because the builder only records what a
student **claims**. Everything that requires calling GitHub or a coding
platform (numeric `github_user_id`/`github_repo_id`, analyses, snapshots)
belongs to the Phase II verification workers and is not modeled here.

Two intentional divergences from the §3 design, both agreed before
implementation:

1. **`projects` instead of `repositories`.** §3's `repositories` is
   GitHub-shaped (`github_repo_id BigInteger NOT NULL`, `is_fork`,
   `primary_language`) and can only be populated from the GitHub API. The
   builder's section 3 accepts "a repo URL *or* a described project", so it
   needs a table that can hold a free-text project with no GitHub identity.
   `repositories` stays unbuilt, reserved for the GitHub-sync phase.
2. **No `evidence_records` writes.** §3's `evidence_records` is a derived
   *scoring* hub: it carries `weight NUMERIC NOT NULL` and a `source_type`
   naming completed artifacts (`repository_analysis`,
   `coding_platform_snapshot`), neither of which exists at claim time, and
   it has no `status` column. Pending verification is therefore tracked by
   each source row's own `verification_status` plus a queued `AsyncJob` —
   see `src/domains/student/evidence.py`.

Nothing in this layer ever writes `VerificationStatus.VERIFIED`.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base
from src.shared.db_mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class VerificationStatus(str, enum.Enum):
    """Shared verification lifecycle for every claim a student makes.

    The profile builder may only ever write `UNVERIFIED` or `PENDING`.
    `VERIFIED`/`REJECTED`/`FLAGGED` are written exclusively by the
    verification consumers in `src/jobs/tasks/verification.py`.

    `FLAGGED` is distinct from `REJECTED`: it means the claim stays visible
    to recruiters but could not be *strongly* confirmed — an unmatched
    certificate-issuer domain, a coding-platform handle checked only by a
    reachability heuristic, a self-reported experience with no independent
    source of truth. `REJECTED` means the check actively contradicted the
    claim (e.g. the contribution share was near zero, or a credential URL
    404s). A failed third-party call (timeout, outage) leaves the row at
    `UNVERIFIED` — never `VERIFIED` — so an infrastructure blip cannot look
    like a passed check.
    """

    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    FLAGGED = "flagged"


class VerificationResultMixin:
    """The written-back outcome of a verification check (`docs/DATA_MODEL.md`
    §0.5-adjacent, scoped to this layer rather than `evidence_records` — see
    `src/jobs/tasks/verification.py` module docstring for why).

    - `verification_score`: 0-100, the check's own confidence/quality number.
      Its meaning is check-specific (contribution share and quality signals
      for a repository, reachability + issuer match for a certificate) —
      `verification_source` names which check produced it.
    - `verification_source`: short machine-readable string identifying the
      check, e.g. `"github_api"`, `"codeforces_api"`, `"certificate_url_check"`.
    - `verification_payload`: the raw evidence the check was based on
      (API response fields actually used, not a full dump), kept for audit —
      "why does this candidate have this score" must always be answerable.
    """

    verification_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    verification_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verification_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class CodingPlatform(str, enum.Enum):
    """Competitive-programming platforms a student may claim a handle on.

    Confidence differs sharply by platform and that is reflected in what a
    check can conclude, not in whether the platform is offered: only
    Codeforces has a documented public API, so it is the only one whose
    verification can reach `VERIFIED` on hard data. The rest are checked by
    reachability heuristics and cap at `FLAGGED` — see
    `domains/verification/clients/`.

    `OTHER` is the escape hatch for a platform this list does not name. It has
    no URL template (the student supplies the full profile URL) and no
    platform-specific check, so it can only ever reach `FLAGGED` via
    reachability — the same ceiling as HackerRank, for the same reason.
    """

    LEETCODE = "leetcode"
    CODEFORCES = "codeforces"
    HACKERRANK = "hackerrank"
    CODECHEF = "codechef"
    ATCODER = "atcoder"
    GEEKSFORGEEKS = "geeksforgeeks"
    OTHER = "other"


class ProjectKind(str, enum.Enum):
    """Discriminates section 3's two accepted shapes."""

    REPOSITORY = "repository"
    DESCRIBED = "described"


class EmploymentType(str, enum.Enum):
    """Shapes of work a student can report in section 5.

    `OPEN_SOURCE` is the one value with an independent corroboration path:
    contributions to a public repository can be cross-checked against the
    candidate's verified GitHub identity, unlike the rest, which have no
    third-party source of truth and therefore cap at `FLAGGED`
    (see `Experience` below).
    """

    INTERNSHIP = "internship"
    FULL_TIME = "full_time"
    FREELANCE = "freelance"
    PART_TIME = "part_time"
    RESEARCH = "research"
    OPEN_SOURCE = "open_source"


class GithubAccount(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VerificationResultMixin, Base):
    """A student's claimed GitHub identity.

    `github_user_id` is nullable here (unlike §3's design) because the
    builder only has a username/URL — resolving it to GitHub's stable
    numeric id requires an API call owned by the verification worker.
    It stays UNIQUE: Postgres permits many NULLs under a unique index, so
    the constraint binds only once a worker fills the id in.

    `access_token_encrypted`/`token_scopes`/`oauth_connected_at` are set only
    when the student connects via OAuth (`src/domains/student/github_oauth.py`)
    rather than typing a bare username — see that module for why an
    OAuth-verified account is written straight to `VERIFIED` instead of going
    through the async verification queue.
    """

    __tablename__ = "github_accounts"

    candidate_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    github_username: Mapped[str] = mapped_column(String(100), nullable=False)
    profile_url: Mapped[str] = mapped_column(String(500), nullable=False)
    github_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, name="verification_status", native_enum=True),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- OAuth token storage (nullable: most rows are username-only claims) ---
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_scopes: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    oauth_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    candidate_profile: Mapped["CandidateProfile"] = relationship(  # noqa: F821
        back_populates="github_accounts"
    )


class CodingPlatformAccount(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VerificationResultMixin, Base):
    """A student's claimed handle on a competitive-programming platform."""

    __tablename__ = "coding_platform_accounts"
    __table_args__ = (UniqueConstraint("candidate_profile_id", "platform", name="uq_coding_platform_per_candidate"),)

    candidate_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[CodingPlatform] = mapped_column(
        SAEnum(CodingPlatform, name="coding_platform", native_enum=True), nullable=False
    )
    handle: Mapped[str] = mapped_column(String(100), nullable=False)
    profile_url: Mapped[str] = mapped_column(String(500), nullable=False)
    # Only set when `platform is OTHER` — the display name the student typed
    # ("TopCoder", "SPOJ"). A column rather than a widened enum because a
    # platform nobody has written a checker for is data, not a code path: new
    # enum members are how a platform gets its own verification branch, and
    # minting one per free-text entry would imply a check that does not exist.
    custom_platform_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, name="verification_status", native_enum=True),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    candidate_profile: Mapped["CandidateProfile"] = relationship(  # noqa: F821
        back_populates="coding_platform_accounts"
    )


class Project(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VerificationResultMixin, Base):
    """A repository link or a described project (section 3, max 3 rows).

    `repo_url` is required when `kind=REPOSITORY` and forbidden otherwise;
    `description` is required when `kind=DESCRIBED`. Enforced in the Pydantic
    layer (`schemas.ProjectItem`) rather than as a CHECK constraint, keeping
    the rule reportable as a field-level 422 instead of an opaque DB error.
    """

    __tablename__ = "projects"

    candidate_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[ProjectKind] = mapped_column(
        SAEnum(ProjectKind, name="project_kind", native_enum=True), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    repo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Optional deployed URL. Never fetched or verified — it is shown to
    # recruiters as a link the candidate provided, and no check here could
    # distinguish a live demo from any other reachable page.
    live_demo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # **Detected**, not typed: written by `verify_repository_task` from the
    # repository's own dependency manifests. See `claimed_technologies` below
    # for the student-supplied list, which is deliberately a different column.
    technologies: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list, nullable=False)
    # What the student says the project is built with. Kept apart from
    # `technologies` so a claim can never be rendered as a detection: the
    # recruiter-facing evidence surfaces read the detected list, and this one
    # exists to be *corroborated against* it — exactly the role
    # `Experience.technologies` already plays for work history.
    claimed_technologies: Mapped[list[str]] = mapped_column(
        ARRAY(String(60)), default=list, nullable=False
    )
    # The one project the student nominates as their strongest. At most one row
    # per candidate carries this; `service.replace_projects` enforces it, since
    # a partial unique index would reject the intermediate state a full-section
    # replace passes through.
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Preserves the student's chosen ordering across a full-section replace.
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, name="verification_status", native_enum=True),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    candidate_profile: Mapped["CandidateProfile"] = relationship(back_populates="projects")  # noqa: F821
    verification_stages: Mapped[list["VerificationStage"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="VerificationStage.sequence",
    )


class VerificationStageKind(str, enum.Enum):
    """The seven stages of repository verification, in the order they run.

    Declared as an ordered enum rather than free-text so `sequence` and the
    "a stage may not start before its predecessor succeeded" rule are both
    derivable from one definition — see `STAGE_SEQUENCE` below.
    """

    REPOSITORY_SELECTION = "repository_selection"
    FORK_AUTHORSHIP_CHECK = "fork_authorship_check"
    CONTRIBUTION_ANALYSIS = "contribution_analysis"
    ARCHITECTURE_CODE_QUALITY = "architecture_code_quality"
    TECHNOLOGY_DETECTION = "technology_detection"
    CODE_GROUNDED_INTERVIEW = "code_grounded_interview"
    EVIDENCE_REPORT = "evidence_report"


#: Canonical run order. Index + 1 is the stored `sequence`, so the ordering
#: lives in exactly one place and a reordering cannot drift from the data.
STAGE_SEQUENCE: tuple[VerificationStageKind, ...] = tuple(VerificationStageKind)


class VerificationStageStatus(str, enum.Enum):
    """`SKIPPED` is distinct from `FAILED`: a stage that never ran because an
    earlier stage failed (or because authorship was rejected, which
    deliberately suppresses the interview) is not itself a failure, and the
    two must not be conflated when reporting why a repository is unverified.
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class VerificationStage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One stage of one repository's verification pipeline.

    Repository verification used to be a single Celery task writing a single
    `Project.verification_payload` blob, so a failure in a late stage threw
    away the output of every stage that had already succeeded. One row per
    `(project, stage)` makes each stage's result independently queryable and
    independently retryable, and means a mid-pipeline failure preserves
    everything computed before it.

    `result` holds only that stage's own output. The composite
    `Project.verification_payload` is still written at the end of the run —
    it is what the interview and matching layers read — but it is now assembled
    from these rows rather than being the only place the analysis exists.
    """

    __tablename__ = "verification_stages"
    __table_args__ = (
        UniqueConstraint("project_id", "stage", name="uq_verification_stage_project_stage"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[VerificationStageKind] = mapped_column(
        SAEnum(VerificationStageKind, name="verification_stage_kind", native_enum=True), nullable=False
    )
    status: Mapped[VerificationStageStatus] = mapped_column(
        SAEnum(VerificationStageStatus, name="verification_stage_status", native_enum=True),
        default=VerificationStageStatus.PENDING,
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="verification_stages")


class Certificate(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VerificationResultMixin, Base):
    """A certificate or achievement claim (section 4)."""

    __tablename__ = "certificates"

    candidate_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    issuer: Mapped[str] = mapped_column(String(200), nullable=False)
    issued_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    credential_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- Uploaded certificate file (optional; see `certificate_files.py`) ---
    #
    # The object key, never a URL: the bucket is private and the only read path
    # is a short-lived presigned URL minted per request, exactly as resumes
    # work. Storing a URL would either bake in an expiry or require a public
    # object.
    #
    # An uploaded file is **not** evidence. `verify_certificate_task` checks the
    # `credential_url` against the issuer's domain; a PDF the candidate uploaded
    # is a document they control and cannot corroborate itself, so it never
    # moves `verification_status`.
    file_object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, name="verification_status", native_enum=True),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    candidate_profile: Mapped["CandidateProfile"] = relationship(back_populates="certificates")  # noqa: F821


class Experience(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VerificationResultMixin, Base):
    """Self-reported internship / freelance / part-time work (section 5).

    `company_name` is free text, not an FK to `companies` — a student's past
    employer is not necessarily a GroundTruth customer (per §3's design note).

    `verification_status` was added after the fact (originally this table
    carried no verification state at all — the profile builder never queued
    it). There is no independent third-party source of truth for "worked at
    X" the way there is a GitHub API or a Codeforces handle, so this claim can
    only ever reach `FLAGGED` (self-reported, corroborated by weak internal
    signals) or stay `UNVERIFIED` — never `VERIFIED`. See
    `src/jobs/tasks/verification.py::verify_experience_task`.
    """

    __tablename__ = "experiences"

    candidate_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    employment_type: Mapped[EmploymentType] = mapped_column(
        SAEnum(EmploymentType, name="employment_type", native_enum=True), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    technologies: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, name="verification_status", native_enum=True),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    candidate_profile: Mapped["CandidateProfile"] = relationship(back_populates="experiences")  # noqa: F821
