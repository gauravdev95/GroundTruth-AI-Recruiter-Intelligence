"""FastAPI dependencies: current-user resolution, role guards, CSRF checks."""

from __future__ import annotations

import uuid
from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.domains.auth.exceptions import CsrfValidationFailed
from src.domains.auth.models import User, UserRole
from src.domains.auth.security import decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"


def resolve_user_from_access_token(db: Session, token: str) -> User | None:
    """Access token in, `User` out — or `None` for any reason the token does
    not identify a usable account (bad signature, expired, wrong token type,
    unknown subject, deactivated user).

    Extracted from `get_current_user` so the WebSocket handshake
    (`src/realtime/router.py`) authenticates through *this* function rather
    than a second implementation of the same checks. A socket that accepted a
    refresh token, or one that kept working after an account was
    deactivated, would be a real authentication bypass — and the way that
    happens is a parallel code path drifting from this one.

    Returns `None` rather than raising `HTTPException`: a WebSocket cannot
    answer with an HTTP status once it has been accepted, so the two callers
    need to fail in different ways. The decision itself is shared; only its
    presentation differs.
    """
    try:
        payload = decode_access_token(token)
    except jwt.InvalidTokenError:
        return None

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user = resolve_user_from_access_token(db, credentials.credentials)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user


def require_role(*roles: UserRole) -> Callable[[User], User]:
    def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _dependency


def verify_csrf(request: Request) -> None:
    """Double-submit cookie CSRF check for cookie-authenticated endpoints."""
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if not cookie_token or not header_token or cookie_token != header_token:
        raise CsrfValidationFailed()
