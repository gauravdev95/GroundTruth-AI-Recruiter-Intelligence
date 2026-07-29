"""Integration tests for the shared error envelope, request-id propagation,
and 401/403 flows through real HTTP endpoints.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.test_auth_flow import _register_and_verify_candidate


def test_unauthenticated_request_returns_401_envelope(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/me")

    assert resp.status_code == 401
    body = resp.json()
    # get_current_user raises a plain fastapi.HTTPException (not an AppError
    # subclass) — the generic HTTPException handler still normalizes it into
    # the same envelope shape.
    assert body["error"]["code"] == "UNAUTHENTICATED"
    assert "X-Request-ID" in resp.headers


def test_invalid_token_returns_401(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_role_mismatch_returns_403_envelope(client: TestClient, db_session: Session) -> None:
    _register_and_verify_candidate(db_session, email="envelope.role@example.com")

    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "envelope.role@example.com",
            "password": "StrongPass1!",
            "captcha_token": "test",
            "remember_me": False,
            "expected_role": "recruiter",
        },
    )

    assert resp.status_code == 403
    body = resp.json()
    assert body["error"]["code"] == "ROLE_MISMATCH"
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    assert body["error"]["details"]["request_id"] == resp.headers["X-Request-ID"]


def test_domain_error_envelope_shape(client: TestClient, db_session: Session) -> None:
    """A generic assertion on the {"error": {code, message, details}} shape,
    exercised via a known AppError subclass (INVALID_CREDENTIALS)."""
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nobody@example.com",
            "password": "WrongPass1!",
            "captcha_token": "test",
            "remember_me": False,
            "expected_role": "candidate",
        },
    )

    assert resp.status_code == 401
    body = resp.json()
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) == {"code", "message", "details"}
    assert body["error"]["code"] == "INVALID_CREDENTIALS"


def test_validation_error_returns_422_envelope(client: TestClient) -> None:
    # Missing required fields (password, captcha_token, expected_role).
    resp = client.post("/api/v1/auth/login", json={"email": "not-even-valid-format"})

    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_FAILED"
    assert isinstance(body["error"]["details"]["errors"], list)
    assert len(body["error"]["details"]["errors"]) > 0


def test_request_id_is_stable_within_a_response(client: TestClient) -> None:
    resp = client.get("/health")
    assert "X-Request-ID" in resp.headers

    resp_2 = client.get("/health")
    assert resp.headers["X-Request-ID"] != resp_2.headers["X-Request-ID"]
