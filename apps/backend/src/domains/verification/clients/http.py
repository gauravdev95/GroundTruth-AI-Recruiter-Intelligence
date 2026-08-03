"""Shared rate limiting + response caching for every third-party verification
call (GitHub, Codeforces, LeetCode, certificate-URL checks).

Backed by the same Redis instance Celery already requires
(`CELERY_RESULT_BACKEND` — reused rather than adding a second required piece
of infrastructure just for this). Both the limiter and the cache degrade to
"do nothing" if Redis is unreachable: a verification check is best-effort
background work, and a Redis blip should slow it down, not crash the worker.
Client code always calls through `RateLimiter.acquire()` before a request and
`ResponseCache.get`/`set` around it — neither raises on a backend outage.
"""

from __future__ import annotations

import hashlib
import time
from functools import lru_cache

import redis
import structlog

from src.config.config import get_celery_settings

logger = structlog.get_logger(__name__)


@lru_cache
def _redis_client() -> redis.Redis | None:
    settings = get_celery_settings()
    try:
        client = redis.Redis.from_url(
            settings.celery_result_backend, socket_connect_timeout=2, socket_timeout=2
        )
        client.ping()
        return client
    except redis.RedisError as exc:
        logger.warning("verification_redis_unavailable", error=str(exc))
        return None


class RateLimiter:
    """Fixed-window request limiter, one window counter per `(name, window)`.

    A fixed window (not a sliding one or a token bucket) is enough here: these
    are background jobs with no user waiting on a specific millisecond, so the
    "up to 2x burst at a window boundary" imprecision fixed windows have is an
    acceptable trade for a single `INCR`+`EXPIRE` instead of a sorted-set.
    """

    def __init__(self, name: str, *, max_requests: int, window_seconds: int) -> None:
        self._name = name
        self._max_requests = max_requests
        self._window_seconds = window_seconds

    def acquire(self) -> bool:
        """Returns True if the call may proceed. Never raises."""
        client = _redis_client()
        if client is None:
            return True  # no limiter available — fail open, not closed

        window = int(time.time()) // self._window_seconds
        key = f"verification:ratelimit:{self._name}:{window}"
        try:
            count = client.incr(key)
            if count == 1:
                client.expire(key, self._window_seconds)
            return count <= self._max_requests
        except redis.RedisError as exc:
            logger.warning("verification_ratelimit_error", name=self._name, error=str(exc))
            return True


class ResponseCache:
    """TTL cache for third-party API responses, keyed by an arbitrary string
    the caller builds (typically the request URL). Values are short strings
    (JSON), never binary payloads."""

    def __init__(self, namespace: str, *, ttl_seconds: int) -> None:
        self._namespace = namespace
        self._ttl_seconds = ttl_seconds

    def _key(self, key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"verification:cache:{self._namespace}:{digest}"

    def get(self, key: str) -> str | None:
        client = _redis_client()
        if client is None:
            return None
        try:
            value = client.get(self._key(key))
            return value.decode("utf-8") if value is not None else None
        except redis.RedisError as exc:
            logger.warning("verification_cache_read_error", namespace=self._namespace, error=str(exc))
            return None

    def set(self, key: str, value: str) -> None:
        client = _redis_client()
        if client is None:
            return
        try:
            client.setex(self._key(key), self._ttl_seconds, value)
        except redis.RedisError as exc:
            logger.warning("verification_cache_write_error", namespace=self._namespace, error=str(exc))
