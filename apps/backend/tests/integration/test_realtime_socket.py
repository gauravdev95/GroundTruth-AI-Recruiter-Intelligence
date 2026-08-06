"""Integration tests for the WebSocket endpoint's authentication handshake.

The load-bearing claim under test is that the socket authenticates through
the *same* JWT path HTTP requests do — `resolve_user_from_access_token`, the
function `get_current_user` also calls. A socket that accepted a refresh
token, or one that kept working for a deactivated account, would be a real
authentication bypass, and the way that happens is a second implementation
drifting from the first.

Delivery itself (bus → registry → frame) is covered without Redis in
`tests/unit/test_realtime.py`; this file is about who is allowed to open a
connection at all.
"""

from __future__ import annotations

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from src.config.config import get_security_settings
from src.domains.auth import service as auth_service
from src.domains.auth.models import CandidateProfile, User
from src.domains.auth.schemas import CandidateRegisterRequest
from src.domains.auth.security import create_access_token
from src.realtime.manager import manager
from src.realtime.router import CLOSE_AUTH_FAILED

WS_URL = "/api/v1/realtime/ws"


@pytest.fixture()
def candidate(db_session: Session) -> tuple[User, str]:
    user = auth_service.register_candidate(
        db_session,
        CandidateRegisterRequest(
            full_name="Ada Lovelace", email="socket@example.com", phone_number="+14155552671",
            password="StrongPass1!", confirm_password="StrongPass1!", captcha_token="test", accept_terms=True,
        ),
    )
    db_session.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id)).scalar_one()
    return user, create_access_token(user_id=user.id, role=user.role.value)


def test_a_valid_access_token_opens_the_socket_and_registers_the_connection(
    client: TestClient, candidate
) -> None:
    user, token = candidate

    with client.websocket_connect(WS_URL) as socket:
        socket.send_json({"type": "authenticate", "token": token})
        assert socket.receive_json() == {"type": "connected", "payload": {}}

        # The `connected` frame is the client's cue to invalidate its queries
        # — that refetch is what replaces a server-side replay buffer, so it
        # has to actually arrive.
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong", "payload": {}}


@pytest.mark.parametrize(
    "frame",
    [
        {"type": "authenticate", "token": "not-a-jwt"},
        {"type": "authenticate", "token": ""},
        {"type": "authenticate"},
        {"type": "subscribe", "token": "irrelevant"},
        {"not": "a frame this endpoint knows"},
    ],
    ids=["garbage-token", "empty-token", "no-token", "wrong-frame-type", "unknown-frame"],
)
def test_a_socket_that_does_not_authenticate_is_closed(client: TestClient, frame) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(WS_URL) as socket:
            socket.send_json(frame)
            socket.receive_json()
    assert exc.value.code == CLOSE_AUTH_FAILED


def test_a_refresh_token_is_not_accepted_as_a_socket_credential(client: TestClient, candidate) -> None:
    """`decode_access_token` rejects anything whose `type` claim is not
    `access`. Asserted here specifically because it is the check a
    hand-rolled socket auth path is most likely to omit — the signature is
    valid, so a naive `jwt.decode` would let it through."""
    user, _token = candidate
    settings = get_security_settings()
    refresh_shaped = jwt.encode(
        {"sub": str(user.id), "role": user.role.value, "type": "refresh"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(WS_URL) as socket:
            socket.send_json({"type": "authenticate", "token": refresh_shaped})
            socket.receive_json()
    assert exc.value.code == CLOSE_AUTH_FAILED


def test_a_token_signed_with_the_wrong_key_is_not_accepted(client: TestClient, candidate) -> None:
    user, _token = candidate
    forged = jwt.encode(
        {"sub": str(user.id), "role": user.role.value, "type": "access"}, "not-the-real-key", algorithm="HS256"
    )

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(WS_URL) as socket:
            socket.send_json({"type": "authenticate", "token": forged})
            socket.receive_json()
    assert exc.value.code == CLOSE_AUTH_FAILED


def test_a_deactivated_account_cannot_open_a_socket(
    client: TestClient, db_session: Session, candidate
) -> None:
    """The same `is_active` check `get_current_user` applies. A socket is a
    long-lived credential-backed connection, so this is the check that stops
    a deactivated user simply reconnecting."""
    user, token = candidate
    user.is_active = False
    db_session.commit()

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(WS_URL) as socket:
            socket.send_json({"type": "authenticate", "token": token})
            socket.receive_json()
    assert exc.value.code == CLOSE_AUTH_FAILED


def test_the_connection_is_deregistered_when_the_client_goes_away(
    client: TestClient, candidate
) -> None:
    """A registry that kept dead connections would push into closed sockets
    forever and leak one entry per user who has ever connected."""
    user, token = candidate

    with client.websocket_connect(WS_URL) as socket:
        socket.send_json({"type": "authenticate", "token": token})
        socket.receive_json()
        assert user.id in manager._connections  # noqa: SLF001

    # Read the plain dict rather than `connection_count()`: that coroutine
    # takes an `asyncio.Lock` bound to the app's own event loop, which this
    # (synchronous, different-thread) test body has no way to enter. The
    # deregistration happens in the endpoint's `finally`, which `__exit__`
    # above has already awaited.
    assert user.id not in manager._connections  # noqa: SLF001
