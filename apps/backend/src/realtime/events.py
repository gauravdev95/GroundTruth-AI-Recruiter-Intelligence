"""The wire format for realtime pushes.

One envelope shape for every event, so a client can route on `type` without
having to sniff the payload, and so adding an event type is a constant here
plus a call site rather than a new message grammar.

Event `type` values deliberately mirror `NotificationType`
(`domains/pipeline/models.py`) rather than inventing a parallel vocabulary:
every realtime event this system sends is the push half of a notification
row that was already written and committed. If the two ever disagreed, the
socket would be describing something the durable record does not contain.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from src.domains.pipeline.models import NotificationType

#: The single Redis pub/sub channel every process publishes to and every API
#: process subscribes to.
#:
#: One channel with the recipient inside the message, rather than a channel
#: per user. A per-user channel would mean each API instance only receives
#: events for users it actually holds a socket for — genuinely better fan-out
#: — but it also means subscribing and unsubscribing on the live `PubSub`
#: object from the request tasks that accept and drop connections, while the
#: reader task is concurrently blocked on it. redis-py's asyncio `PubSub` is
#: not safe to mutate that way, and working around it costs a lock plus a
#: sentinel subscription to keep the reader valid when no user is connected.
#:
#: The cost of the simple version is a JSON parse and one dict lookup per
#: event per API instance, for events that are already rare (a new match, not
#: a chat keystroke). That is the right trade at this scale. The point at
#: which it stops being right is when either the event rate or the instance
#: count grows enough that per-instance discard work is measurable — at which
#: point the fix is a per-user channel or a dedicated socket gateway, not a
#: cleverer version of this.
EVENTS_CHANNEL = "groundtruth:realtime:events"


@dataclass(frozen=True)
class RealtimeEvent:
    """What one connected client receives, and what one pub/sub message
    carries. `user_id` is the routing key — it never reaches the client,
    which already knows who it is."""

    user_id: uuid.UUID
    type: NotificationType
    payload: dict[str, Any]

    def to_bus_message(self) -> dict[str, Any]:
        return {"user_id": str(self.user_id), "type": self.type.value, "payload": self.payload}

    def to_client_frame(self) -> dict[str, Any]:
        return {"type": self.type.value, "payload": self.payload}

    @classmethod
    def from_bus_message(cls, message: dict[str, Any]) -> "RealtimeEvent | None":
        """Returns `None` for anything malformed rather than raising.

        A single unparseable message must not kill the subscriber loop and
        take every connected client's push delivery down with it — and since
        the socket is best-effort over durable notification rows
        (`src/realtime/__init__.py`), dropping one is recoverable in a way
        that a dead reader task is not.
        """
        try:
            return cls(
                user_id=uuid.UUID(message["user_id"]),
                type=NotificationType(message["type"]),
                payload=dict(message["payload"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
