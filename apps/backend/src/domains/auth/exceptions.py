"""Domain exceptions for the authentication module.

Raised by `service.py`, translated into consistent JSON error responses by
`src/core/error_handlers.py`. `status_code` + `code` let the frontend
branch on a stable machine-readable identifier instead of parsing prose.
"""

from __future__ import annotations


class AuthError(Exception):
    status_code: int = 400
    code: str = "AUTH_ERROR"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.__class__.__doc__ or "Authentication error"
        super().__init__(self.message)


class EmailAlreadyRegistered(AuthError):
    """An account with this email already exists."""

    status_code = 409
    code = "EMAIL_ALREADY_REGISTERED"


class InvalidCredentials(AuthError):
    """Invalid email or password."""

    status_code = 401
    code = "INVALID_CREDENTIALS"


class AccountLocked(AuthError):
    """Account temporarily locked due to repeated failed login attempts."""

    status_code = 423
    code = "ACCOUNT_LOCKED"


class AccountInactive(AuthError):
    """This account has been deactivated."""

    status_code = 403
    code = "ACCOUNT_INACTIVE"


class RoleMismatch(AuthError):
    """This account is registered under a different role."""

    status_code = 403
    code = "ROLE_MISMATCH"


class EmailNotVerified(AuthError):
    """Please verify your email before logging in."""

    status_code = 403
    code = "EMAIL_NOT_VERIFIED"


class InvalidOtp(AuthError):
    """Invalid or expired verification code."""

    status_code = 400
    code = "INVALID_OTP"


class OtpRequestTooSoon(AuthError):
    """Please wait before requesting another code."""

    status_code = 429
    code = "OTP_REQUEST_TOO_SOON"


class InvalidOrExpiredToken(AuthError):
    """This link is invalid or has expired."""

    status_code = 400
    code = "INVALID_OR_EXPIRED_TOKEN"


class CaptchaVerificationFailed(AuthError):
    """CAPTCHA verification failed. Please try again."""

    status_code = 400
    code = "CAPTCHA_FAILED"


class InvalidRefreshToken(AuthError):
    """Session expired. Please log in again."""

    status_code = 401
    code = "INVALID_REFRESH_TOKEN"


class CsrfValidationFailed(AuthError):
    """CSRF validation failed."""

    status_code = 403
    code = "CSRF_FAILED"


class OAuthNotConfigured(AuthError):
    """Google sign-in isn't configured yet."""

    status_code = 503
    code = "OAUTH_NOT_CONFIGURED"


class OAuthError(AuthError):
    """Google sign-in failed. Please try again."""

    status_code = 400
    code = "OAUTH_ERROR"
