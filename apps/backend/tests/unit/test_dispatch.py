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
    # Fix 2: the fire-and-forget publish must also skip the Celery result
    # backend, or a dead broker burns ~19 s per publish in the
    # result-consumer reconnect loop before the publish even runs.
    assert failing.apply_async.call_args.kwargs["ignore_result"] is True


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


# --- Fix 2 regression tests (16 Nov 2026, FIX2_STALL_REPORT.md) ------------
# With the default ignore_result=False, Celery's send_task calls
# backend.on_task_call() BEFORE the broker publish, subscribing the Redis
# result consumer; when Redis is down that subscribe burns ~19 s per publish
# in the reconnect loop (retry_policy max_retries=20 x 1 s) inside the HTTP
# request. dispatch() is fire-and-forget — job status lives in the
# async_jobs table — so it must pass ignore_result=True. The wall-time proof
# is the local UP/DOWN/UP run (FIX2_PATCH_REPORT.md); these tests pin the
# mechanism (the flag is passed, every other argument preserved) and that
# the worker-side completion tracking it replaces nothing of still works.


def test_dispatch_passes_ignore_result_true(monkeypatch) -> None:
    """(a) The publish call skips the Celery result backend; all other
    arguments are preserved exactly."""
    monkeypatch.setattr(dispatch_module, "get_request_id", lambda: "req-fix2-1")
    task = MagicMock()
    job = _fake_job()

    dispatch_module.dispatch(job, task, queue="verification", args=["extra"])

    task.apply_async.assert_called_once()
    _, kwargs = task.apply_async.call_args
    assert kwargs["ignore_result"] is True
    assert kwargs["retry"] is False
    assert kwargs["queue"] == "verification"
    assert kwargs["args"] == [str(job.id), "extra"]
    assert kwargs["headers"] == {"request_id": "req-fix2-1"}


def test_dispatch_passes_ignore_result_true_when_broker_is_down(monkeypatch) -> None:
    """(a) With the broker down, dispatch still passes the flag and does not
    raise — the fast failure path, not the ~19 s drainer loop."""
    logger = MagicMock()
    monkeypatch.setattr(dispatch_module, "logger", logger)
    ref = _JobRefWithoutJobType(uuid.uuid4())

    dispatch_module.dispatch(ref, _failing_task(), queue="verification")  # must not raise

    logger.error.assert_called_once()
    _, kwargs = logger.error.call_args
    assert kwargs["job_type"] == "unknown"


class _FakeSession:
    """Minimal stand-in for a SQLAlchemy session for DatabaseTask tests."""

    def __init__(self, job) -> None:
        self.job = job
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def get(self, _model: object, _key: object):
        return self.job

    def commit(self) -> None:
        self.committed = True


def _fake_db_task(monkeypatch, job):
    """A DatabaseTask wired to a fake session; returns (task, session)."""
    from types import SimpleNamespace

    from src.jobs import celery_app as celery_app_module
    from src.jobs.celery_app import DatabaseTask

    session = _FakeSession(job)
    monkeypatch.setattr(celery_app_module, "SessionLocal", lambda: session)
    task = DatabaseTask()
    task.name = "src.jobs.tasks.verification.verify_github_account_task"
    return task, session


def test_database_task_on_success_marks_job_succeeded(monkeypatch) -> None:
    """(b) on_success still fires with ignore_result=True: the row reaches
    SUCCEEDED with the result stored — completion tracking is the Postgres
    row, not the Celery result backend."""
    from types import SimpleNamespace

    job = SimpleNamespace(status=None, result=None, error=None, finished_at=None)
    task, session = _fake_db_task(monkeypatch, job)

    task.on_success({"verified": True}, "task-id-1", (str(uuid.uuid4()),), {})

    assert job.status == AsyncJobStatus.SUCCEEDED
    assert job.result == {"verified": True}
    assert job.error is None
    assert job.finished_at is not None
    assert session.committed is True


def test_database_task_on_failure_marks_job_failed_and_dead_letters(monkeypatch) -> None:
    """(b) on_failure still fires with ignore_result=True: the row reaches
    FAILED with the error recorded, and the dead-letter publish runs."""
    from types import SimpleNamespace

    job = SimpleNamespace(status=None, result=None, error=None, finished_at=None)
    task, session = _fake_db_task(monkeypatch, job)
    dead_letter_stub = types.ModuleType("src.jobs.tasks.dead_letter")
    dead_letter_stub.record_dead_letter = MagicMock()
    monkeypatch.setitem(sys.modules, "src.jobs.tasks.dead_letter", dead_letter_stub)
    job_id = str(uuid.uuid4())

    task.on_failure(RuntimeError("boom"), "task-id-2", (job_id,), {}, None)

    assert job.status == AsyncJobStatus.FAILED
    assert job.error == "RuntimeError: boom"
    assert job.finished_at is not None
    assert session.committed is True
    dead_letter_stub.record_dead_letter.apply_async.assert_called_once()
    _dl_args, dl_kwargs = dead_letter_stub.record_dead_letter.apply_async.call_args
    assert dl_kwargs["args"][0] == job_id
    assert dl_kwargs["queue"] == "dead_letter"


def test_database_task_autoretry_policy_preserved(monkeypatch) -> None:
    """(b) Retries are unchanged by the flag: transient failures still
    autoretry with backoff, deterministic ones still skip it, and on_retry
    keeps the row PENDING with the error recorded."""
    from types import SimpleNamespace

    from src.config.config import get_celery_settings
    from src.jobs.celery_app import DatabaseTask, NonRetryableJobError

    settings = get_celery_settings()
    assert DatabaseTask.autoretry_for == (Exception,)
    assert DatabaseTask.dont_autoretry_for == (NonRetryableJobError,)
    assert DatabaseTask.max_retries == settings.job_max_retries
    assert DatabaseTask.retry_backoff == settings.job_retry_backoff_base_seconds
    assert DatabaseTask.retry_backoff_max == settings.job_retry_backoff_max_seconds

    job = SimpleNamespace(status=None, result=None, error=None, finished_at=None)
    task, session = _fake_db_task(monkeypatch, job)
    job_id = str(uuid.uuid4())

    task.on_retry(ConnectionError("flaky"), "task-id-3", (job_id,), {}, None)

    assert job.status == AsyncJobStatus.PENDING
    assert job.error == "ConnectionError: flaky"
    assert session.committed is True
