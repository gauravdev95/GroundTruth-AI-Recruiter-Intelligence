"""Unit tests for the generic cursor-pagination primitives in core/pagination.py."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.core.exceptions import ValidationFailed
from src.core.pagination import Page, decode_cursor, encode_cursor


def test_cursor_round_trips() -> None:
    created_at = datetime(2026, 1, 15, 12, 30, tzinfo=timezone.utc)
    id_ = uuid.uuid4()

    cursor = encode_cursor(created_at=created_at, id=id_)
    decoded_created_at, decoded_id = decode_cursor(cursor)

    assert decoded_created_at == created_at
    assert decoded_id == id_


def test_cursor_is_opaque_and_url_safe() -> None:
    cursor = encode_cursor(created_at=datetime.now(timezone.utc), id=uuid.uuid4())
    assert "/" not in cursor
    assert "+" not in cursor


def test_decode_cursor_rejects_garbage() -> None:
    with pytest.raises(ValidationFailed):
        decode_cursor("not-a-valid-cursor")


def test_decode_cursor_rejects_well_formed_but_wrong_shape() -> None:
    import base64
    import json

    bogus = base64.urlsafe_b64encode(json.dumps({"unexpected": "shape"}).encode()).decode()
    with pytest.raises(ValidationFailed):
        decode_cursor(bogus)


def test_page_model_defaults() -> None:
    page: Page[int] = Page(items=[1, 2, 3])
    assert page.next_cursor is None
    assert page.has_more is False


def test_page_model_with_cursor() -> None:
    page: Page[str] = Page(items=["a"], next_cursor="abc", has_more=True)
    assert page.next_cursor == "abc"
    assert page.has_more is True
