"""Authentication API routes.

Thin by design: parse request -> call `service` -> return a schema.
Endpoints stay plain `def` (not `async def`) to match this codebase's
existing sync-SQLAlchemy convention (see `src/main.py`) — FastAPI runs
sync endpoints in a threadpool automatically, so this doesn't block the
event loop despite `captcha`/`oauth` making outbound HTTP calls.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.config.config import get_security_settings
from src.db.database import get_db
from src.domains.auth import service
from src.domains.auth.captcha import verify_captcha
from src.domains.auth.dependencies import CSRF_COOKIE_NAME, get_current_user, verify_csrf
from src.domains.auth.exceptions import InvalidRefreshToken, OAuthError
from src.domains.auth.models import User, UserRole
from src.domains.auth.oauth import build_google_authorize_url, decode_state_role, exchange_code_and_fetch_user
from src.domains.auth.rate_limit import limiter
from src.domains.auth.schemas import (
    AccessTokenResponse,
    CandidateRegisterRequest,
    ForgotPasswordRequest,
    GenericMessageResponse,
    LoginRequest,
    OtpExpiryResponse,
    RecruiterRegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    UserResponse,
    VerifyEmailConfirmRequest,
    VerifyEmailResendRequest,
)
from src.domains.auth.security import generate_opaque_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"
COOKIE_PATH = "/api/v1/auth"
# The CSRF cookie must be readable via document.cookie from every frontend
# route (/login/candidate, /reset-password, ...), not just API paths — a
# cookie's Path also gates document.cookie visibility on the page that
# reads it, not only which requests it's attached to. Path=/api/v1/auth
# would work for what the *server* receives but make the cookie invisible
# to JS on any page whose URL isn't under /api/v1/auth.
CSRF_COOKIE_PATH = "/"


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_session_cookies(
    response: Response, *, refresh_token: str, remember_me: bool, expires_at: datetime
) -> None:
    settings = get_security_settings()
    max_age = int((expires_at - datetime.now(timezone.utc)).total_seconds()) if remember_me else None

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=COOKIE_PATH,
        max_age=max_age,
    )
    # Non-httpOnly by design: the frontend reads this and echoes it back in a
    # header (double-submit CSRF pattern) for cookie-authenticated requests.
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=generate_opaque_token(),
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path=CSRF_COOKIE_PATH,
        max_age=max_age,
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME, path=COOKIE_PATH)
    response.delete_cookie(CSRF_COOKIE_NAME, path=CSRF_COOKIE_PATH)


@router.post("/candidate/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
def candidate_register(
    request: Request, payload: CandidateRegisterRequest, db: Session = Depends(get_db)
) -> RegisterResponse:
    verify_captcha(payload.captcha_token, _client_ip(request))
    user, _otp, expires_in = service.register_candidate(db, payload)
    return RegisterResponse(
        message="Registration successful. Check your email for a verification code.",
        email=user.email,
        otp_expires_in_seconds=expires_in,
    )


@router.post("/recruiter/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
def recruiter_register(
    request: Request, payload: RecruiterRegisterRequest, db: Session = Depends(get_db)
) -> RegisterResponse:
    verify_captcha(payload.captcha_token, _client_ip(request))
    user, _otp, expires_in = service.register_recruiter(db, payload)
    return RegisterResponse(
        message="Registration successful. Check your email for a verification code.",
        email=user.email,
        otp_expires_in_seconds=expires_in,
    )


@router.post("/login", response_model=AccessTokenResponse)
@limiter.limit("5/minute")
def login(
    request: Request, response: Response, payload: LoginRequest, db: Session = Depends(get_db)
) -> AccessTokenResponse:
    verify_captcha(payload.captcha_token, _client_ip(request))
    user = service.authenticate(db, payload)
    session = service.issue_session(
        db,
        user,
        remember_me=payload.remember_me,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )
    _set_session_cookies(
        response,
        refresh_token=session.raw_refresh_token,
        remember_me=session.remember_me,
        expires_at=session.refresh_expires_at,
    )
    return AccessTokenResponse(
        access_token=session.access_token,
        expires_in=session.access_expires_in,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
@limiter.limit("30/minute")
def refresh(
    request: Request, response: Response, db: Session = Depends(get_db), _csrf: None = Depends(verify_csrf)
) -> AccessTokenResponse:
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_refresh:
        raise InvalidRefreshToken()

    user, session = service.refresh_session(
        db, raw_refresh, user_agent=request.headers.get("user-agent"), ip_address=_client_ip(request)
    )
    _set_session_cookies(
        response,
        refresh_token=session.raw_refresh_token,
        remember_me=session.remember_me,
        expires_at=session.refresh_expires_at,
    )
    return AccessTokenResponse(
        access_token=session.access_token,
        expires_in=session.access_expires_in,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout", response_model=GenericMessageResponse)
@limiter.limit("10/minute")
def logout(
    request: Request, response: Response, db: Session = Depends(get_db), _csrf: None = Depends(verify_csrf)
) -> GenericMessageResponse:
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_refresh:
        service.revoke_refresh_token(db, raw_refresh)
    _clear_session_cookies(response)
    return GenericMessageResponse(message="Logged out successfully.")


@router.post("/verify-email/confirm", response_model=GenericMessageResponse)
@limiter.limit("10/minute")
def verify_email_confirm(
    request: Request, payload: VerifyEmailConfirmRequest, db: Session = Depends(get_db)
) -> GenericMessageResponse:
    service.confirm_email_otp(db, payload.email, payload.otp)
    return GenericMessageResponse(message="Email verified successfully.")


@router.post("/verify-email/resend", response_model=OtpExpiryResponse)
@limiter.limit("5/hour")
def verify_email_resend(
    request: Request, payload: VerifyEmailResendRequest, db: Session = Depends(get_db)
) -> OtpExpiryResponse:
    expires_in = service.resend_verification_otp(db, payload.email)
    return OtpExpiryResponse(
        message="If an account exists and is unverified, a new code has been sent.",
        otp_expires_in_seconds=expires_in,
    )


@router.post("/forgot-password", response_model=GenericMessageResponse)
@limiter.limit("3/minute")
def forgot_password(
    request: Request, payload: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> GenericMessageResponse:
    service.request_password_reset(db, payload.email)
    return GenericMessageResponse(message="If an account with that email exists, a reset link has been sent.")


@router.post("/reset-password", response_model=GenericMessageResponse)
@limiter.limit("5/minute")
def reset_password_endpoint(
    request: Request, payload: ResetPasswordRequest, db: Session = Depends(get_db)
) -> GenericMessageResponse:
    service.reset_password(db, payload.token, payload.new_password)
    return GenericMessageResponse(message="Password reset successfully. Please log in.")


@router.get("/google/login")
@limiter.limit("15/minute")
def google_login(request: Request, role: UserRole) -> RedirectResponse:
    url = build_google_authorize_url(role)
    return RedirectResponse(url)


@router.get("/google/callback")
@limiter.limit("15/minute")
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = get_security_settings()

    if error or not code or not state:
        return RedirectResponse(f"{settings.frontend_base_url}/auth/callback?error=oauth_failed")

    try:
        role = decode_state_role(state)
        info = exchange_code_and_fetch_user(code)
        user = service.get_or_create_google_user(db, info, role)
        session = service.issue_session(
            db,
            user,
            remember_me=True,
            user_agent=request.headers.get("user-agent"),
            ip_address=_client_ip(request),
        )
    except OAuthError:
        return RedirectResponse(f"{settings.frontend_base_url}/auth/callback?error=oauth_failed")

    redirect = RedirectResponse(f"{settings.frontend_base_url}/auth/callback?success=true")
    _set_session_cookies(
        redirect,
        refresh_token=session.raw_refresh_token,
        remember_me=True,
        expires_at=session.refresh_expires_at,
    )
    return redirect


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)
