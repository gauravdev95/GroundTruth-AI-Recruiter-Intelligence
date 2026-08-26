"""The cross-process channel between whoever *decides* an event happened and
whoever *holds the socket* to tell.

Those are never the same process. A new match is computed by a Celery worker
(`jobs/tasks/matching.py`); the student waiting to hear about it has a
WebSocket open against an API process. Neither can reach the other's memory,
so the event goes through Redis pub/sub.

**Why pub/sub and not another Celery queue.** A Celery queue is
work-distribution: exactly one consumer gets each message. That is the wrong
shape here — the message has to reach *the specific instance* holding the
recipient's socket, and no producer knows which one that is. Pub/sub
broadcasts, and every instance decides for itself whether it has anyone to
deliver to (`manager.py`). Redis is already a hard dependency of this system
(broker, result backend, verification rate limiter), so this adds a usage,
not a component.

**Publishing is synchronous, subscribing is not.** Publishers are ordinary
sync code — Celery tasks and FastAPI's sync request handlers — so
`publish_to_user` uses the sync client and can be called from anywhere. Only
the API process subscribes, and it does so on its own event loop, so
`RealtimeSubscriber` uses `redis.asyncio`.

**Publishing never raises.** A Redis outage must degrade to "no live push"
and nothing else: the notification row is already committed by the time
anything here is called, so the user still sees it on their next fetch. A
publish failure taking down a matching run — or worse, a stage transition —
would trade a durable feature for a best-effort one.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import redis
import redis.asyncio as aioredis
import structlog

from src.config.config import get_realtime_settings
from src.domains.pipeline.models import NotificationType
from src.realtime.events import EVENTS_CHANNEL, RealtimeEvent
from src.realtime.manager import ConnectionManager, manager as default_manager

logger = structlog.get_logger(__name__)


_publisher_client: redis.Redis | None = None


def _publisher() -> redis.Redis | None:
    """Cached sync client, or ``None`` if Redis is unreachable.

    Unlike the original ``@lru_cache`` implementation, this does **not**
    permanently cache a ``None`` result. If Redis was down at first use but
    recovers 10 seconds later (common on shared Render Redis), subsequent
    calls will retry the connection rather than remaining permanently dead
    for the lifetime of the process.

    The trade-off is a dict lookup on every publish instead of the
    ``lru_cache`` fast-path — negligible compared to the network round-trip.
    """
    global _publisher_client
    if _publisher_client is not None:
        # Verify the cached client is still alive with a fast pipeline ping.
        try:
            _publisher_client.ping()
            return _publisher_client
        except redis.RedisError:
            _publisher_client = None

    settings = get_realtime_settings()
    try:
        client = redis.Redis.from_url(
            settings.redis_url, socket_connect_timeout=2, socket_timeout=2
        )
        client.ping()
        _publisher_client = client
        return client
    except redis.RedisError as exc:
        logger.warning("realtime_publisher_unavailable", error=str(exc))
        return None


def publish_to_user(user_id: uuid.UUID, type_: NotificationType, payload: dict[str, Any]) -> bool:
    """Fans one event out to every API instance. Returns whether it was
    handed to Redis at all — *not* whether anyone received it, which no
    publisher can know and none of them act on.

    Call this only after the notification row it mirrors has been committed.
    A push for a row that then rolls back is a notification the user was told
    about and can never find.
    """
    client = _publisher()
    if client is None:
        return False

    event = RealtimeEvent(user_id=user_id, type=type_, payload=payload)
    try:
        client.publish(EVENTS_CHANNEL, json.dumps(event.to_bus_message()))
        return True
    except redis.RedisError as exc:
        logger.warning("realtime_publish_failed", user_id=str(user_id), error=str(exc))
        return False


def publish_many(events: list[tuple[uuid.UUID, dict[str, Any]]], *, type_: NotificationType) -> int:
    """Bulk form for a worker that just wrote a batch of notifications —
    e.g. `notifications.notify_new_matches`' `(user_id, payload)` return
    value, which exists precisely so the caller can emit the same payload it
    persisted without re-deriving it. Returns the number published."""
    return sum(1 for user_id, payload in events if publish_to_user(user_id, type_, payload))


class RealtimeSubscriber:
    """The API process's half: one long-lived task reading `EVENTS_CHANNEL`
    and handing each event to the local `ConnectionManager`.

    Started and stopped by the FastAPI lifespan (`src/main.py`) rather than
    lazily on first connection, so a Redis problem shows up in the startup
    log rather than the first time a student happens to open a dashboard.
    """

    def __init__(self, connection_manager: ConnectionManager | None = None) -> None:
        self._manager = connection_manager or default_manager
        self._task: asyncio.Task | None = None
        self._client: aioredis.Redis | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run(), name="realtime-subscriber")

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _run(self) -> None:
        """Reconnects indefinitely with a bounded backoff.

        Deliberately no give-up condition. A Redis restart must not
        permanently disable live push for the lifetime of an API process that
        is otherwise perfectly healthy — and because delivery is best-effort
        over durable rows, an outage costs latency on the next fetch, never
        data.
        """
        backoff = 1.0
        while not self._stopping.is_set():
            try:
                await self._consume()
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("realtime_subscriber_reconnecting", error=str(exc), retry_in=backoff)
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=backoff)
                    return  # stop() was called while waiting
                except asyncio.TimeoutError:
                    backoff = min(backoff * 2, 30.0)

    async def _consume(self) -> None:
        settings = get_realtime_settings()
        self._client = aioredis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        pubsub = self._client.pubsub()
        await pubsub.subscribe(EVENTS_CHANNEL)
        logger.info("realtime_subscriber_started", channel=EVENTS_CHANNEL)

        try:
            while not self._stopping.is_set():
                # Timeout rather than an indefinite block: it is what lets the
                # loop notice `_stopping` and shut down promptly instead of
                # hanging until the next message arrives.
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:
                    continue
                await self._dispatch(message.get("data"))
        finally:
            await pubsub.aclose()

    async def _dispatch(self, raw: Any) -> None:
        try:
            decoded = json.loads(raw)
        except (TypeError, ValueError):
            logger.debug("realtime_message_unparseable")
            return

        event = RealtimeEvent.from_bus_message(decoded) if isinstance(decoded, dict) else None
        if event is None:
            logger.debug("realtime_message_malformed")
            return

        # 0 delivered is the ordinary case: this instance holds no socket for
        # that user. It is not logged as a miss, because on a multi-instance
        # deployment most instances legitimately discard most events.
        await self._manager.send_to_user(event.user_id, event.to_client_frame())


#: Process-wide singleton, for the same reason `manager` is one.
subscriber = RealtimeSubscriber()
