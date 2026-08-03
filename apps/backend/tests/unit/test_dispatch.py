"""Unit tests for `jobs/dispatch.py::dispatch` — specifically that it
carries the current request id into the Celery message headers, which is
what lets a worker correlate its own log lines back to the HTTP request
that triggered the job (see `celery_app.py`'s `_bind_request_id`).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.jobs import dispatch as dispatch_module
from src.platform.models import AsyncJob, AsyncJobStatus


def _fake_job() -> AsyncJob:
    job = AsyncJob(job_type="extract_resume", status=AsyncJobStatus.PENDING, payload={})
    job.id = "11111111-1111-1111-1111-111111111111"  # type: ignore[assignment]
    return job


def test_dispatch_carries_the_current_request_id_as_a_message_header(monkeypatch) -> None:
    monkeypatch.setattr(dispatch_module, "get_request_id", lambda: "req-abc-123")
    task = MagicMock()
    job = _fake_job()

    dispatch_module.dispatch(job, task, queue="extraction")

    task.apply_async.assert_called_once()
    _, kwargs = task.apply_async.call_args
    assert kwargs["headers"] == {"request_id": "req-abc-123"}


def test_dispatch_sends_a_null_request_id_outside_a_request_lifecycle(monkeypatch) -> None:
    monkeypatch.setattr(dispatch_module, "get_request_id", lambda: None)
    task = MagicMock()
    job = _fake_job()

    dispatch_module.dispatch(job, task, queue="matching")

    _, kwargs = task.apply_async.call_args
    assert kwargs["headers"] == {"request_id": None}
