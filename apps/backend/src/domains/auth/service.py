"""Auth domain business logic — the only layer allowed to touch models directly.

`router.py` stays thin: parse request, call a service function, return the
response schema. All security-relevant decisions (lockout, token rotation,
verification, enumeration-safe messaging) live here so they're tested once
and reused by every endpoint.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.config import get_security_settings
from src.core.mail.service import send_password_reset_email, send_verification_otp_email
from src.domains.company.service import get_or_create_company
from src.domains.auth.exceptions import (
    AccountInactive,
    AccountLocked,
    EmailAlreadyRegistered,
    EmailNotVerified,
    InvalidCredentials,
    InvalidOrExpiredToken,
    InvalidOtp,
    InvalidRefreshToken,
    OtpRequestTooSoon,
    RoleMismatch,
)
from src.domains.auth.models import (
    CandidateProfile,
    EmailVerificationToken,
    PasswordResetToken,
    RecruiterProfile,
    RefreshToken,
    User,
    UserRole,
)
from src.domains.auth.oauth import GoogleUserInfo
from src.domains.auth.schemas import CandidateRegisterRequest, LoginRequest, RecruiterRegisterRequest
from src.domains.auth.security import (
    create_access_token,
    generate_opaque_token,
    generate_otp,
    hash_opaque_token,
    hash_otp,
    hash_password,
    verify_password,
)

logger = structlog.get_logger(__name__)

MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)
OTP_VALIDITY = timedelta(minutes=10)
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN = timedelta(seconds=60)
RESET_TOKEN_VALIDITY = timedelta(minutes=30)
SESSION_COOKIE_VALIDITY = timedelta(days=1)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


# --- Registration -------------------------------------------------------------


def register_candidate(db: Session, payload: CandidateRegisterRequest) -> tuple[User, str, int]:
    if _get_user_by_email(db, payload.email) is not None:
        raise EmailAlreadyRegistered()

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.CANDIDATE,
        full_name=payload.full_name,
    )
    db.add(user)
    db.flush()
    db.add(CandidateProfile(user_id=user.id, phone_number=payload.phone_number))
    db.commit()
    db.refresh(user)

    otp = _issue_otp(db, user)
    logger.info("candidate_registered", user_id=str(user.id))
    return user, otp, int(OTP_VALIDITY.total_seconds())


def register_recruiter(db: Session, payload: RecruiterRegisterRequest) -> tuple[User, str, int]:
    if _get_user_by_email(db, payload.company_email) is not None:
        raise EmailAlreadyRegistered()

    user = User(
        email=payload.company_email,
        password_hash=hash_password(payload.password),
        role=UserRole.RECRUITER,
        full_name=payload.full_name,
    )
    db.add(user)
    db.flush()
    company = get_or_create_company(db, name=payload.company_name, recruiter_email=payload.company_email)
    db.add(RecruiterProfile(user_id=user.id, company_name=payload.company_name, company_id=company.id))
    db.commit()
    db.refresh(user)

    otp = _issue_otp(db, user)
    logger.info("recruiter_registered", user_id=str(user.id), company_id=str(company.id))
    return user, otp, int(OTP_VALIDITY.total_seconds())


# --- Email verification ---------------------------------------------------------


def _issue_otp(db: Session, user: User) -> str:
    # Invalidate any outstanding OTPs so only the newest one is valid.
    stale = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.user_id == user.id, EmailVerificationToken.consumed_at.is_(None))
        .all()
    )
    for token in stale:
        token.consumed_at = _now()

    otp = generate_otp()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            otp_hash=hash_otp(otp),
            expires_at=_now() + OTP_VALIDITY,
        )
    )
    db.commit()

    send_verification_otp_email(
        to_email=user.email,
        full_name=user.full_name,
        otp=otp,
        expires_in_minutes=int(OTP_VALIDITY.total_seconds() // 60),
    )
    return otp


def resend_verification_otp(db: Session, email: str) -> int:
    user = _get_user_by_email(db, email)
    if user is None or user.is_email_verified:
        # Generic success — do not reveal whether the account exists or its state.
        return int(OTP_VALIDITY.total_seconds())

    latest = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.user_id == user.id)
        .order_by(EmailVerificationToken.created_at.desc())
        .first()
    )
    if latest is not None and _now() - latest.created_at < OTP_RESEND_COOLDOWN:
        raise OtpRequestTooSoon()

    _issue_otp(db, user)
    return int(OTP_VALIDITY.total_seconds())


def confirm_email_otp(db: Session, email: str, otp: str) -> None:
    user = _get_user_by_email(db, email)
    if user is None:
        raise InvalidOtp()

    token = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.consumed_at.is_(None),
            EmailVerificationToken.expires_at > _now(),
        )
        .order_by(EmailVerificationToken.created_at.desc())
        .first()
    )
    if token is None:
        raise InvalidOtp()

    if token.attempt_count >= OTP_MAX_ATTEMPTS:
        token.consumed_at = _now()
        db.commit()
        raise InvalidOtp("Too many attempts. Please request a new code.")

    if hash_otp(otp) != token.otp_hash:
        token.attempt_count += 1
        db.commit()
        raise InvalidOtp()

    token.consumed_at = _now()
    user.is_email_verified = True
    db.commit()
    logger.info("email_verified", user_id=str(user.id))


# --- Login / sessions -----------------------------------------------------------


def authenticate(db: Session, payload: LoginRequest) -> User:
    user = _get_user_by_email(db, payload.email)
    if user is None or user.password_hash is None:
        raise InvalidCredentials()

    if user.locked_until is not None and user.locked_until > _now():
        raise AccountLocked()

    if not verify_password(payload.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = _now() + LOCKOUT_DURATION
            logger.warning("account_locked", user_id=str(user.id))
        db.commit()
        raise InvalidCredentials()

    if payload.expected_role is not None and user.role != payload.expected_role:
        raise RoleMismatch(
            f"This account is registered as a {user.role.value.capitalize()}. "
            f"Please use {user.role.value.capitalize()} login."
        )

    if not user.is_active:
        raise AccountInactive()

    if not user.is_email_verified:
        raise EmailNotVerified()

    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    logger.info("login_success", user_id=str(user.id))
    return user


@dataclass
class IssuedSession:
    access_token: str
    access_expires_in: int
    raw_refresh_token: str
    refresh_expires_at: datetime
    remember_me: bool


def issue_session(
    db: Session, user: User, *, remember_me: bool, user_agent: str | None, ip_address: str | None
) -> IssuedSession:
    settings = get_security_settings()
    access_token = create_access_token(user_id=user.id, role=user.role.value)

    raw_refresh = generate_opaque_token()
    expires_at = (
        _now() + timedelta(days=settings.jwt_refresh_token_expire_days)
        if remember_me
        else _now() + SESSION_COOKIE_VALIDITY
    )
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_opaque_token(raw_refresh),
            user_agent=user_agent,
            ip_address=ip_address,
            remember_me=remember_me,
            expires_at=expires_at,
        )
    )
    db.commit()

    return IssuedSession(
        access_token=access_token,
        access_expires_in=settings.jwt_access_token_expire_minutes * 60,
        raw_refresh_token=raw_refresh,
        refresh_expires_at=expires_at,
        remember_me=remember_me,
    )


def refresh_session(
    db: Session, raw_refresh_token: str, *, user_agent: str | None, ip_address: str | None
) -> tuple[User, IssuedSession]:
    token_hash = hash_opaque_token(raw_refresh_token)
    existing = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > _now(),
        )
        .first()
    )
    if existing is None:
        raise InvalidRefreshToken()

    user = db.get(User, existing.user_id)
    if user is None or not user.is_active:
        raise InvalidRefreshToken()

    # Rotate: revoke the presented token, issue a brand new one.
    existing.revoked_at = _now()
    db.commit()

    session = issue_session(
        db, user, remember_me=existing.remember_me, user_agent=user_agent, ip_address=ip_address
    )
    return user, session


def revoke_refresh_token(db: Session, raw_refresh_token: str) -> None:
    token_hash = hash_opaque_token(raw_refresh_token)
    existing = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if existing is not None and existing.revoked_at is None:
        existing.revoked_at = _now()
        db.commit()


def revoke_all_sessions_for_user(db: Session, user_id: uuid.UUID) -> None:
    tokens = (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .all()
    )
    for token in tokens:
        token.revoked_at = _now()
    db.commit()


# --- Password reset --------------------------------------------------------------


def request_password_reset(db: Session, email: str) -> str | None:
    """Returns the raw reset token only for logging/testing; callers must not leak it to the response."""
    user = _get_user_by_email(db, email)
    if user is None or user.password_hash is None:
        return None

    raw_token = generate_opaque_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_opaque_token(raw_token),
            expires_at=_now() + RESET_TOKEN_VALIDITY,
        )
    )
    db.commit()

    settings = get_security_settings()
    reset_url = f"{settings.frontend_base_url}/reset-password?token={raw_token}"
    send_password_reset_email(
        to_email=user.email,
        full_name=user.full_name,
        reset_url=reset_url,
        expires_in_minutes=int(RESET_TOKEN_VALIDITY.total_seconds() // 60),
    )
    return raw_token


def reset_password(db: Session, raw_token: str, new_password: str) -> None:
    token_hash = hash_opaque_token(raw_token)
    token = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.consumed_at.is_(None),
            PasswordResetToken.expires_at > _now(),
        )
        .first()
    )
    if token is None:
        raise InvalidOrExpiredToken()

    user = db.get(User, token.user_id)
    if user is None:
        raise InvalidOrExpiredToken()

    user.password_hash = hash_password(new_password)
    token.consumed_at = _now()
    db.commit()

    revoke_all_sessions_for_user(db, user.id)
    logger.info("password_reset", user_id=str(user.id))


# --- Google OAuth ------------------------------------------------------------------


def get_or_create_google_user(db: Session, info: GoogleUserInfo, role: UserRole) -> User:
    user = db.execute(select(User).where(User.google_id == info.google_id)).scalar_one_or_none()
    if user is not None:
        return user

    user = _get_user_by_email(db, info.email)
    if user is not None:
        # Link the Google identity to the existing local account.
        user.google_id = info.google_id
        if info.email_verified:
            user.is_email_verified = True
        db.commit()
        db.refresh(user)
        return user

    user = User(
        email=info.email,
        password_hash=None,
        role=role,
        full_name=info.full_name,
        is_email_verified=info.email_verified,
        google_id=info.google_id,
    )
    db.add(user)
    db.flush()
    if role == UserRole.CANDIDATE:
        db.add(CandidateProfile(user_id=user.id, phone_number=""))
    else:
        db.add(RecruiterProfile(user_id=user.id, company_name=info.full_name))
    db.commit()
    db.refresh(user)
    logger.info("google_user_created", user_id=str(user.id), role=role.value)
    return user
