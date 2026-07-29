"""Google OAuth 2.0 Authorization Code flow (server-side).

No `google-auth` SDK dependency — the flow only needs a handful of HTTP
calls, made with `httpx` (already a project dependency).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
import structlog

from src.config.config import get_google_oauth_settings, get_security_settings
from src.domains.auth.exceptions import OAuthError, OAuthNotConfigured
from src.domains.auth.models import UserRole

logger = structlog.get_logger(__name__)

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

_STATE_TYPE = "oauth_state"


class GoogleUserInfo:
    def __init__(self, *, email: str, email_verified: bool, full_name: str, google_id: str) -> None:
        self.email = email.strip().lower()
        self.email_verified = email_verified
        self.full_name = full_name
        self.google_id = google_id


def build_google_authorize_url(role: UserRole) -> str:
    oauth_settings = get_google_oauth_settings()
    if not oauth_settings.is_configured:
        raise OAuthNotConfigured()

    state = _encode_state(role)
    params = {
        "client_id": oauth_settings.google_client_id,
        "redirect_uri": oauth_settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


def decode_state_role(state: str) -> UserRole:
    settings = get_security_settings()
    try:
        payload = jwt.decode(state, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError as exc:
        raise OAuthError("Invalid or expired OAuth state") from exc
    if payload.get("type") != _STATE_TYPE:
        raise OAuthError("Invalid OAuth state")
    return UserRole(payload["role"])


def exchange_code_and_fetch_user(code: str) -> GoogleUserInfo:
    """Sync httpx.Client to match this codebase's sync-endpoint convention (see main.py)."""
    oauth_settings = get_google_oauth_settings()
    if not oauth_settings.is_configured:
        raise OAuthNotConfigured()

    with httpx.Client(timeout=10.0) as client:
        try:
            token_resp = client.post(
                _TOKEN_URL,
                data={
                    "client_id": oauth_settings.google_client_id,
                    "client_secret": oauth_settings.google_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": oauth_settings.google_oauth_redirect_uri,
                },
            )
            token_resp.raise_for_status()
            access_token = token_resp.json()["access_token"]

            userinfo_resp = client.get(
                _USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
            userinfo_resp.raise_for_status()
            info = userinfo_resp.json()
        except httpx.HTTPError as exc:
            logger.error("google_oauth_exchange_failed", error=str(exc))
            raise OAuthError() from exc

    if not info.get("email"):
        raise OAuthError("Google did not return an email address")

    return GoogleUserInfo(
        email=info["email"],
        email_verified=bool(info.get("email_verified", False)),
        full_name=info.get("name") or info.get("email"),
        google_id=info["sub"],
    )


def _encode_state(role: UserRole) -> str:
    settings = get_security_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "role": role.value,
        "type": _STATE_TYPE,
        "iat": now,
        "exp": now + timedelta(minutes=10),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
