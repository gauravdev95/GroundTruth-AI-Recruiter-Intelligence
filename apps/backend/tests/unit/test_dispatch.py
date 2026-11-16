"""Unit tests for `jobs/dispatch.py::dispatch` — specifically that it
carries the current request id into the Celery message headers, which is
what lets a worker correlate its own log lines back to the HTTP request
that triggered the job (see `celery_app.py`'s `_bind_request_id`).

Regression tests (16 Nov 2026, Fix 1 — LOCAL_500_REPRO_REPORT.md): the
failure path of `dispatch()` logged `job_type=job.job_type`, but the
`evidence.dispatch_all()` caller passes a duck-type stand-in
(`_AsyncJobRef`) that defines only `.id`. When the broker was down, the
`logger.error(...)` call itself raised
`AttributeError: '_AsyncJobRef' object has no attribute 'job_type'`,
turning the profile save into a 500 AFTER the row had committed.
`dispatch()` must never raise, whatever job-like object it is handed.
"""

from __future__ import annotations

import sys
import types
import uuid
from unittest.mock import MagicMock

from kombu.exceptions import OperationalError

from src.domains.student.evidence import QueuedVerification, dispatch_all
from src.jobs import dispatch as dispatch_module
from src.platform.models import AsyncJob, AsyncJobStatus


class _JobRefWithoutJobType:
    """Mirrors `evidence._AsyncJobRef`: only `.id`, no `.job_type`."""

    def __init__(self, job_id: uuid.UUID) -> None:
        self.id = job_id


def _failing_task() -> MagicMock:
    task = MagicMock()
    task.apply_async.side_effect = OperationalError("Error 111 connecting to localhost:6379. Connection refused.")
    return task


def test_dispatch_does_not_raise_when_job_has_no_job_type_and_broker_is_down(monkeypatch) -> None:
    """(a) The Fix 1 regression: _AsyncJobRef + broker OperationalError.

    Before the fix this raised AttributeError from inside the error-logging
    call; now dispatch must swallow the publish failure and log with
    job_type="unknown".
    """
    logger = MagicMock()
    monkeypatch.setattr(dispatch_module, "logger", logger)
    ref = _JobRefWithoutJobType(uuid.uuid4())

    # Must NOT raise — this is the whole point of the fix.
    dispatch_module.dispatch(ref, _failing_task(), queue="verification")

    logger.error.assert_called_once()
    _, kwargs = logger.error.call_args
    assert kwargs["job_type"] == "unknown"
    assert str(kwargs["async_job_id"]) == str(ref.id)


def test_dispatch_does_not_raise_when_logging_itself_fails(monkeypatch) -> None:
    """Guardrail: even a failure inside the error-logging call must not
    escape dispatch(). The PENDING row is the durable signal; a logging
    failure must never fail the request."""
    logger = MagicMock()
    logger.error.side_effect = RuntimeError("logging subsystem broken")
    monkeypatch.setattr(dispatch_module, "logger", logger)
    ref = _JobRefWithoutJobType(uuid.uuid4())

    dispatch_module.dispatch(ref, _failing_task(), queue="verification")  # must not raise

    logger.error.assert_called_once()


def test_dispatch_keeps_real_job_type_in_the_failure_log(monkeypatch) -> None:
    """(b) A normal AsyncJob still logs its real job_type on publish failure."""
    logger = MagicMock()
    monkeypatch.setattr(dispatch_module, "logger", logger)
    job = _fake_job()

    dispatch_module.dispatch(job, _failing_task(), queue="extraction")

    logger.error.assert_called_once()
    _, kwargs = logger.error.call_args
    assert kwargs["job_type"] == "extract_resume"
    assert str(kwargs["async_job_id"]) == str(job.id)


def test_dispatch_all_does_not_raise_when_broker_is_down(monkeypatch) -> None:
    """(c) A dispatch failure after DB commit must not turn the API call
    into a 500. `evidence.dispatch_all` (the `_finalize` post-commit path)
    with a down broker must complete silently, leaving the job PENDING.

    The verification tasks and celery_app are stubbed at the import level
    (dispatch_all lazy-imports them) so this test needs no broker.
    """
    failing = _failing_task()
    verification_stub = types.ModuleType("src.jobs.tasks.verification")
    for name in (
        "verify_github_account_task",
        "verify_coding_platform_account_task",
        "verify_repository_task",
        "verify_certificate_task",
        "verify_experience_task",
    ):
        setattr(verification_stub, name, failing)
    celery_app_stub = types.ModuleType("src.jobs.celery_app")
    celery_app_stub.QUEUE_VERIFICATION = "verification"
    monkeypatch.setitem(sys.modules, "src.jobs.tasks.verification", verification_stub)
    monkeypatch.setitem(sys.modules, "src.jobs.celery_app", celery_app_stub)

    queued = [
        QueuedVerification(
            async_job_id=uuid.uuid4(),
            job_type="verify_github_account",
            source_type="github_account",
            source_id=uuid.uuid4(),
        )
    ]

    # Must NOT raise — before Fix 1 this raised AttributeError, which
    # propagated out of _finalize() as a 500 after the commit.
    dispatch_all(queued)

    failing.apply_async.assert_called_once()


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
