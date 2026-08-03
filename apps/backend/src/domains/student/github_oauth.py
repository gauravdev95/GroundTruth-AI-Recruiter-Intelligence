"""GitHub OAuth 2.0 (Authorization Code flow, read scopes only).

Connects a candidate's **existing** GroundTruth account to their GitHub
identity — distinct from `domains/auth/oauth.py`, which authenticates a
visitor *into* the app via Google. This flow requires the caller to already
be a logged-in candidate; its `state` parameter is a short-lived signed JWT
carrying that candidate's id, mirroring `auth/oauth.py::_encode_state`'s
pattern exactly (same library, same expiry style) but scoped to a
`candidate_profile_id` instead of a signup `role`.

An OAuth-verified account is written straight to `VERIFIED` rather than going
through the async `verify_github_account` queue: the OAuth exchange itself
*is* stronger proof of ownership than anything `verify_github_account_task`
can check from a bare username (that task can only confirm the username
exists, not that the candidate controls it). Queueing it anyway would be
strictly redundant work for a weaker result.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.config import get_github_oauth_settings, get_security_settings
from src.core.crypto import encrypt_secret
from src.core.exceptions import AppError
from src.domains.auth.models import CandidateProfile
from src.domains.student.models import GithubAccount, VerificationStatus
from src.domains.verification.clients import github as github_client
from src.domains.verification.exceptions import ClaimNotFound, VerificationServiceUnavailable

logger = structlog.get_logger(__name__)

_STATE_TYPE = "github_oauth_state"


class GitHubOAuthNotConfigured(AppError):
    """GitHub OAuth isn't configured in this environment."""

    status_code = 503
    code = "GITHUB_OAUTH_NOT_CONFIGURED"


class GitHubOAuthError(AppError):
    """GitHub connection failed. Please try again."""

    status_code = 400
    code = "GITHUB_OAUTH_ERROR"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_connect_url(candidate_profile_id: uuid.UUID) -> str:
    settings = get_github_oauth_settings()
    if not settings.is_configured:
        raise GitHubOAuthNotConfigured()

    security_settings = get_security_settings()
    now = _utcnow()
    state = jwt.encode(
        {
            "candidate_profile_id": str(candidate_profile_id),
            "nonce": secrets.token_urlsafe(16),
            "type": _STATE_TYPE,
            "iat": now,
            "exp": now + timedelta(minutes=10),
        },
        security_settings.jwt_secret_key,
        algorithm=security_settings.jwt_algorithm,
    )
    return github_client.build_authorize_url(state=state)


def _decode_state(state: str) -> uuid.UUID:
    settings = get_security_settings()
    try:
        payload = jwt.decode(state, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError as exc:
        raise GitHubOAuthError("Invalid or expired GitHub connection request") from exc
    if payload.get("type") != _STATE_TYPE:
        raise GitHubOAuthError("Invalid GitHub connection request")
    return uuid.UUID(payload["candidate_profile_id"])


def handle_callback(db: Session, *, code: str, state: str) -> GithubAccount:
    """Exchanges `code`, resolves the GitHub identity, and upserts the
    candidate's `GithubAccount` row as `VERIFIED`.

    Raises `GitHubOAuthError`/`GitHubOAuthNotConfigured` (safe to show the
    candidate) or lets `VerificationServiceUnavailable` propagate for a
    genuine GitHub outage — the router maps that to the same generic
    `EXTERNAL_SERVICE_ERROR` envelope every other third-party failure uses.
    """
    settings = get_github_oauth_settings()
    if not settings.is_configured:
        raise GitHubOAuthNotConfigured()

    candidate_profile_id = _decode_state(state)
    profile = db.get(CandidateProfile, candidate_profile_id)
    if profile is None:
        raise GitHubOAuthError("Candidate profile not found")

    try:
        access_token, scopes = github_client.exchange_code_for_token(code)
        user = github_client.get_user_authenticated(access_token)
    except ClaimNotFound as exc:
        raise GitHubOAuthError(str(exc)) from exc
    # VerificationServiceUnavailable intentionally propagates uncaught.

    existing = db.execute(
        select(GithubAccount).where(
            GithubAccount.candidate_profile_id == profile.id, GithubAccount.deleted_at.is_(None)
        )
    ).scalar_one_or_none()

    if existing is not None and existing.github_username.casefold() != user["login"].casefold():
        # Same reconciliation rule `student/service.py::_reconcile_github_account`
        # uses for a manually-edited username: retire, don't mutate, so any
        # prior verification stays historically accurate.
        existing.deleted_at = _utcnow()
        existing = None

    account = existing or GithubAccount(
        candidate_profile_id=profile.id,
        github_username=user["login"],
        profile_url=user.get("html_url", f"https://github.com/{user['login']}"),
    )
    account.github_username = user["login"]
    account.profile_url = user.get("html_url", f"https://github.com/{user['login']}")
    account.github_user_id = user["id"]
    account.verification_status = VerificationStatus.VERIFIED
    account.verification_score = 100.0
    account.verification_source = "github_oauth"
    account.verification_payload = {
        "id": user["id"],
        "login": user["login"],
        "public_repos": user.get("public_repos"),
        "followers": user.get("followers"),
    }
    account.verified_at = _utcnow()
    account.access_token_encrypted = encrypt_secret(access_token)
    account.token_scopes = scopes
    account.oauth_connected_at = _utcnow()

    if existing is None:
        db.add(account)
    db.flush()
    db.commit()

    # OAuth connection can be the first evidence the "technical" section has
    # (a candidate might connect GitHub before ever saving section 2 by
    # hand) — recompute rather than leaving `profile_strength` stale until
    # the candidate happens to save some other section.
    from src.domains.student import service as student_service

    student_service.recompute_and_persist_strength(db, profile.id)

    logger.info("github_oauth_connected", candidate_profile_id=str(profile.id), github_login=user["login"])
    return account
