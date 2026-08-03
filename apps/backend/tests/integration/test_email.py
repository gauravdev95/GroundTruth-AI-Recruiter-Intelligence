"""Integration tests for the mail module (`src/core/mail/`) — proves real
delivery, not just that a function was called. The `mail_outbox` fixture
(see `conftest.py`) is the `CaptureMailer` backend's in-memory outbox;
`MAIL_BACKEND=capture` is pinned for the whole test process regardless of
`.env`, so these tests never touch a real SMTP server.

The two auth flows go one step further than "an email was sent": the OTP /
reset token is *extracted from the captured body* (never read off a service
return value) and submitted back to the real HTTP endpoint, proving the
content a user would actually receive is functional, not just present.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.domains.auth import service as auth_service
from src.domains.auth.schemas import CandidateRegisterRequest


def _register_candidate(db_session: Session, email: str = "mail.flow@example.com"):
    payload = CandidateRegisterRequest(
        full_name="Ada Lovelace",
        email=email,
        phone_number="+14155552671",
        password="StrongPass1!",
        confirm_password="StrongPass1!",
        captcha_token="test",
        accept_terms=True,
    )
    return auth_service.register_candidate(db_session, payload)


def test_registration_sends_a_verification_email_and_the_otp_in_it_actually_works(
    client: TestClient, db_session: Session, mail_outbox
):
    assert mail_outbox == []
    user, _otp_from_service, _ = _register_candidate(db_session, "otp.roundtrip@example.com")

    assert len(mail_outbox) == 1
    message = mail_outbox[0]
    assert message.to_email == user.email
    assert "verif" in message.subject.lower()

    match = re.search(r"code is:\s*(\d{6})", message.text_body)
    assert match is not None, f"no 6-digit OTP found in captured body: {message.text_body!r}"
    otp_from_email = match.group(1)

    resp = client.post(
        "/api/v1/auth/verify-email/confirm", json={"email": user.email, "otp": otp_from_email}
    )
    assert resp.status_code == 200, resp.text


def test_password_reset_sends_an_email_and_the_link_token_actually_works(
    client: TestClient, db_session: Session, mail_outbox
):
    user, otp, _ = _register_candidate(db_session, "reset.roundtrip@example.com")
    auth_service.confirm_email_otp(db_session, user.email, otp)
    mail_outbox.clear()

    resp = client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert resp.status_code == 200

    assert len(mail_outbox) == 1
    message = mail_outbox[0]
    assert message.to_email == user.email

    match = re.search(r"token=([^\s\"]+)", message.text_body)
    assert match is not None, f"no reset token found in captured body: {message.text_body!r}"
    token_from_email = match.group(1)

    reset_resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token_from_email, "new_password": "NewStrongPass2@", "confirm_password": "NewStrongPass2@"},
    )
    assert reset_resp.status_code == 200, reset_resp.text

    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "NewStrongPass2@",
            "captcha_token": "test",
            "remember_me": False,
            "expected_role": "candidate",
        },
    )
    assert login_resp.status_code == 200


def test_forgot_password_for_unknown_email_sends_nothing(client: TestClient, mail_outbox):
    resp = client.post("/api/v1/auth/forgot-password", json={"email": "nobody.here@example.com"})
    assert resp.status_code == 200
    assert mail_outbox == []
