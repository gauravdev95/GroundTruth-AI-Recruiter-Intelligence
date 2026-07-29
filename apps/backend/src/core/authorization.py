"""Generic authorization helpers usable by any domain.

`require_role` already lives in `domains/auth/dependencies.py` — it only
depends on `User`/`UserRole`, so it's already domain-agnostic; re-exported
here so future domains have one place to import authorization primitives
from without reaching into `domains.auth`.
"""

from __future__ import annotations

import uuid

from src.core.exceptions import Forbidden
from src.domains.auth.dependencies import require_role
from src.domains.auth.models import User, UserRole

__all__ = ["require_role", "verify_ownership"]


def verify_ownership(*, resource_owner_id: uuid.UUID, current_user: User) -> None:
    """Raise `Forbidden` (403) unless `current_user` owns the resource.

    Admins bypass ownership checks. Deliberately 403, not 404 — per the
    acceptance criteria, a candidate requesting another candidate's
    resource must get "forbidden", not "not found" (which would leak
    whether the resource exists).
    """
    if current_user.role == UserRole.ADMIN:
        return
    if current_user.id != resource_owner_id:
        raise Forbidden()
