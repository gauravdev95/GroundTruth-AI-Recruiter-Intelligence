"""Unit tests for the realtime push layer (`src/realtime/`).

No Redis and no real socket: the connection registry, the wire envelope, and
the subscriber's routing decision are each testable in isolation, and the
end-to-end handshake has its own integration test
(`tests/integration/test_realtime_socket.py`).
"""

from __future__ import annotations

import json
import uuid

import pytest

from src.domains.pipeline.models import NotificationType
from src.realtime.bus import RealtimeSubscriber
from src.realtime.events import RealtimeEvent
from src.realtime.manager import ConnectionManager


class _FakeSocket:
    """Records what was pushed. `fail=True` models a peer that vanished
    between the registry snapshot and the write."""

    def __init__(self, *, fail: bool = False) -> None:
        self.sent: list[dict] = []
        self.fail = fail

    async def send_json(self, frame: dict) -> None:
        if self.fail:
            raise RuntimeError("peer gone")
        self.sent.append(frame)


# --------------------------------------------------------------------------
# Envelope
# --------------------------------------------------------------------------


def test_bus_message_round_trips():
    event = RealtimeEvent(
        user_id=uuid.uuid4(), type=NotificationType.NEW_MATCH, payload={"job_title": "Backend Intern"}
    )
    restored = RealtimeEvent.from_bus_message(json.loads(json.dumps(event.to_bus_message())))
    assert restored == event


def test_the_client_frame_carries_no_user_id():
    """The recipient already knows who they are; echoing the id back would be
    the only place a socket frame contained a routing key a client could
    confuse for data."""
    event = RealtimeEvent(user_id=uuid.uuid4(), type=NotificationType.NEW_MATCH, payload={"score": 71})
    assert event.to_client_frame() == {"type": "new_match", "payload": {"score": 71}}


@pytest.mark.parametrize(
    "message",
    [
        {},
        {"user_id": "not-a-uuid", "type": "new_match", "payload": {}},
        {"user_id": str(uuid.uuid4()), "type": "no_such_type", "payload": {}},
        {"user_id": str(uuid.uuid4()), "type": "new_match"},
        {"user_id": str(uuid.uuid4()), "type": "new_match", "payload": "not-a-dict"},
    ],
    ids=["empty", "bad-uuid", "unknown-type", "no-payload", "payload-not-a-dict"],
)
def test_malformed_bus_messages_are_dropped_not_raised(message):
    """One bad message must not kill the subscriber loop and take live
    delivery down for every connected client — and because pushes are
    best-effort over durable rows, dropping one is recoverable in a way a
    dead reader task is not."""
    assert RealtimeEvent.from_bus_message(message) is None


# --------------------------------------------------------------------------
# Connection registry
# --------------------------------------------------------------------------


async def test_every_socket_a_user_holds_receives_the_event():
    """Two tabs, one user. A notification is about the user, not a session —
    delivering to only one would make which tab updates depend on connection
    order."""
    registry = ConnectionManager()
    user_id = uuid.uuid4()
    tab_one, tab_two = _FakeSocket(), _FakeSocket()
    await registry.add(user_id, tab_one)
    await registry.add(user_id, tab_two)

    delivered = await registry.send_to_user(user_id, {"type": "new_match", "payload": {}})

    assert delivered == 2
    assert tab_one.sent == tab_two.sent == [{"type": "new_match", "payload": {}}]


async def test_events_never_reach_another_user():
    registry = ConnectionManager()
    mine, theirs = _FakeSocket(), _FakeSocket()
    my_id, their_id = uuid.uuid4(), uuid.uuid4()
    await registry.add(my_id, mine)
    await registry.add(their_id, theirs)

    await registry.send_to_user(my_id, {"type": "new_match", "payload": {}})

    assert len(mine.sent) == 1
    assert theirs.sent == []


async def test_delivering_to_an_unconnected_user_is_zero_not_an_error():
    """The ordinary case on a multi-instance deployment: most instances hold
    no socket for most users and legitimately discard most events."""
    registry = ConnectionManager()
    assert await registry.send_to_user(uuid.uuid4(), {"type": "new_match", "payload": {}}) == 0


async def test_a_failed_send_drops_that_socket_without_stopping_the_others():
    registry = ConnectionManager()
    user_id = uuid.uuid4()
    dead, alive = _FakeSocket(fail=True), _FakeSocket()
    await registry.add(user_id, dead)
    await registry.add(user_id, alive)

    delivered = await registry.send_to_user(user_id, {"type": "new_match", "payload": {}})

    assert delivered == 1
    assert len(alive.sent) == 1
    # The dead socket was evicted, so it is not retried on the next event.
    assert await registry.connection_count() == 1


async def test_removing_the_last_socket_drops_the_user_key():
    """Otherwise `_connections` grows by one entry per user who has ever
    connected, for the lifetime of the process."""
    registry = ConnectionManager()
    user_id = uuid.uuid4()
    socket = _FakeSocket()
    await registry.add(user_id, socket)
    await registry.remove(user_id, socket)

    assert await registry.connection_count() == 0
    assert registry._connections == {}  # noqa: SLF001 — the leak is the point


async def test_removing_an_unknown_socket_is_a_no_op():
    registry = ConnectionManager()
    await registry.remove(uuid.uuid4(), _FakeSocket())  # must not raise


# --------------------------------------------------------------------------
# Subscriber routing
# --------------------------------------------------------------------------


async def test_subscriber_routes_a_published_message_to_that_users_sockets():
    registry = ConnectionManager()
    user_id = uuid.uuid4()
    socket = _FakeSocket()
    await registry.add(user_id, socket)

    event = RealtimeEvent(
        user_id=user_id, type=NotificationType.NEW_MATCH, payload={"message": "New match — 71%"}
    )
    await RealtimeSubscriber(registry)._dispatch(json.dumps(event.to_bus_message()))  # noqa: SLF001

    assert socket.sent == [{"type": "new_match", "payload": {"message": "New match — 71%"}}]


@pytest.mark.parametrize("raw", [b"not json", "{", None, json.dumps(["a", "list"])])
async def test_subscriber_survives_unparseable_traffic_on_the_channel(raw):
    registry = ConnectionManager()
    await RealtimeSubscriber(registry)._dispatch(raw)  # noqa: SLF001 — must not raise
