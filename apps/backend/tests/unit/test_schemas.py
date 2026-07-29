"""Unit tests for the server-side validation rules in schemas.py."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.domains.auth.schemas import CandidateRegisterRequest, LoginRequest, RecruiterRegisterRequest

VALID_CANDIDATE = {
    "full_name": "Ada Lovelace",
    "email": "Ada@Example.com",
    "phone_number": "+14155552671",
    "password": "StrongPass1!",
    "confirm_password": "StrongPass1!",
    "captcha_token": "token",
    "accept_terms": True,
}


def test_valid_candidate_register_normalizes_email() -> None:
    payload = CandidateRegisterRequest(**VALID_CANDIDATE)
    assert payload.email == "ada@example.com"


@pytest.mark.parametrize(
    "password",
    [
        "short1!",  # too short
        "alllowercase1!",  # no uppercase
        "ALLUPPERCASE1!",  # no lowercase
        "NoDigitsHere!",  # no digit
        "NoSpecialChar1",  # no special char
    ],
)
def test_weak_passwords_rejected(password: str) -> None:
    payload = {**VALID_CANDIDATE, "password": password, "confirm_password": password}
    with pytest.raises(ValidationError):
        CandidateRegisterRequest(**payload)


def test_mismatched_confirm_password_rejected() -> None:
    payload = {**VALID_CANDIDATE, "confirm_password": "SomethingElse1!"}
    with pytest.raises(ValidationError):
        CandidateRegisterRequest(**payload)


def test_unaccepted_terms_rejected() -> None:
    payload = {**VALID_CANDIDATE, "accept_terms": False}
    with pytest.raises(ValidationError):
        CandidateRegisterRequest(**payload)


@pytest.mark.parametrize("phone", ["123", "not-a-phone", "0123456789", "++14155552671"])
def test_invalid_phone_numbers_rejected(phone: str) -> None:
    payload = {**VALID_CANDIDATE, "phone_number": phone}
    with pytest.raises(ValidationError):
        CandidateRegisterRequest(**payload)


def test_valid_recruiter_register() -> None:
    payload = RecruiterRegisterRequest(
        full_name="Grace Hopper",
        company_name="Acme Corp",
        company_email="Grace@Acme.com",
        password="StrongPass1!",
        confirm_password="StrongPass1!",
        captcha_token="token",
        accept_terms=True,
    )
    assert payload.company_email == "grace@acme.com"


def test_login_request_normalizes_email() -> None:
    payload = LoginRequest(
        email="Ada@Example.com",
        password="whatever",
        captcha_token="token",
        remember_me=False,
        expected_role="candidate",
    )
    assert payload.email == "ada@example.com"
