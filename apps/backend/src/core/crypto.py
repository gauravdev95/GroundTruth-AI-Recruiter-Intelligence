"""Symmetric encryption for secrets that must be stored, not just hashed.

Everything else in the auth domain (passwords, refresh tokens, OTPs) is
one-way hashed — the app never needs the plaintext back. A GitHub OAuth
access token is different: `domains/student/github_oauth.py` needs the
plaintext to call the GitHub API on the candidate's behalf, so it must be
reversibly encrypted rather than hashed. Fernet (AES-128-CBC + HMAC, from
the `cryptography` package) is used rather than hand-rolled AES because it
also verifies integrity — a tampered ciphertext raises rather than decrypting
into garbage that gets sent to GitHub as a bearer token.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from src.config.config import get_security_settings


@lru_cache
def _fernet() -> Fernet:
    settings = get_security_settings()
    if settings.token_encryption_key:
        key = settings.token_encryption_key.encode("utf-8")
    else:
        # Dev fallback: derive a stable Fernet key from `secret_key` so local
        # development doesn't need a second generated secret. Not used when
        # `TOKEN_ENCRYPTION_KEY` is set, which every non-dev environment must do.
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str | None:
    """Returns `None` rather than raising on a corrupt/foreign-key value —
    callers treat a token that fails to decrypt the same as a missing one
    (re-connect required), not as a 500."""
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None
