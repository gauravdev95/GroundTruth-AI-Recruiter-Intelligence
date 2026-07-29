"""Generic cursor (keyset) pagination.

Every table has `created_at` + `id` via the shared mixins (`TimestampMixin`
+ `UUIDPrimaryKeyMixin`), so a cursor is always `(created_at, id)` — no
bespoke offset math per endpoint, and no "page drift" when rows are
inserted between requests (offset pagination's classic failure mode).

Usage in a future list endpoint:

    after = decode_cursor(query_param) if query_param else None
    rows = (
        select(Model)
        .where(tuple_(Model.created_at, Model.id) < after if after else True)
        .order_by(Model.created_at.desc(), Model.id.desc())
        .limit(limit + 1)
    )
    # take `limit` rows, use the (limit+1)th's existence as `has_more`,
    # encode_cursor(created_at=last.created_at, id=last.id) as next_cursor
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel

from src.core.exceptions import ValidationFailed

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False


def encode_cursor(*, created_at: datetime, id: uuid.UUID) -> str:  # noqa: A002
    raw = json.dumps({"created_at": created_at.isoformat(), "id": str(id)})
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        data = json.loads(raw)
        return datetime.fromisoformat(data["created_at"]), uuid.UUID(data["id"])
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ValidationFailed("Invalid pagination cursor") from exc
