"""Integration tests for the authentication API and service layer.

Registration/verification are set up by calling `service` functions
directly (the OTP is intentionally never exposed over HTTP), then the
actual behavior under test goes through the real HTTP endpoints via
`TestClient` so cookie/CSRF/status-code behavior is exercised for real.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.domains.auth import service
from src.domains.auth.exceptions import AccountLocked, InvalidCredentials
from src.domains.auth.models import UserRole
from src.domains.auth.schemas import CandidateRegisterRequest, LoginRequest, RecruiterRegisterRequest


def _error_body_without_request_id(response) -> dict:
    """Strip the per-request `request_id` so two independent responses can be
    compared for enumeration-safety (identical error shape/message)."""
    body = response.json()
    details = (body.get("error") or {}).get("details") or {}
    stripped_details = {k: v for k, v in details.items() if k != "request_id"} or None
    return {**body, "error": {**body["error"], "details": stripped_details}}


def _register_candidate(db_session: Session, email: str = "candidate.flow@example.com"):
    payload = CandidateRegisterRequest(
        full_name="Ada Lovelace",
        email=email,
        phone_number="+14155552671",
        password="StrongPass1!",
        confirm_password="StrongPass1!",
        captcha_token="test",
        accept_terms=True,
    )
    return service.register_candidate(db_session, payload)


def _register_and_verify_candidate(db_session: Session, email: str = "candidate.flow@example.com"):
    user, otp, _ = _register_candidate(db_session, email)
    service.confirm_email_otp(db_session, user.email, otp)
    return user


def _register_recruiter(db_session: Session, email: str = "recruiter.flow@acme.com"):
    payload = RecruiterRegisterRequest(
        full_name="Grace Hopper",
        company_name="Acme Corp",
        company_email=email,
        password="StrongPass1!",
        confirm_password="StrongPass1!",
        captcha_token="test",
        accept_terms=True,
    )
    return service.register_recruiter(db_session, payload)


def test_candidate_full_auth_flow(client: TestClient, db_session: Session) -> None:
    _register_and_verify_candidate(db_session)

    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "candidate.flow@example.com",
            "password": "StrongPass1!",
            "captcha_token": "test",
            "remember_me": True,
            "expected_role": "candidate",
        },
    )
    assert login_resp.status_code == 200
    body = login_resp.json()
    access_token = body["access_token"]
    assert body["user"]["role"] == "candidate"
    assert body["user"]["is_email_verified"] is True
    assert "refresh_token" in login_resp.cookies
    assert "csrf_token" in login_resp.cookies

    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "candidate.flow@example.com"

    # Refresh rotates both the refresh token and the CSRF token.
    old_refresh_cookie = login_resp.cookies["refresh_token"]
    csrf_token = login_resp.cookies["csrf_token"]
    refresh_resp = client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf_token})
    assert refresh_resp.status_code == 200
    # Not `!= access_token`: JWT `iat`/`exp` are integer-second NumericDate
    # claims (RFC 7519), so two tokens for the same user minted within the
    # same wall-clock second are byte-identical — a real possibility now
    # that this suite runs fast against a local test database, and not a
    # security property worth asserting anyway. The refresh *token* rotating
    # is the actual replay defense; assert that instead, plus that the new
    # access token genuinely works.
    new_access_token = refresh_resp.json()["access_token"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access_token}"}).status_code == 200
    assert refresh_resp.cookies["refresh_token"] != old_refresh_cookie

    # The stale CSRF token from before rotation must no longer work.
    stale_csrf_resp = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf_token})
    assert stale_csrf_resp.status_code == 403

    new_csrf = refresh_resp.cookies["csrf_token"]
    logout_resp = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": new_csrf})
    assert logout_resp.status_code == 200

    # The refresh token was revoked on logout.
    refresh_after_logout = client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": new_csrf})
    assert refresh_after_logout.status_code in (401, 403)


def test_recruiter_full_auth_flow(client: TestClient, db_session: Session) -> None:
    user, otp, _ = _register_recruiter(db_session)
    verify_resp = client.post(
        "/api/v1/auth/verify-email/confirm", json={"email": user.email, "otp": otp}
    )
    assert verify_resp.status_code == 200

    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "StrongPass1!",
            "captcha_token": "test",
            "remember_me": False,
            "expected_role": "recruiter",
        },
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["user"]["role"] == "recruiter"
    # Non-"remember me" sessions are browser session cookies (no Max-Age set).
    refresh_cookie = next(c for c in login_resp.headers.get_list("set-cookie") if c.startswith("refresh_token="))
    assert "Max-Age" not in refresh_cookie


def test_role_mismatch_rejected(client: TestClient, db_session: Session) -> None:
    _register_and_verify_candidate(db_session, email="wrongportal@example.com")

    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "wrongportal@example.com",
            "password": "StrongPass1!",
            "captcha_token": "test",
            "remember_me": False,
            "expected_role": "recruiter",
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ROLE_MISMATCH"


def test_login_without_expected_role_succeeds_and_reports_role(
    client: TestClient, db_session: Session
) -> None:
    """The unified `/login` page sends no `expected_role` — the role comes back
    on the session instead, and is what the client redirects on. A candidate
    signing in through it must not be treated as a role mismatch."""
    _register_and_verify_candidate(db_session, email="roleagnostic@example.com")

    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "roleagnostic@example.com",
            "password": "StrongPass1!",
            "captcha_token": "test",
            "remember_me": False,
        },
    )

    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "candidate"


def test_unverified_email_cannot_login(client: TestClient, db_session: Session) -> None:
    user, _otp, _ = _register_candidate(db_session, email="unverified@example.com")

    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "StrongPass1!",
            "captcha_token": "test",
            "remember_me": False,
            "expected_role": "candidate",
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"


def test_invalid_otp_rejected(client: TestClient, db_session: Session) -> None:
    user, _otp, _ = _register_candidate(db_session, email="badotp@example.com")

    resp = client.post(
        "/api/v1/auth/verify-email/confirm", json={"email": user.email, "otp": "000000"}
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_OTP"


def test_login_wrong_password_does_not_leak_existence(client: TestClient, db_session: Session) -> None:
    _register_and_verify_candidate(db_session, email="realuser@example.com")

    real_user_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "realuser@example.com",
            "password": "WrongPass1!",
            "captcha_token": "test",
            "remember_me": False,
            "expected_role": "candidate",
        },
    )
    nonexistent_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "doesnotexist@example.com",
            "password": "WrongPass1!",
            "captcha_token": "test",
            "remember_me": False,
            "expected_role": "candidate",
        },
    )
    assert real_user_resp.status_code == nonexistent_resp.status_code == 401
    assert _error_body_without_request_id(real_user_resp) == _error_body_without_request_id(nonexistent_resp)


def test_account_locks_after_repeated_failed_logins(db_session: Session) -> None:
    """Exercises service.authenticate directly so the 5-attempt account
    lockout is isolated from the endpoint's own 5/minute rate limit."""
    user = _register_and_verify_candidate(db_session, email="lockout@example.com")
    bad_login = LoginRequest(
        email=user.email,
        password="WrongPass1!",
        captcha_token="test",
        remember_me=False,
        expected_role=UserRole.CANDIDATE,
    )

    for _ in range(5):
        with pytest.raises(InvalidCredentials):
            service.authenticate(db_session, bad_login)

    with pytest.raises(AccountLocked):
        service.authenticate(db_session, bad_login)


def test_password_reset_flow_and_session_revocation(client: TestClient, db_session: Session) -> None:
    user = _register_and_verify_candidate(db_session, email="reset@example.com")
    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "StrongPass1!",
            "captcha_token": "test",
            "remember_me": True,
            "expected_role": "candidate",
        },
    )
    assert login_resp.status_code == 200
    csrf_token = login_resp.cookies["csrf_token"]

    raw_token = service.request_password_reset(db_session, user.email)
    assert raw_token is not None

    reset_resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "NewStrongPass2@", "confirm_password": "NewStrongPass2@"},
    )
    assert reset_resp.status_code == 200

    # Resetting the password revokes existing sessions.
    refresh_resp = client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf_token})
    assert refresh_resp.status_code in (401, 403)

    # The reset token is single-use.
    reuse_resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "AnotherPass3@", "confirm_password": "AnotherPass3@"},
    )
    assert reuse_resp.status_code == 400
    assert reuse_resp.json()["error"]["code"] == "INVALID_OR_EXPIRED_TOKEN"

    # New password works.
    new_login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "NewStrongPass2@",
            "captcha_token": "test",
            "remember_me": False,
            "expected_role": "candidate",
        },
    )
    assert new_login_resp.status_code == 200


def test_forgot_password_does_not_leak_existence(client: TestClient, db_session: Session) -> None:
    _register_and_verify_candidate(db_session, email="knownuser@example.com")

    known_resp = client.post("/api/v1/auth/forgot-password", json={"email": "knownuser@example.com"})
    unknown_resp = client.post("/api/v1/auth/forgot-password", json={"email": "unknown@example.com"})
    assert known_resp.status_code == unknown_resp.status_code == 200
    assert known_resp.json() == unknown_resp.json()


def test_duplicate_registration_rejected(client: TestClient, db_session: Session) -> None:
    _register_candidate(db_session, email="dupe@example.com")

    resp = client.post(
        "/api/v1/auth/candidate/register",
        json={
            "full_name": "Someone Else",
            "email": "dupe@example.com",
            "phone_number": "+14155552671",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "captcha_token": "test",
            "accept_terms": True,
        },
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


def test_registration_rate_limited(client: TestClient) -> None:
    def _register(email: str):
        return client.post(
            "/api/v1/auth/candidate/register",
            json={
                "full_name": "Rate Limited",
                "email": email,
                "phone_number": "+14155552671",
                "password": "StrongPass1!",
                "confirm_password": "StrongPass1!",
                "captcha_token": "test",
                "accept_terms": True,
            },
        )

    responses = [_register(f"ratelimit{i}@example.com") for i in range(4)]
    assert [r.status_code for r in responses[:3]] == [201, 201, 201]
    assert responses[3].status_code == 429
