"""Celery application: queue topology, retry policy, and the base task.

Queue topology
--------------

| Queue          | Consumes                                                   | Why separate                       |
|----------------|--------------------------------------------------------------|-------------------------------------|
| `extraction`   | `extract_resume_task`, the interview tasks in `jobs/tasks/interview.py`, and `extract_job_requirements_task` | Long, external LLM/network calls |
| `verification` | the five `verify_*` tasks in `jobs/tasks/verification.py`, consuming the jobs `student/evidence.py` enqueues | Third-party API calls, throttled independently of LLM work |
| `matching`     | the embed-and-match tasks in `jobs/tasks/matching.py`      | OpenAI embedding calls + the rank-fusion computation itself — neither an Anthropic call nor a third-party verification check, and potentially high-volume (one candidate re-verification can trigger matching against every published job) |
| `dead_letter`  | `record_dead_letter`                                          | Terminal failures, inspectable     |

Slow work is isolated on its own queue so a backlog of minute-long extractions
cannot head-of-line block a short verification job behind it. Interview and
job-extraction tasks share `extraction` rather than getting their own queues:
they are the same kind of work (slow, LLM-bound, externally rate-limited by
the Anthropic API), with no distinct backpressure reason to isolate them
further. `matching` gets its own queue because its volume characteristics
differ — a single candidate verification can fan out into recomputing
matches against every open job — and it must not be able to starve the
`extraction` queue's LLM work of broker throughput.

`async_jobs` — not the Celery result backend — is the durable record the UI
polls. A broker flush loses task ids; the table survives it, which is the whole
reason `docs/DATA_MODEL.md` §7 specifies it.

Retries
-------

`DatabaseTask` retries only transient failures (timeouts, connection errors,
upstream 5xx/429) with exponential backoff and jitter. Deterministic failures —
malformed LLM output, an unparseable PDF — are **not** retried: re-running them
produces the identical failure while burning quota and delaying the row's
terminal state. On exhaustion the job lands in `FAILED` and is published to the
dead-letter queue.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from celery import Celery, Task
from celery.signals import task_postrun, task_prerun

from src.config.config import get_celery_settings, get_security_settings
from src.core.logging import configure_logging
from src.db import register_models  # noqa: F401 — mapper configuration for worker processes
from src.db.database import SessionLocal
from src.platform.models import AsyncJob, AsyncJobStatus

# `main.py` configures structlog for the API process; a standalone
# `celery worker` process never imports `main.py`, so without this call it
# would run with structlog's unconfigured defaults — plain console output,
# no JSON, and critically no `merge_contextvars` processor, which would
# silently drop the `request_id` binding below from ever reaching a log
# line. Called at import time (not a `worker_process_init` signal) so it
# also covers the `solo` pool, which never spawns a separate child process
# for that signal to fire in.
configure_logging(debug=get_security_settings().app_env == "development")

logger = structlog.get_logger(__name__)

settings = get_celery_settings()

QUEUE_EXTRACTION = "extraction"
QUEUE_VERIFICATION = "verification"
QUEUE_MATCHING = "matching"
QUEUE_DEAD_LETTER = "dead_letter"

celery_app = Celery(
    "groundtruth",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    # Every module that defines a `@celery_app.task`. `include=` is what
    # makes a real `celery -A src.jobs.celery_app:celery_app worker` process
    # actually register these — without it, only whichever tasks happened to
    # be imported as a side effect of something else (e.g. a request handler
    # importing `extract_resume_task` to dispatch it) would be known to a
    # worker process, and everything else would fail with Celery's
    # "Received unregistered task" error the first time a job for it arrived.
    # `task_routes` above only tells the *producer* which queue to publish
    # to; it does not import anything.
    include=[
        "src.jobs.tasks.resume",
        "src.jobs.tasks.verification",
        "src.jobs.tasks.interview",
        "src.jobs.tasks.job_extraction",
        "src.jobs.tasks.matching",
        "src.jobs.tasks.dead_letter",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Redelivers a task if the worker dies mid-run. Safe here because every
    # task is keyed on an `async_jobs` row it re-reads before acting.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=settings.job_time_limit_seconds,
    task_soft_time_limit=settings.job_soft_time_limit_seconds,
    # Publishing happens inside an HTTP request, so a broker outage must fail
    # fast rather than hanging the caller. Kombu's defaults retry a connection
    # for a long time; these bound it to roughly a second, after which
    # `dispatch()` logs and leaves the job PENDING for a requeue.
    broker_connection_retry_on_startup=False,
    broker_transport_options={
        "max_retries": 1,
        "interval_start": 0,
        "interval_step": 0.2,
        "interval_max": 0.5,
        "socket_timeout": 2,
        "socket_connect_timeout": 2,
    },
    task_default_queue=QUEUE_EXTRACTION,
    task_routes={
        "src.jobs.tasks.resume.*": {"queue": QUEUE_EXTRACTION},
        "src.jobs.tasks.interview.*": {"queue": QUEUE_EXTRACTION},
        "src.jobs.tasks.job_extraction.*": {"queue": QUEUE_EXTRACTION},
        "src.jobs.tasks.dead_letter.*": {"queue": QUEUE_DEAD_LETTER},
        "src.jobs.tasks.verification.*": {"queue": QUEUE_VERIFICATION},
        "src.jobs.tasks.matching.*": {"queue": QUEUE_MATCHING},
    },
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NonRetryableJobError(Exception):
    """A failure that re-running cannot fix.

    Malformed LLM output, an unparseable or encrypted file, a missing row.
    Raising this skips the backoff ladder and fails the job immediately.
    """


class DatabaseTask(Task):
    """Base task that keeps the `async_jobs` row in step with the run.

    Every task in this package takes `async_job_id` as its first argument;
    that row is the durable status the UI polls, so it is updated on start,
    success, retry, and terminal failure.
    """

    autoretry_for = (Exception,)
    # Celery computes delay = retry_backoff * 2**(retries), then applies jitter.
    retry_backoff = settings.job_retry_backoff_base_seconds
    retry_backoff_max = settings.job_retry_backoff_max_seconds
    retry_jitter = True
    max_retries = settings.job_max_retries
    # Deterministic failures bypass autoretry entirely.
    dont_autoretry_for = (NonRetryableJobError,)

    def _update_job(self, async_job_id: str, **fields: Any) -> None:
        """Write job state in its own session.

        Deliberately not the task's business-logic session: that one may be
        rolling back precisely because the task failed, and the status write
        must survive it.
        """
        with SessionLocal() as session:
            job = session.get(AsyncJob, uuid.UUID(async_job_id))
            if job is None:
                logger.warning("async_job_missing", async_job_id=async_job_id)
                return
            for key, value in fields.items():
                setattr(job, key, value)
            session.commit()

    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        async_job_id = args[0] if args else kwargs.get("async_job_id")
        if async_job_id:
            self._update_job(
                str(async_job_id),
                status=AsyncJobStatus.SUCCEEDED,
                result=retval if isinstance(retval, dict) else {"value": retval},
                error=None,
                finished_at=_utcnow(),
            )

    def on_retry(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        async_job_id = args[0] if args else kwargs.get("async_job_id")
        if async_job_id:
            self._update_job(
                str(async_job_id),
                status=AsyncJobStatus.PENDING,
                error=f"{type(exc).__name__}: {exc}",
            )

    def on_failure(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        """Terminal failure: mark FAILED and dead-letter the job."""
        async_job_id = args[0] if args else kwargs.get("async_job_id")
        if not async_job_id:
            return

        self._update_job(
            str(async_job_id),
            status=AsyncJobStatus.FAILED,
            error=f"{type(exc).__name__}: {exc}",
            finished_at=_utcnow(),
        )
        logger.error(
            "job_failed_terminal",
            async_job_id=str(async_job_id),
            task=self.name,
            error=str(exc),
        )

        # Imported here rather than at module scope: the tasks module imports
        # this one for `DatabaseTask`, so a top-level import would cycle.
        from src.jobs.tasks.dead_letter import record_dead_letter

        record_dead_letter.apply_async(
            args=[str(async_job_id), self.name, f"{type(exc).__name__}: {exc}"],
            queue=QUEUE_DEAD_LETTER,
        )


@task_prerun.connect
def _mark_job_running(task_id: str | None = None, task: Task | None = None, args: tuple = (), **_: Any) -> None:
    """Flip the row to RUNNING and count the attempt as the run begins."""
    if not isinstance(task, DatabaseTask) or not args:
        return

    with SessionLocal() as session:
        job = session.get(AsyncJob, uuid.UUID(str(args[0])))
        if job is None:
            return
        job.status = AsyncJobStatus.RUNNING
        job.attempts += 1
        job.celery_task_id = task_id
        if job.started_at is None:
            job.started_at = _utcnow()
        session.commit()


@task_prerun.connect
def _bind_request_id(task: Task | None = None, **_: Any) -> None:
    """Carries the HTTP request id that triggered this job (set by
    `jobs/dispatch.py`'s `headers={"request_id": ...}`) into the worker's own
    structlog context, so every log line this task emits — including ones
    from `_mark_job_running` above and any task-specific logging — can be
    correlated back to the API request that caused it. `None` for work with
    no originating request (a retry republish, a scheduled sweep); binding
    `None` is harmless and just omits the key from log output.
    """
    request_id = getattr(getattr(task, "request", None), "request_id", None) if task is not None else None
    if request_id:
        structlog.contextvars.bind_contextvars(request_id=request_id)


@task_postrun.connect
def _unbind_request_id(**_: Any) -> None:
    structlog.contextvars.unbind_contextvars("request_id")
