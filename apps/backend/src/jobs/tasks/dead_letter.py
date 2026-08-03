"""Dead-letter handling for jobs that exhausted their retries.

A dead-lettered job is *not* deleted or hidden: the `async_jobs` row keeps its
payload, error, and attempt count, and gains `dead_lettered_at`. That makes the
queue a queryable view (`status = 'failed' AND dead_lettered_at IS NOT NULL`)
rather than a black hole, so a failure can be inspected and requeued after the
underlying cause is fixed.

This task runs on its own queue so that recording a failure never queues behind
the backlog of slow work that caused it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from src.db.database import SessionLocal
from src.jobs.celery_app import QUEUE_DEAD_LETTER, celery_app
from src.platform.models import AsyncJob, AsyncJobStatus

logger = structlog.get_logger(__name__)


@celery_app.task(name="src.jobs.tasks.dead_letter.record_dead_letter", queue=QUEUE_DEAD_LETTER)
def record_dead_letter(async_job_id: str, task_name: str, error: str) -> dict[str, str]:
    """Stamp a failed job as dead-lettered.

    Deliberately a plain task, not a `DatabaseTask`: it must not recurse into
    the failure handler that published it.
    """
    with SessionLocal() as session:
        job = session.get(AsyncJob, uuid.UUID(async_job_id))
        if job is None:
            logger.warning("dead_letter_job_missing", async_job_id=async_job_id)
            return {"status": "missing"}

        job.dead_lettered_at = datetime.now(timezone.utc)
        job.status = AsyncJobStatus.FAILED
        job.error = error
        session.commit()

    logger.error("job_dead_lettered", async_job_id=async_job_id, task=task_name, error=error)
    return {"status": "recorded", "async_job_id": async_job_id}


def requeue_dead_lettered(async_job_id: uuid.UUID, *, db: Session | None = None) -> bool:
    """Reset a dead-lettered job so it can be dispatched again.

    Clears the terminal state and the attempt counter; the caller re-publishes
    the task. Used both as an operator/script action (no `db` passed — opens
    and commits its own session) and by `jobs/router.py`'s ownership-scoped
    `POST /api/v1/jobs/{id}/retry` (passes the request's own `db`, so the
    reset lands in the same transaction the endpoint already authorized).
    """
    if db is not None:
        job = db.get(AsyncJob, async_job_id)
        if job is None or job.dead_lettered_at is None:
            return False
        job.status = AsyncJobStatus.PENDING
        job.dead_lettered_at = None
        job.error = None
        job.attempts = 0
        job.started_at = None
        job.finished_at = None
        db.commit()
        return True

    with SessionLocal() as session:
        job = session.get(AsyncJob, async_job_id)
        if job is None or job.dead_lettered_at is None:
            return False
        job.status = AsyncJobStatus.PENDING
        job.dead_lettered_at = None
        job.error = None
        job.attempts = 0
        job.started_at = None
        job.finished_at = None
        session.commit()
    return True
