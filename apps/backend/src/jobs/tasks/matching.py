"""Embed-and-match — the two triggers named in the task: a profile becoming
(re-)verified, and a job's requirements being confirmed/re-confirmed.

Both tasks do the same two steps in order: (1) call the embedding service
to refresh this entity's vector, (2) recompute that entity's half of
`match_results`. Splitting embedding from matching into two separate tasks
was considered and rejected — a stale embedding computing "fresh" matches
against it is a worse bug than the two steps not being independently
retryable, and `domains/matching/service.py`'s recompute functions are cheap
relative to the embedding API call anyway.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select

from src.db.database import SessionLocal
from src.domains.ai.exceptions import LLMMalformedOutput, LLMNotConfigured, LLMRefused
from src.domains.auth.models import CandidateProfile
from src.domains.matching import embeddings, service as matching_service
from src.domains.pipeline import notifications
from src.domains.pipeline.models import NotificationType
from src.domains.recruiter.models import JobPosting
from src.domains.student import service as student_service
from src.jobs.celery_app import DatabaseTask, NonRetryableJobError, celery_app
from src.platform.models import AsyncJob
from src import realtime

logger = structlog.get_logger(__name__)

_DETERMINISTIC_ERRORS = (LLMMalformedOutput, LLMRefused, LLMNotConfigured)


def _load_payload(async_job_id: str) -> dict:
    with SessionLocal() as session:
        job = session.get(AsyncJob, uuid.UUID(async_job_id))
        if job is None or not job.payload:
            raise NonRetryableJobError(f"Job {async_job_id} has no payload")
        return dict(job.payload)


def _announce_new_matches(session, result: matching_service.RecomputeResult) -> None:
    """Notifies each *newly* matched student, once the worker has finished.

    Deliberately at the end of the run, not per row: the flow requires that no
    notification is emitted before the computation completes, so a student is
    never told about a match that a later part of the same pass removes.

    Only `newly_matched` pairs produce a notification — an updated score on a
    pair the student already knows about is not news.

    The durable row is written and committed first, and only then pushed over
    the socket (`src/realtime/`). That order is the whole delivery contract:
    the row is the record and the push is a latency optimisation, so a push
    for a row that then rolled back would be a notification the student was
    shown and can never find. `notify_new_matches` returns exactly the
    `(user_id, payload)` pairs it persisted so the emit re-derives nothing —
    the socket and the inbox cannot describe different matches.
    """
    if not result.newly_matched:
        return

    job_titles = dict(
        session.execute(
            select(JobPosting.id, JobPosting.title).where(
                JobPosting.id.in_({pair.job_posting_id for pair in result.newly_matched})
            )
        ).all()
    )

    emitted = notifications.notify_new_matches(
        session,
        matches=[
            (
                pair.candidate_profile_id,
                job_titles.get(pair.job_posting_id, "a new role"),
                pair.match_score,
            )
            for pair in result.newly_matched
        ],
    )
    session.commit()

    # After the commit, and never blocking on the result: `publish_to_user`
    # swallows Redis failures by design, so a broker outage costs live push
    # and nothing else — the rows are already safe.
    pushed = realtime.publish_many(emitted, type_=NotificationType.NEW_MATCH)
    logger.info("new_match_notifications", written=len(emitted), pushed=pushed)


@celery_app.task(base=DatabaseTask, bind=True, name="src.jobs.tasks.matching.embed_and_match_candidate_task")
def embed_and_match_candidate_task(self: DatabaseTask, async_job_id: str) -> dict[str, str]:
    payload = _load_payload(async_job_id)
    candidate_profile_id = uuid.UUID(payload["candidate_profile_id"])

    with SessionLocal() as session:
        profile = session.get(CandidateProfile, candidate_profile_id)
        if profile is None:
            raise NonRetryableJobError(f"Candidate profile {candidate_profile_id} no longer exists")

        # Re-checked at compute time, not just at enqueue time: a student can
        # delete a mandatory field between the two. Keyed on *eligibility*
        # rather than `is_discoverable`, because `is_discoverable` requires the
        # embedding this task is about to create — testing it here would mean
        # the first run always skips and the profile is never indexed.
        if not student_service.get_completeness(session, profile).meets_section_requirements:
            matching_service.remove_matches_for_candidate(session, candidate_profile_id)
            return {"status": "skipped_not_eligible"}

        try:
            embeddings.embed_candidate_profile(session, profile)
            session.commit()
        except _DETERMINISTIC_ERRORS as exc:
            logger.warning(
                "candidate_embedding_failed_permanently",
                candidate_profile_id=str(candidate_profile_id),
                error=str(exc),
            )
            raise NonRetryableJobError(str(exc)) from exc

        # The vector now exists, which is the last condition `is_discoverable`
        # was waiting on. Persisting it here — before matching — is what makes
        # the profile visible to `_prefiltered_candidate_ids`, including the
        # `recompute_for_candidate` call on the very next line.
        completeness = student_service.recompute_and_persist_strength(
            session, candidate_profile_id, sync_matching_index=False
        )
        if completeness is None or not completeness.is_discoverable:
            return {"status": "skipped_not_discoverable"}

        session.refresh(profile)
        result = matching_service.recompute_for_candidate(session, profile)
        _announce_new_matches(session, result)

    logger.info(
        "candidate_embedded_and_matched",
        candidate_profile_id=str(candidate_profile_id),
        match_count=result.total,
        newly_matched=len(result.newly_matched),
    )
    return {"status": "matched", "match_count": str(result.total)}


@celery_app.task(base=DatabaseTask, bind=True, name="src.jobs.tasks.matching.embed_and_match_job_task")
def embed_and_match_job_task(self: DatabaseTask, async_job_id: str) -> dict[str, str]:
    payload = _load_payload(async_job_id)
    job_posting_id = uuid.UUID(payload["job_posting_id"])

    with SessionLocal() as session:
        job = session.get(JobPosting, job_posting_id)
        if job is None:
            raise NonRetryableJobError(f"Job posting {job_posting_id} no longer exists")

        try:
            embeddings.embed_job_posting(session, job)
        except _DETERMINISTIC_ERRORS as exc:
            logger.warning("job_embedding_failed_permanently", job_posting_id=str(job_posting_id), error=str(exc))
            raise NonRetryableJobError(str(exc)) from exc

        job.needs_reembedding = False
        session.commit()

        result = matching_service.recompute_for_job(session, job)
        _announce_new_matches(session, result)

    logger.info(
        "job_embedded_and_matched",
        job_posting_id=str(job_posting_id),
        match_count=result.total,
        newly_matched=len(result.newly_matched),
    )
    return {"status": "matched", "match_count": str(result.total)}
