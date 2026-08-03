"""Realtime push — a WebSocket layer over the notification rows that already
exist.

The hole this fills was left deliberately: `pipeline/notifications.py`'s
`notify_new_matches` has always returned `(user_id, payload)` per notification
"so the caller can emit the same payload over the socket without re-deriving
it", and until now nothing consumed that return value.

## Delivery guarantee: best-effort, on top of durable rows

**The `notifications` row is the record. The socket is a latency
optimisation.** Every event pushed here mirrors a row that was written and
*committed* first — the ordering matters, and the call sites enforce it
(`jobs/tasks/matching.py::_announce_new_matches` commits, then publishes).

That single decision answers what happens to events emitted while a client is
disconnected: **nothing, and nothing needs to.**

* There is **no server-side replay buffer**, no per-user outbox, no
  at-least-once redelivery. A push that lands while a socket is down is
  dropped.
* On (re)connect the server sends a `connected` frame, and the client
  responds by invalidating its queries. The refetch reads the same tables the
  notification rows live in, so it recovers *everything* missed — not just
  what a buffer happened to retain, and correctly even if the client was
  offline for a week.

Building replay would mean duplicating durability that Postgres already
provides, and doing it worse: a Redis-backed outbox would need its own
retention policy, its own ack protocol, and its own answer for a client that
never comes back. The refetch-on-connect is strictly stronger and is three
lines of client code.

The honest consequence, stated rather than hidden: a client that is connected
but whose *socket* silently dies without either side noticing will not get
pushes and will not know to refetch. Two things bound that window rather than
eliminating it — a client-driven 25s keepalive (`ping`/`pong`, so a dead
connection surfaces as a close within about half a minute instead of never),
and the notification bell's own 30s poll, which is deliberately kept as the
floor underneath the socket for exactly this case.

## Shape

* `events.py` — the wire envelope and the one pub/sub channel.
* `manager.py` — this process's live connections, keyed by `user_id`.
* `bus.py` — Redis pub/sub: `publish_to_user` (sync, callable from a Celery
  worker) and `RealtimeSubscriber` (async, one per API process).
* `router.py` — the endpoint and its first-frame JWT handshake.
"""

from src.realtime.bus import publish_many, publish_to_user, subscriber
from src.realtime.events import RealtimeEvent
from src.realtime.manager import manager

__all__ = ["RealtimeEvent", "manager", "publish_many", "publish_to_user", "subscriber"]
