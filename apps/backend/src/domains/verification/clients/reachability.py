"""Generic URL-reachability check, shared by HackerRank handle verification
and certificate credential-URL verification.

Neither has a real API to check against: HackerRank has no public API at
all, and a certificate's issuing platform is arbitrary (Coursera, a
university, an internal LMS — anything a student can paste a URL for). Both
therefore fall back to the same honest, low-confidence check: is the URL
reachable, and does the response body corroborate the claim in any way this
module can check. This is why both checks can reach at most `FLAGGED`, never
`VERIFIED` — see `verification_status`'s docstring in
`domains/student/models.py`.
"""

from __future__ import annotations

import httpx
import structlog

from src.config.config import get_verification_settings
from src.domains.verification.clients.http import RateLimiter
from src.domains.verification.exceptions import VerificationServiceUnavailable

logger = structlog.get_logger(__name__)


def _limiter(name: str, max_requests: int) -> RateLimiter:
    return RateLimiter(name, max_requests=max_requests, window_seconds=60)


def check_reachable(url: str, *, rate_limit_name: str, max_requests_per_minute: int) -> tuple[bool, str]:
    """Returns `(reachable, body_snippet)`. Raises `VerificationServiceUnavailable`
    only on a genuine network failure — a 4xx/5xx response is a normal,
    informative outcome here (the URL exists but the resource doesn't), not
    an error worth retrying."""
    if not _limiter(rate_limit_name, max_requests_per_minute).acquire():
        raise VerificationServiceUnavailable(f"{rate_limit_name} verification rate limit reached; will retry")

    settings = get_verification_settings()
    try:
        with httpx.Client(timeout=settings.verification_http_timeout_seconds, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "GroundTruth-Verification/1.0"})
    except httpx.HTTPError as exc:
        raise VerificationServiceUnavailable(f"Could not reach {url}") from exc

    if response.status_code >= 500:
        raise VerificationServiceUnavailable(f"{url} returned {response.status_code}")

    body = response.text[:20_000] if response.status_code < 400 else ""
    return response.status_code < 400, body


def domain_of(url: str) -> str:
    from urllib.parse import urlparse

    netloc = urlparse(url).netloc.lower()
    return netloc.removeprefix("www.")
