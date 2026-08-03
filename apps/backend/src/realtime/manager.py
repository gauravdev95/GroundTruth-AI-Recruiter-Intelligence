"""The per-process registry of live WebSocket connections.

Deliberately in-process and non-durable: it maps a `user_id` to the sockets
*this* API process is currently holding, and nothing else. Cross-process
delivery is `bus.py`'s job — every API instance receives every event and
this decides whether any of its own connections care.

One user may hold several sockets at once (two browser tabs, a phone and a
laptop). All of them receive the event: a notification is about the user, not
about a session, and delivering to only one tab would make which tab updates
depend on connection order.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from typing import Any

import structlog
from fastapi import WebSocket

logger = structlog.get_logger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)
        # Guards the map against interleaved add/remove from concurrent
        # connection handlers. Not for `send_to_user`'s actual sends — those
        # happen outside the lock, so one slow client cannot block another
        # client from connecting.
        self._lock = asyncio.Lock()

    async def add(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[user_id].add(websocket)

    async def remove(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(user_id)
            if sockets is None:
                return
            sockets.discard(websocket)
            # Drop the empty set rather than leaving it: `_connections` is
            # keyed by user and would otherwise grow by one entry per user who
            # has ever connected, for the lifetime of the process.
            if not sockets:
                del self._connections[user_id]

    async def send_to_user(self, user_id: uuid.UUID, frame: dict[str, Any]) -> int:
        """Pushes `frame` to every socket this process holds for `user_id`.
        Returns how many sends succeeded — 0 is the ordinary case for an
        instance that holds none of this user's connections, not an error.

        A send that fails (the peer vanished between the snapshot and the
        write) is logged and the socket dropped, never raised: one dead
        connection must not abort delivery to the user's other tabs, and it
        must not propagate into the subscriber loop.
        """
        async with self._lock:
            # Snapshot under the lock, send outside it.
            sockets = list(self._connections.get(user_id, ()))

        delivered = 0
        for websocket in sockets:
            try:
                await websocket.send_json(frame)
                delivered += 1
            except Exception:
                logger.debug("realtime_send_failed", user_id=str(user_id))
                await self.remove(user_id, websocket)
        return delivered

    async def connection_count(self) -> int:
        async with self._lock:
            return sum(len(sockets) for sockets in self._connections.values())


#: Process-wide singleton — the WebSocket endpoint and the subscriber loop
#: must be looking at the same registry, and there is exactly one of each per
#: process.
manager = ConnectionManager()
