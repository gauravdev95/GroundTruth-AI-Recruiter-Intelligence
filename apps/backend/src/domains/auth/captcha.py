"""Google reCAPTCHA v2 server-side verification."""

from __future__ import annotations

import httpx
import structlog

from src.config.config import get_captcha_settings, get_security_settings
from src.domains.auth.exceptions import CaptchaVerificationFailed

logger = structlog.get_logger(__name__)

_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


def verify_captcha(token: str, remote_ip: str | None = None) -> None:
    """Raises CaptchaVerificationFailed if the token is missing/invalid.

    In development, if no secret key is configured, verification is
    skipped so the module is testable without a Google account. This
    bypass never triggers when APP_ENV != "development".

    Uses a sync httpx.Client (not AsyncClient) to match this codebase's
    existing sync-endpoint/sync-SQLAlchemy convention (see main.py) —
    FastAPI runs sync `def` endpoints in a threadpool automatically.
    """
    captcha_settings = get_captcha_settings()
    security_settings = get_security_settings()

    if not captcha_settings.recaptcha_secret_key:
        if security_settings.app_env == "development":
            logger.warning("captcha_bypassed_dev_mode")
            return
        raise CaptchaVerificationFailed("CAPTCHA is not configured")

    payload = {"secret": captcha_settings.recaptcha_secret_key, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(_VERIFY_URL, data=payload)
            resp.raise_for_status()
            result = resp.json()
    except httpx.HTTPError as exc:
        logger.error("captcha_verification_request_failed", error=str(exc))
        raise CaptchaVerificationFailed() from exc

    if not result.get("success"):
        logger.info("captcha_verification_rejected", errors=result.get("error-codes"))
        raise CaptchaVerificationFailed()
