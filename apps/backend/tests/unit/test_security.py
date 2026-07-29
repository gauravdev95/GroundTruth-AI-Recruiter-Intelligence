"""Unit tests for password hashing, JWT round-trips, and token/OTP generation."""

from __future__ import annotations

import uuid

import jwt
import pytest

from src.domains.auth.security import (
    create_access_token,
    decode_access_token,
    generate_opaque_token,
    generate_otp,
    hash_opaque_token,
    hash_otp,
    hash_password,
    verify_password,
)


def test_hash_password_is_not_plaintext() -> None:
    hashed = hash_password("StrongPass1!")
    assert hashed != "StrongPass1!"
    assert hashed.startswith("$2b$")


def test_verify_password_correct_and_incorrect() -> None:
    hashed = hash_password("StrongPass1!")
    assert verify_password("StrongPass1!", hashed) is True
    assert verify_password("WrongPass1!", hashed) is False


def test_verify_password_rejects_malformed_hash() -> None:
    assert verify_password("anything", "not-a-real-hash") is False


def test_access_token_round_trip() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, role="candidate")
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "candidate"
    assert payload["type"] == "access"


def test_access_token_tampered_signature_rejected() -> None:
    token = create_access_token(user_id=uuid.uuid4(), role="candidate")
    tampered = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(tampered)


def test_opaque_token_is_unique_and_hash_is_deterministic() -> None:
    token_a = generate_opaque_token()
    token_b = generate_opaque_token()
    assert token_a != token_b
    assert hash_opaque_token(token_a) == hash_opaque_token(token_a)
    assert hash_opaque_token(token_a) != hash_opaque_token(token_b)


def test_otp_is_six_digits_and_hash_is_deterministic() -> None:
    otp = generate_otp()
    assert len(otp) == 6
    assert otp.isdigit()
    assert hash_otp(otp) == hash_otp(otp)
    assert hash_otp(otp) != hash_otp(generate_otp() + "0")
