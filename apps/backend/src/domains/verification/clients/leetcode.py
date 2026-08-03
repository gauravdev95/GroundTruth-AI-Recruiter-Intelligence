"""LeetCode client.

LeetCode has no official public API. This uses the `matchedUser` query
against LeetCode's own GraphQL endpoint (`leetcode.com/graphql`) — undocumented,
but the same endpoint LeetCode's own site calls to render a public profile,
requires no authentication, and is widely relied on by open-source stat
trackers. It is treated as **lower-confidence than Codeforces** for exactly
that reason: an undocumented endpoint can change shape without notice. If the
response doesn't parse the way this client expects, that is raised as a
transient failure (see module docstring in `exceptions.py`) rather than
silently downgraded to a heuristic — a schema change should surface as
"couldn't verify" (`UNVERIFIED`), not as a false pass.
"""

from __future__ import annotations

import json

import httpx
import structlog

from src.config.config import get_verification_settings
from src.domains.verification.clients.http import RateLimiter, ResponseCache
from src.domains.verification.exceptions import ClaimNotFound, VerificationServiceUnavailable

logger = structlog.get_logger(__name__)

_GRAPHQL_URL = "https://leetcode.com/graphql"
_cache = ResponseCache("leetcode", ttl_seconds=900)

_QUERY = """
query userProfile($username: String!) {
  matchedUser(username: $username) {
    username
    submitStats {
      acSubmissionNum {
        difficulty
        count
      }
    }
    profile {
      ranking
      reputation
    }
  }
}
"""


def _limiter() -> RateLimiter:
    settings = get_verification_settings()
    return RateLimiter("leetcode", max_requests=settings.leetcode_rate_limit_per_minute, window_seconds=60)


def get_user_stats(handle: str) -> dict:
    """Raises `ClaimNotFound` if the handle does not exist, or
    `VerificationServiceUnavailable` on a network failure or a response shape
    this client no longer understands."""
    cache_key = f"matchedUser:{handle}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return json.loads(cached)

    if not _limiter().acquire():
        raise VerificationServiceUnavailable("LeetCode verification rate limit reached; will retry")

    try:
        with httpx.Client(timeout=get_verification_settings().verification_http_timeout_seconds) as client:
            response = client.post(
                _GRAPHQL_URL,
                json={"query": _QUERY, "variables": {"username": handle}},
                headers={"Content-Type": "application/json", "Referer": f"https://leetcode.com/{handle}/"},
            )
    except httpx.HTTPError as exc:
        raise VerificationServiceUnavailable("Could not reach LeetCode") from exc

    if response.status_code >= 500:
        raise VerificationServiceUnavailable(f"LeetCode returned {response.status_code}")
    if response.status_code >= 400:
        raise VerificationServiceUnavailable(f"LeetCode rejected the request ({response.status_code})")

    try:
        body = response.json()
        matched_user = body["data"]["matchedUser"]
    except (KeyError, TypeError, ValueError) as exc:
        raise VerificationServiceUnavailable("Unexpected response shape from LeetCode") from exc

    if matched_user is None:
        raise ClaimNotFound(f"LeetCode handle not found: {handle}")

    _cache.set(cache_key, json.dumps(matched_user))
    return matched_user


def total_solved(stats: dict) -> int:
    for entry in (stats.get("submitStats") or {}).get("acSubmissionNum") or []:
        if entry.get("difficulty") == "All":
            return int(entry.get("count", 0))
    return 0
