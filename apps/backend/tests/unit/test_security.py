"""Unit tests for password hashing, JWT round-trips, and opaque token generation."""

from __future__ import annotations

import uuid

import jwt
import pytest
from jwt.utils import base64url_decode

from src.domains.auth.security import (
    create_access_token,
    decode_access_token,
    generate_opaque_token,
    hash_opaque_token,
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
    """Flips a character in the *middle* of the signature segment, and
    asserts the decoded signature bytes really changed before relying on the
    rejection.

    The previous version rewrote the last two base64url characters, which is
    intermittently a no-op. An HS256 signature is 32 bytes = 43 base64url
    characters; the final character encodes only 4 significant bits, its
    low 2 bits being padding. So `'a'` (011010) and `'b'` (011011) in the
    last position decode to identical bytes — a token ending in `"ab"`
    "tampered" to `"aa"` verified fine and the test failed roughly one run
    in a few hundred. Every character before the last carries 6 significant
    bits, so a middle-of-segment flip always changes the signature.
    """
    token = create_access_token(user_id=uuid.uuid4(), role="candidate")
    header, payload, signature = token.split(".")

    index = len(signature) // 2
    original = signature[index]
    # Two candidates so the replacement is never equal to what was there.
    flipped = "A" if original != "A" else "B"
    tampered_signature = signature[:index] + flipped + signature[index + 1 :]

    assert base64url_decode(tampered_signature) != base64url_decode(signature)

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(f"{header}.{payload}.{tampered_signature}")


def test_opaque_token_is_unique_and_hash_is_deterministic() -> None:
    token_a = generate_opaque_token()
    token_b = generate_opaque_token()
    assert token_a != token_b
    assert hash_opaque_token(token_a) == hash_opaque_token(token_a)
    assert hash_opaque_token(token_a) != hash_opaque_token(token_b)


