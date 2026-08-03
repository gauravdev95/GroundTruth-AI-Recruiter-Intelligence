"""Codeforces public API client.

Codeforces is the one competitive-programming platform GroundTruth supports
with a genuine, documented, unauthenticated public API — `leetcode.py` and
`hackerrank.py` document why LeetCode and HackerRank cannot reach the same
confidence level.
"""

from __future__ import annotations

import json

import httpx
import structlog

from src.config.config import get_verification_settings
from src.domains.verification.clients.http import RateLimiter, ResponseCache
from src.domains.verification.exceptions import ClaimNotFound, VerificationServiceUnavailable

logger = structlog.get_logger(__name__)

_API_BASE = "https://codeforces.com/api"
_cache = ResponseCache("codeforces", ttl_seconds=900)


def _limiter() -> RateLimiter:
    settings = get_verification_settings()
    return RateLimiter("codeforces", max_requests=settings.codeforces_rate_limit_per_minute, window_seconds=60)


def _get(method: str, params: dict) -> dict:
    from urllib.parse import urlencode

    cache_key = f"{method}?{urlencode(params)}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return json.loads(cached)

    if not _limiter().acquire():
        raise VerificationServiceUnavailable("Codeforces verification rate limit reached; will retry")

    try:
        with httpx.Client(timeout=get_verification_settings().verification_http_timeout_seconds) as client:
            response = client.get(f"{_API_BASE}/{method}", params=params)
    except httpx.HTTPError as exc:
        raise VerificationServiceUnavailable("Could not reach Codeforces") from exc

    if response.status_code >= 500:
        raise VerificationServiceUnavailable(f"Codeforces returned {response.status_code}")

    body = response.json()
    if body.get("status") != "OK":
        comment = body.get("comment", "")
        if "not found" in comment.casefold():
            raise ClaimNotFound(f"Codeforces handle not found: {comment}")
        raise VerificationServiceUnavailable(f"Codeforces API error: {comment}")

    _cache.set(cache_key, json.dumps(body))
    return body


def get_user_info(handle: str) -> dict:
    """Raises `ClaimNotFound` if the handle does not exist."""
    body = _get("user.info", {"handles": handle})
    result = body.get("result") or []
    if not result:
        raise ClaimNotFound(f"Codeforces handle not found: {handle}")
    return result[0]


def count_solved_problems(handle: str, *, max_submissions: int = 10_000) -> int:
    """Distinct problems with an `OK` verdict across the handle's submission
    history. One call, capped at `max_submissions` — enough for the vast
    majority of accounts without risking an unbounded response."""
    body = _get("user.status", {"handle": handle, "from": 1, "count": max_submissions})
    solved: set[str] = set()
    for submission in body.get("result", []):
        if submission.get("verdict") != "OK":
            continue
        problem = submission.get("problem", {})
        key = f"{problem.get('contestId')}-{problem.get('index')}"
        solved.add(key)
    return len(solved)
