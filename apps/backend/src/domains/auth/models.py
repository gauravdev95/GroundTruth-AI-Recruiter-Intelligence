"""SQLAlchemy models for the authentication domain.

A single `users` table backs authentication for every role (candidate,
recruiter, admin). Role-specific data lives in separate profile tables,
never in a separate authentication table per role.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
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
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)

    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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
    college: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    degree: Mapped[DegreeType | None] = mapped_column(
        SAEnum(DegreeType, name="degree_type", native_enum=True), nullable=True, index=True
    )
    branch: Mapped[Branch | None] = mapped_column(
        SAEnum(Branch, name="branch", native_enum=True), nullable=True, index=True
    )
    graduation_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    target_role: Mapped[TargetRole | None] = mapped_column(
        SAEnum(TargetRole, name="target_role", native_enum=True), nullable=True, index=True
    )

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

    # --- Derived discoverability state (never client-supplied) ---
    profile_strength: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
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


class EmailVerificationToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Hashed 6-digit OTPs for email verification."""

    __tablename__ = "email_verification_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    otp_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class PasswordResetToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Hashed single-use tokens for the forgot-password link flow."""

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
