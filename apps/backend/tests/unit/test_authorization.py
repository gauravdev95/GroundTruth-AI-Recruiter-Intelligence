"""Unit tests for the generic RBAC/ownership primitives in core/authorization.py.

`require_role` is a FastAPI dependency *factory* — it returns a plain
callable, so it's testable directly without spinning up the app or a real
protected endpoint (none exists yet; Part C is infrastructure-only).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from src.core.authorization import require_role, verify_ownership
from src.core.exceptions import Forbidden
from src.domains.auth.models import User, UserRole


def _make_user(role: UserRole, user_id: uuid.UUID | None = None) -> User:
    user = User(email="u@example.com", role=role, full_name="Test User")
    user.id = user_id or uuid.uuid4()
    return user


def test_require_role_allows_matching_role() -> None:
    dependency = require_role(UserRole.RECRUITER)
    user = _make_user(UserRole.RECRUITER)
    assert dependency(user=user) is user


def test_require_role_allows_any_of_multiple_roles() -> None:
    dependency = require_role(UserRole.RECRUITER, UserRole.ADMIN)
    assert dependency(user=_make_user(UserRole.ADMIN)) is not None


def test_require_role_rejects_mismatched_role() -> None:
    dependency = require_role(UserRole.RECRUITER)
    candidate = _make_user(UserRole.CANDIDATE)

    with pytest.raises(HTTPException) as exc_info:
        dependency(user=candidate)

    assert exc_info.value.status_code == 403


def test_verify_ownership_allows_owner() -> None:
    user = _make_user(UserRole.CANDIDATE)
    verify_ownership(resource_owner_id=user.id, current_user=user)  # no raise


def test_verify_ownership_allows_admin_regardless_of_owner() -> None:
    admin = _make_user(UserRole.ADMIN)
    verify_ownership(resource_owner_id=uuid.uuid4(), current_user=admin)  # no raise


def test_verify_ownership_rejects_non_owner() -> None:
    candidate_a = _make_user(UserRole.CANDIDATE)
    other_candidates_resource_id = uuid.uuid4()

    with pytest.raises(Forbidden) as exc_info:
        verify_ownership(resource_owner_id=other_candidates_resource_id, current_user=candidate_a)

    assert exc_info.value.status_code == 403
