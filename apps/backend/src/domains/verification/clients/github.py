"""GitHub REST API client for account resolution, repository analysis, and
the OAuth token exchange.

The only module that speaks `httpx` to `api.github.com` — everything above
this (the OAuth flow, the `verify_github_account`/`verify_repository`
consumers) calls these functions and only ever sees `dict`/`list` responses
or the typed errors from `domains/verification/exceptions.py`.

Every read call is rate-limited and cached through `clients/http.py`; the
OAuth token exchange is neither (it is a one-time, non-idempotent POST).
"""

from __future__ import annotations

import base64
import json
from urllib.parse import urlencode, urlparse

import httpx
import structlog

from src.config.config import get_github_oauth_settings, get_verification_settings
from src.domains.verification.clients.http import RateLimiter, ResponseCache
from src.domains.verification.exceptions import (
    ClaimNotFound,
    VerificationRateLimited,
    VerificationServiceUnavailable,
    VerificationStatPending,
)

logger = structlog.get_logger(__name__)

_API_BASE = "https://api.github.com"
_AUTH_URL = "https://github.com/login/oauth/authorize"
_TOKEN_URL = "https://github.com/login/oauth/access_token"

_cache = ResponseCache("github", ttl_seconds=600)


def _limiter_for_settings() -> RateLimiter:
    # Built per-call rather than once at import time: `RateLimiter` itself is
    # stateless (state lives in Redis, keyed by `name`), and settings can
    # change between test runs via monkeypatched env vars.
    settings = get_verification_settings()
    return RateLimiter("github", max_requests=settings.github_rate_limit_per_minute, window_seconds=60)


def _headers(token: str | None) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    settings = get_verification_settings()
    bearer = token or settings.github_api_token
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    return headers


def _get(path: str, *, token: str | None = None, params: dict | None = None, use_cache: bool = True) -> dict | list:
    """GET a GitHub API path, rate-limited and (for anonymous/shared reads) cached.

    Caching is keyed on the path+params only, deliberately excluding the
    token — the response for a public resource does not depend on which
    token asked, and caching per-token would defeat the point of sharing one
    cache across every candidate's verification jobs.
    """
    cache_key = f"{path}?{urlencode(params or {})}"
    if use_cache:
        cached = _cache.get(cache_key)
        if cached is not None:
            return json.loads(cached)

    if not _limiter_for_settings().acquire():
        raise VerificationRateLimited("GitHub verification rate limit reached; will retry")

    try:
        with httpx.Client(timeout=get_verification_settings().verification_http_timeout_seconds) as client:
            response = client.get(f"{_API_BASE}{path}", headers=_headers(token), params=params)
    except httpx.HTTPError as exc:
        raise VerificationServiceUnavailable("Could not reach GitHub") from exc

    if response.status_code == 404:
        raise ClaimNotFound(f"GitHub resource not found: {path}")
    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        raise VerificationRateLimited("GitHub API rate limit exhausted")
    if response.status_code == 202:
        # GitHub returns 202 while it computes stats asynchronously (the
        # contributor-stats and commit-activity endpoints do this on a cache
        # miss). Transient in the usual case — the Celery task's retry/backoff
        # gives GitHub time to finish before the next attempt — but not always:
        # some repositories 202 forever and never produce the statistic, so
        # this raises the narrower `VerificationStatPending` to let callers
        # distinguish "not ready yet" from "GitHub is down". See that class.
        raise VerificationStatPending("GitHub is still computing this statistic")
    if response.status_code >= 500:
        raise VerificationServiceUnavailable(f"GitHub returned {response.status_code}")
    if response.status_code >= 400:
        raise VerificationServiceUnavailable(f"GitHub rejected the request ({response.status_code})")

    data = response.json()
    if use_cache:
        _cache.set(cache_key, json.dumps(data))
    return data


def get_user(username: str, *, token: str | None = None) -> dict:
    """Raises `ClaimNotFound` if the username does not exist."""
    result = _get(f"/users/{username}", token=token)
    assert isinstance(result, dict)
    return result


def get_user_authenticated(token: str) -> dict:
    """`GET /user` — the account the token itself belongs to. Used only by
    the OAuth callback, where the token *is* the identity claim; not cached
    (keyed on a secret would be a cache-poisoning risk, and every candidate's
    result differs anyway)."""
    result = _get("/user", token=token, use_cache=False)
    assert isinstance(result, dict)
    return result


def parse_repo_url(repo_url: str) -> tuple[str, str]:
    """`https://github.com/owner/repo(.git)` -> `("owner", "repo")`."""
    path = urlparse(repo_url).path.strip("/")
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        raise ClaimNotFound(f"Not a valid GitHub repository URL: {repo_url}")
    return parts[0], parts[1].removesuffix(".git")


def get_repo(owner: str, repo: str, *, token: str | None = None) -> dict:
    result = _get(f"/repos/{owner}/{repo}", token=token)
    assert isinstance(result, dict)
    return result


def get_contributor_stats(owner: str, repo: str, *, token: str | None = None) -> list[dict]:
    """Total commits per contributor. Raises `VerificationServiceUnavailable`
    (transient) while GitHub is still computing this for a repo it hasn't
    cached — the retry ladder is what actually resolves that."""
    result = _get(f"/repos/{owner}/{repo}/stats/contributors", token=token, use_cache=False)
    assert isinstance(result, list)
    return result


def get_repo_tree(owner: str, repo: str, branch: str, *, token: str | None = None) -> list[str]:
    """Every file path in the repo at `branch`, via one recursive tree call.

    GitHub truncates the response for very large repos (`truncated: true`);
    that is accepted here rather than paginated — the caller (manifest
    detection, test-directory detection) only needs a representative sample,
    not exhaustive coverage, and a truncated list undercounts rather than
    fabricates evidence.
    """
    result = _get(f"/repos/{owner}/{repo}/git/trees/{branch}", token=token, params={"recursive": "1"})
    assert isinstance(result, dict)
    return [entry["path"] for entry in result.get("tree", []) if entry.get("type") == "blob"]


def get_file_content(owner: str, repo: str, path: str, *, token: str | None = None) -> str | None:
    """Decoded text content of a file, or `None` if it doesn't exist or isn't text."""
    try:
        result = _get(f"/repos/{owner}/{repo}/contents/{path}", token=token)
    except ClaimNotFound:
        return None
    assert isinstance(result, dict)
    if result.get("encoding") != "base64" or "content" not in result:
        return None
    try:
        return base64.b64decode(result["content"]).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return None


def get_commit_activity(owner: str, repo: str, *, token: str | None = None) -> list[dict]:
    """Weekly commit counts for the last year. Same 202-while-computing behavior
    as `get_contributor_stats`."""
    result = _get(f"/repos/{owner}/{repo}/stats/commit_activity", token=token, use_cache=False)
    assert isinstance(result, list)
    return result


def list_user_repos(token: str) -> list[dict]:
    """The connected account's own repositories, for the repo-picker UI.
    Requires a real OAuth token (not the optional server-side PAT) — this
    call is always made on the candidate's behalf."""
    result = _get(
        "/user/repos",
        token=token,
        params={"per_page": 100, "sort": "updated", "affiliation": "owner,collaborator"},
        use_cache=False,
    )
    assert isinstance(result, list)
    return result


# --------------------------------------------------------------------------
# OAuth 2.0 (Authorization Code flow, read scopes only)
# --------------------------------------------------------------------------


def build_authorize_url(*, state: str) -> str:
    settings = get_github_oauth_settings()
    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": settings.github_oauth_redirect_uri,
        "scope": settings.github_oauth_scopes,
        "state": state,
        "allow_signup": "false",
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(code: str) -> tuple[str, str]:
    """Returns `(access_token, granted_scopes)`. Never cached or rate-limited
    against the shared limiter — this is a one-shot, non-idempotent exchange
    the candidate initiated, not a background poll."""
    settings = get_github_oauth_settings()
    try:
        with httpx.Client(timeout=get_verification_settings().verification_http_timeout_seconds) as client:
            response = client.post(
                _TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                    "redirect_uri": settings.github_oauth_redirect_uri,
                },
            )
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        logger.error("github_oauth_exchange_failed", error=str(exc))
        raise VerificationServiceUnavailable("Could not reach GitHub") from exc

    if "error" in body or "access_token" not in body:
        raise ClaimNotFound(body.get("error_description", "GitHub declined the authorization code"))

    return body["access_token"], body.get("scope", "")
