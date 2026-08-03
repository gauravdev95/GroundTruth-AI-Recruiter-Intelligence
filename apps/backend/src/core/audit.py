"""Activates `audit_log` — zero write sites before this module
(`PROGRESS.md` §2.6). One function, called from every state-changing action
that matters for compliance/security review, per the table's own design
note in `docs/DATA_MODEL.md` §7.

`write_audit_log` never commits — it `add()`s the row into the caller's
existing transaction, so an audit entry and the state change it records
land atomically (either both happen or neither does), and never leaves an
audit row for a change that then failed to commit.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from src.platform.models import AuditLog


def write_audit_log(
    db: Session,
    *,
    actor_user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """`actor_user_id=None` means a system action (a Celery task, not a
    request) — `AuditLog.actor_user_id` is nullable exactly for this."""
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            ip_address=ip_address,
        )
    )
