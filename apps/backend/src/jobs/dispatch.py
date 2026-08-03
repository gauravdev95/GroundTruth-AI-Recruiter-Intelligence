"""Creates the durable `async_jobs` row and hands the work to Celery.

The row is committed **before** the task is published. If the order were
reversed a fast worker could pick the task up before the row it needs exists,
and a broker failure would leave the UI polling a job id that was never
persisted. Committing first means the worst case is an orphaned PENDING row —
visible, retryable, and far better than a task with no status record.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.orm import Session

from src.core.request_id import get_request_id
from src.platform.models import AsyncJob, AsyncJobStatus

logger = structlog.get_logger(__name__)


def create_job(db: Session, *, job_type: str, payload: dict[str, Any]) -> AsyncJob:
    """Persist a queued job. Commits so the row is visible to the worker."""
    job = AsyncJob(job_type=job_type, status=AsyncJobStatus.PENDING, payload=payload)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def dispatch(job: AsyncJob, task: Any, *, queue: str, args: list[Any] | None = None) -> None:
    """Publish a task for an already-persisted job.

    A publish failure is logged rather than raised: the HTTP request that
    created the job has already succeeded from the user's point of view, and
    the row remains PENDING for a sweeper or manual requeue to pick up. Raising
    here would fail a request whose durable side effect already landed.

    The dispatching request's id (if any — a Celery beat/retry/dead-letter
    republish has none) rides along as a Celery message header, so
    `celery_app.py`'s `task_prerun`/`task_postrun` hooks can bind it into the
    worker's own structlog context. That is what makes the API log line that
    created a job and every worker log line that processed it share one
    `request_id`, without changing any task's signature.
    """
    try:
        # `retry=False` is load-bearing: with Celery's default retry policy a
        # publish to an unreachable broker blocks for tens of seconds inside
        # the request. Failing fast and leaving the row PENDING is strictly
        # better than a hung HTTP call.
        task.apply_async(
            args=[str(job.id), *(args or [])],
            queue=queue,
            retry=False,
            headers={"request_id": get_request_id()},
        )
    except Exception as exc:  # noqa: BLE001 — broker faults must not fail the request
        logger.error(
            "job_dispatch_failed",
            async_job_id=str(job.id),
            job_type=job.job_type,
            error=str(exc),
        )


def get_job(db: Session, job_id: uuid.UUID) -> AsyncJob | None:
    return db.get(AsyncJob, job_id)
