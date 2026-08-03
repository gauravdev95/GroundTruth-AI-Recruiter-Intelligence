"""Unit tests for the worker-side half of request-id propagation
(`celery_app.py`'s `_bind_request_id`/`_unbind_request_id`, the counterpart
to `jobs/dispatch.py`'s producer-side header — see `test_dispatch.py`).

Exercises the signal handlers directly against structlog's own contextvar
state rather than through a live broker/worker round trip: this is what
actually determines whether a task's log lines carry `request_id`, and
testing it this way is deterministic and fast instead of depending on
which task in a live run happens to log something.
"""

from __future__ import annotations

from types import SimpleNamespace

import structlog

from src.jobs.celery_app import _bind_request_id, _unbind_request_id


def _fake_task(request_id: str | None):
    return SimpleNamespace(request=SimpleNamespace(request_id=request_id))


def test_bind_request_id_puts_it_in_the_structlog_context() -> None:
    _unbind_request_id()  # start clean regardless of test order
    _bind_request_id(task=_fake_task("req-worker-test-1"))
    try:
        assert structlog.contextvars.get_contextvars().get("request_id") == "req-worker-test-1"
    finally:
        _unbind_request_id()


def test_unbind_request_id_removes_it() -> None:
    _bind_request_id(task=_fake_task("req-worker-test-2"))
    _unbind_request_id()
    assert "request_id" not in structlog.contextvars.get_contextvars()


def test_bind_request_id_is_a_no_op_when_none() -> None:
    _unbind_request_id()
    _bind_request_id(task=_fake_task(None))
    try:
        assert "request_id" not in structlog.contextvars.get_contextvars()
    finally:
        _unbind_request_id()


def test_bind_request_id_tolerates_a_task_with_no_request(monkeypatch) -> None:
    """`task_prerun` also fires for tasks that aren't `DatabaseTask`
    instances (or in edge cases with no `.request`) — must not raise."""
    _bind_request_id(task=None)
    _bind_request_id(task=SimpleNamespace())
