"""SQLAlchemy models for the authentication domain.

A single `users` table backs authentication for every role (candidate,
recruiter, admin). Role-specific data lives in separate profile tables,
never in a separate authentication table per role.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base
from src.shared.db_mixins import TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(str, enum.Enum):
    CANDIDATE = "candidate"
    RECRUITER = "recruiter"
    ADMIN = "admin"


class DegreeType(str, enum.Enum):
    """Controlled vocabulary so recruiters can filter on degree exactly."""

    BTECH = "btech"
    BE = "be"
    BSC = "bsc"
    BCA = "bca"
    MTECH = "mtech"
    MSC = "msc"
    MCA = "mca"
    MBA = "mba"
    PHD = "phd"
    OTHER = "other"


class Branch(str, enum.Enum):
    """Controlled vocabulary for academic branch — kept filterable, not free text."""

    CSE = "cse"
    IT = "it"
    ECE = "ece"
    EEE = "eee"
    MECHANICAL = "mechanical"
    CIVIL = "civil"
    CHEMICAL = "chemical"
    AIML = "aiml"
    DATA_SCIENCE = "data_science"
    OTHER = "other"


class TargetRole(str, enum.Enum):
    """Controlled vocabulary for the role a candidate is targeting."""

    BACKEND = "backend"
    FRONTEND = "frontend"
    FULLSTACK = "fullstack"
    MOBILE = "mobile"
    DATA_ENGINEER = "data_engineer"
    DATA_SCIENTIST = "data_scientist"
    ML_ENGINEER = "ml_engineer"
    DEVOPS = "devops"
    QA = "qa"
    SECURITY = "security"
    OTHER = "other"


class OnboardingChoice(str, enum.Enum):
    """How a student answered the one-time "Upload Resume vs. Build Manually"
    fork. There is no `SKIPPED`: the fork has no dismiss action, because both
    answers lead somewhere useful and neither is a commitment — a student who
    picks `RESUME_UPLOAD` and abandons the upload still lands in the builder."""

    RESUME_UPLOAD = "resume_upload"
    MANUAL_ENTRY = "manual_entry"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The single authentication identity shared by every role."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", native_enum=True),
        nullable=False,
    )
    # Nullable since student signup became email + password only. A candidate
    # supplies their name in the first onboarding section; a recruiter still
    # supplies it at registration, and Google OAuth carries it from the
    # provider — so in practice this is NULL only for a student between
    # signup and their first section save.
    #
    # NULL rather than "": those are different facts. "" would assert the
    # student told us their name is empty, and this column is read to address
    # them by name in email.
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    @property
    def display_name(self) -> str:
        """A name safe to address this user by, in any context.

        Every greeting — email templates, the dashboard header — reads this
        rather than `full_name`, so a student who has not reached the first
        onboarding section still gets a coherent "Hi there" instead of
        "Hi None".

        Deliberately does NOT derive a name from the email local part.
        Turning `priya.raghunathan@…` into "Priya Raghunathan" is a guess
        presented as fact, and on a platform whose entire proposition is that
        it never states more than it can support, inventing a person's name is
        the worst possible place to start. "there" is honest and reads
        naturally in every sentence these templates build.
        """
        return self.full_name or "there"

    # There is no `is_email_verified`. Signup creates a usable account with no
    # verification step, so nothing in this system ever establishes that a
    # registrant controls their address — see the note above
    # `service.register_candidate`. The column was dropped rather than left
    # permanently `False`, because a stored flag named "verified" that no code
    # path can ever set is a claim the product cannot support.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    candidate_profile: Mapped["CandidateProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    recruiter_profile: Mapped["RecruiterProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class CandidateProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Candidate-specific profile data. Auth fields stay on User.

    Every profile-builder field is nullable: the builder is explicitly a
    multi-sitting flow, so a half-filled profile is a valid persisted state.
    Completeness is expressed by `profile_strength`/`is_discoverable`, both
    of which are **server-computed only** — see
    `src/domains/student/completeness.py`. No request schema exposes them.
    """

    __tablename__ = "candidate_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)

    # --- Section 1: Basic Information ---
    headline: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Free-text self-summary. Deliberately **not** part of
    # `completeness._BASIC_FIELDS`: that tuple's length divides BASIC_POINTS
    # exactly (35 / 7 = 5), and adding an eighth field would make the section
    # unable to reach its own maximum, silently capping every profile below
    # 100. Folding `about` into scoring is a scoring change, not a field
    # addition, and is tracked separately.
    #
    # It does feed the profile embedding, so it affects matching from the day
    # it is filled in even while contributing zero strength points.
    about: Mapped[str | None] = mapped_column(Text, nullable=True)
    college: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    degree: Mapped[DegreeType | None] = mapped_column(
        SAEnum(DegreeType, name="degree_type", native_enum=True), nullable=True, index=True
    )
    branch: Mapped[Branch | None] = mapped_column(
        SAEnum(Branch, name="branch", native_enum=True), nullable=True, index=True
    )
    graduation_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    # The student's **primary** target role, and always `target_roles[0]`.
    #
    # Kept as a scalar native enum beside the array below rather than replaced
    # by it: this column is indexed and is what `matching/`,
    # `pipeline/evidence.py` and the recruiter evidence card filter on. Both
    # are written in one statement by the only writer
    # (`student/service.py::replace_basic_info`), so they cannot drift.
    target_role: Mapped[TargetRole | None] = mapped_column(
        SAEnum(TargetRole, name="target_role", native_enum=True), nullable=True, index=True
    )
    # The full set the student picked at onboarding — one to three roles, in
    # their stated order of preference. `String(40)` elements rather than an
    # array of the native enum, matching how `Project.technologies` already
    # stores a controlled list; the vocabulary is enforced by `TargetRole` on
    # the request schema, and the scalar mirror above keeps a database-level
    # check on the primary value.
    #
    # NULL, not `[]`, for a profile that has not saved section 1 yet — the same
    # "not answered" representation every other field in this section uses.
    target_roles: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(40)), nullable=True
    )

    # --- Profile photo ---
    #
    # The object key in the configured bucket, or NULL for no photo. The photo
    # is optional and earns no completeness points: it is how a student appears
    # to a recruiter, and nothing about a face is evidence of anything, so
    # scoring it would pay strength for a claim the platform cannot check.
    #
    # Content type is stored because it is **sniffed from the file's leading
    # bytes** at upload (`student/profile_photos.py`) and is what the presigned
    # URL later serves the object as. Storing the request's own `Content-Type`
    # would be storing a client claim.
    profile_photo_object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    profile_photo_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # --- Onboarding ---
    # Which lane the student picked at the "Upload Resume vs. Build Manually"
    # fork. NULL means they have not answered it yet, which is what makes the
    # fork show exactly once: the answer is durable server state, so it
    # survives a new device or a cleared browser, and picking "build manually"
    # counts as answered even though it writes no profile data yet. Recording
    # *which* lane rather than a bare boolean costs nothing and says why the
    # fork is done.
    onboarding_choice: Mapped[OnboardingChoice | None] = mapped_column(
        SAEnum(OnboardingChoice, name="onboarding_choice", native_enum=True), nullable=True
    )
    # When the student pressed "Submit Profile" on the final review step.
    # NULL means onboarding is unfinished, and it is the **only** thing that
    # opens the dashboard (`student/setup_state.py::SetupState.is_submitted`,
    # `RequireProfileSetup` on the client).
    #
    # A timestamp rather than a boolean, and deliberately separate from
    # `profile_strength`/`meets_section_requirements`: those are *derived* from
    # rows and move on their own every time a worker writes a verification
    # result, so a gate keyed on them can silently re-open or re-close under a
    # student who did nothing. This is an explicit act with a time, which is
    # what the review step promises.
    onboarding_submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # When the student ticked the consent box on the review step, agreeing to
    # repository analysis and interview-question generation. Required by DPDP,
    # and `submit_onboarding` refuses to stamp `onboarding_submitted_at`
    # without it.
    #
    # A separate column rather than an assumption baked into the submission
    # timestamp: the two answer different questions ("did they finish signing
    # up" vs "did they agree to be analysed"), and a consent record that is
    # merely inferred from another event is not a consent record. Profiles that
    # submitted before this column existed hold NULL and are never backfilled —
    # see migration `b9e2f45c81a7` for why a convenient backfill here would be
    # a fabricated consent log.
    onboarding_consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # When the "verification finished" email was sent. Persisted rather than
    # inferred because that email must arrive exactly once: verification
    # settles asynchronously and `_finish` runs after *every* individual claim,
    # so without a durable marker a candidate with six claims would get six
    # copies of the same summary.
    verification_summary_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Derived discoverability state (never client-supplied) ---
    #
    # Three separate numbers rather than one, because they answer three
    # different questions and collapsing them would make each unanswerable:
    #
    #   profile_strength — how *complete* is the profile? Filled, not verified.
    #                      Cannot fall because a worker rejected a claim.
    #   evidence_score   — how strong is the *verified* evidence behind it?
    #                      This one can fall, and should.
    #   interview_score  — how did they do in the AI interview?
    #
    # `completeness.py` is the single writer of all three.
    profile_strength: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Mean verification confidence across the candidate's verified claims,
    # 0-100. Distinct from `profile_strength` on purpose: a candidate can have
    # a complete profile made of weak evidence, or a sparse profile made of
    # very strong evidence, and one number cannot express both.
    evidence_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Aggregate across the candidate's completed interviews, 0-100. NULL means
    # "has not completed one", which is not the same as scoring zero — the
    # discoverability gate reads presence, and the match score reads value.
    interview_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_discoverable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    user: Mapped["User"] = relationship(back_populates="candidate_profile")

    github_accounts: Mapped[list["GithubAccount"]] = relationship(  # noqa: F821
        back_populates="candidate_profile", cascade="all, delete-orphan"
    )
    coding_platform_accounts: Mapped[list["CodingPlatformAccount"]] = relationship(  # noqa: F821
        back_populates="candidate_profile", cascade="all, delete-orphan"
    )
    projects: Mapped[list["Project"]] = relationship(  # noqa: F821
        back_populates="candidate_profile", cascade="all, delete-orphan"
    )
    certificates: Mapped[list["Certificate"]] = relationship(  # noqa: F821
        back_populates="candidate_profile", cascade="all, delete-orphan"
    )
    experiences: Mapped[list["Experience"]] = relationship(  # noqa: F821
        back_populates="candidate_profile", cascade="all, delete-orphan"
    )


class RecruiterProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Recruiter-specific profile data. Auth fields stay on User."""

    __tablename__ = "recruiter_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )

    user: Mapped["User"] = relationship(back_populates="recruiter_profile")
    company: Mapped["Company | None"] = relationship(back_populates="recruiter_profiles")  # noqa: F821


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Opaque refresh tokens (hashed at rest) backing sessions and Remember Me."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remember_me: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PasswordResetToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Hashed single-use tokens for the forgot-password link flow."""

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
