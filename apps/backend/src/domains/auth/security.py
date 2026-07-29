"""Password hashing, JWT encode/decode, and opaque token/OTP generation.

All secrets (passwords, refresh tokens, reset tokens, OTPs) are hashed
before being persisted — the database never holds a value an attacker
could replay directly from a leaked row.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt

from src.config.config import get_security_settings

TokenType = Literal["access", "refresh"]


# --- Password hashing -------------------------------------------------------


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# --- JWT access tokens --------------------------------------------------------


def create_access_token(*, user_id: uuid.UUID, role: str) -> str:
    settings = get_security_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_security_settings()
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload


# --- Opaque tokens (refresh tokens, password reset links) --------------------


def generate_opaque_token() -> str:
    """A URL-safe random token to hand to the client; only its hash is stored."""
    return secrets.token_urlsafe(48)


def hash_opaque_token(token: str) -> str:
    """SHA-256 is sufficient here (high-entropy random input, not a user password)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --- OTPs ----------------------------------------------------------------------


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return secrets.compare_digest(a, b)
