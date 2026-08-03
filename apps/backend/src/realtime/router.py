"""The WebSocket endpoint: `GET /api/v1/realtime/ws`.

**Authentication is a first-frame handshake, not a query parameter.**

A browser's `WebSocket` constructor cannot set an `Authorization` header, so
the usual options are a `?token=` query parameter, the `Sec-WebSocket-Protocol`
header, or an application-level handshake. This uses the handshake:

* `?token=` puts a live access token in a URL, and URLs are the one place
  credentials reliably leak — nginx/ALB access logs, APM traces, `Referer`
  headers, browser history. This codebase already keeps the access token out
  of Web Storage for the same class of reason (`lib/tokenStore.ts`); putting
  it in a logged URL would undo that.
* `Sec-WebSocket-Protocol` works, but it means overloading a content
  negotiation header with a credential, which every reader has to be told
  about.
* A first frame is plain: connect, send `{"type": "authenticate", "token":
  "..."}`, and the server closes the socket if that does not arrive, parse,
  and resolve within `realtime_auth_timeout_seconds`.

The token itself is the ordinary access token, resolved by
`domains/auth/dependencies.py::resolve_user_from_access_token` — the same
function `get_current_user` uses. There is no realtime-specific token, no
second signing key, and no separate expiry: a socket is exactly as
authenticated as an HTTP request made with the same credential, and an
account deactivated between connect and reconnect fails at the same place.

**Authorization is the connection itself.** A socket is bound to one
`user_id` at handshake and only ever receives events routed to that id
(`manager.py`). There is no subscribe verb a client can use to ask for
another user's stream, which is why there is no per-event authorization
check to get wrong.

**Cross-origin is a non-issue here, and the handshake is why.** WebSockets
are exempt from the same-origin policy — `CORSMiddleware` does not apply to
them and any page on the internet can open a connection to this endpoint.
That is harmless precisely because the credential is a bearer token the
client must *send*, not a cookie the browser attaches automatically: an
attacker's page cannot read our in-memory access token, and the httpOnly
refresh cookie is unreadable to JS by design. A cross-origin socket
therefore reaches exactly as far as `_authenticate` and is closed. Had this
been cookie-authenticated, it would have been a CSRF hole with no preflight
to stop it.
"""

from __future__ import annotations

import asyncio
import uuid

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from src.config.config import get_realtime_settings
from src.db.database import get_db
from src.domains.auth.dependencies import resolve_user_from_access_token
from src.realtime.manager import manager

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/realtime", tags=["realtime"])

# Application close codes, from RFC 6455's private-use range (4000-4999).
# Distinct codes rather than a generic 1008 so the client can tell "your
# credential was refused" (worth one token refresh and a retry) from "you
# never authenticated" (a client bug — retrying changes nothing).
CLOSE_AUTH_FAILED = 4401
CLOSE_AUTH_TIMEOUT = 4408


async def _authenticate(websocket: WebSocket, db: Session) -> uuid.UUID | None:
    settings = get_realtime_settings()
    try:
        frame = await asyncio.wait_for(
            websocket.receive_json(), timeout=settings.realtime_auth_timeout_seconds
        )
    except asyncio.TimeoutError:
        await websocket.close(code=CLOSE_AUTH_TIMEOUT, reason="Authentication timed out")
        return None
    except (WebSocketDisconnect, ValueError):
        # Client vanished, or sent something that is not JSON at all. Either
        # way there is no credential and nothing to answer to.
        return None

    if not isinstance(frame, dict) or frame.get("type") != "authenticate":
        await websocket.close(code=CLOSE_AUTH_FAILED, reason="Expected an authenticate frame")
        return None

    token = frame.get("token")
    user = resolve_user_from_access_token(db, token) if isinstance(token, str) else None
    if user is None:
        await websocket.close(code=CLOSE_AUTH_FAILED, reason="Invalid or expired token")
        return None

    return user.id


@router.websocket("/ws")
async def realtime_socket(websocket: WebSocket, db: Session = Depends(get_db)) -> None:
    """One socket per client, bound to one user for its lifetime.

    The read loop exists to detect disconnects and to service client pings —
    the server never expects meaningful input after the handshake. Pushes go
    the other way, driven by `bus.RealtimeSubscriber`.
    """
    await websocket.accept()

    user_id = await _authenticate(websocket, db)
    if user_id is None:
        return

    await manager.add(user_id, websocket)
    # Tells the client the handshake succeeded, which is its cue to invalidate
    # its queries. That refetch is what covers everything it missed while
    # disconnected — see `src/realtime/__init__.py` on why there is no
    # server-side replay.
    await websocket.send_json({"type": "connected", "payload": {}})
    logger.info("realtime_connected", user_id=str(user_id))

    try:
        while True:
            message = await websocket.receive_json()
            # A client-initiated keepalive. Answered rather than ignored so a
            # client behind a proxy that strips protocol-level pings can still
            # prove the connection is alive.
            if isinstance(message, dict) and message.get("type") == "ping":
                await websocket.send_json({"type": "pong", "payload": {}})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("realtime_socket_closed", user_id=str(user_id), error=str(exc))
    finally:
        await manager.remove(user_id, websocket)
        logger.info("realtime_disconnected", user_id=str(user_id))
