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
from src.domains.auth.models import CandidateProfile, RecruiterProfile
from src.domains.matching import embeddings, service as matching_service, tiers
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

    **And only Tier B pairs**, per `domains/matching/tiers.py`. A Tier A pair
    is discoverable: it sits on the recruiter's board and in the student's
    feed, where the student finds it when they go looking. Interrupting them
    with a push and an email is reserved for a match strong enough to be
    worth acting on now, because a notification stream that fires on every
    50%-and-up pair is one the student turns off — after which Tier B cannot
    reach them either.

    The cutoff is per job and depends on that job's whole pool, so it is
    resolved once per job here rather than once per pair.

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

    job_ids = {pair.job_posting_id for pair in result.newly_matched}
    job_titles = dict(
        session.execute(select(JobPosting.id, JobPosting.title).where(JobPosting.id.in_(job_ids))).all()
    )
    cutoffs = {
        job_id: tiers.tier_b_cutoff(matching_service.pool_scores_for_job(session, job_id))
        for job_id in job_ids
    }

    recommended = [
        pair
        for pair in result.newly_matched
        if tiers.resolve_tier(pair.match_score, cutoff_b=cutoffs[pair.job_posting_id])
        is tiers.MatchTier.SMART_APPLY_RECOMMENDED
    ]

    emitted = notifications.notify_new_matches(
        session,
        matches=[
            (
                pair.candidate_profile_id,
                job_titles.get(pair.job_posting_id, "a new role"),
                pair.match_score,
            )
            for pair in recommended
        ],
    )
    session.commit()

    # After the commit, and never blocking on the result: `publish_to_user`
    # swallows Redis failures by design, so a broker outage costs live push
    # and nothing else — the rows are already safe.
    pushed = realtime.publish_many(emitted, type_=NotificationType.NEW_MATCH)

    # The recruiter half. Separate from the student notification above and
    # deliberately *not* a `Notification` row: a recruiter watching their
    # board wants the new card to appear, not an inbox entry per candidate on
    # a job that may match two hundred of them. This is a live-board hint with
    # no durable counterpart, which is why it carries no payload beyond the
    # job — the board refetches from the server, exactly as
    # `useRealtimeEvents` does on the student side.
    #
    # Fired for Tier A as well as Tier B: the recruiter's "Matched" column is
    # the Tier A surface, so restricting this to Tier B would leave the board
    # stale for precisely the pairs it is supposed to show.
    board_pushes = _push_board_updates(session, result, cutoffs)

    logger.info(
        "new_match_notifications",
        newly_matched=len(result.newly_matched),
        recommended=len(recommended),
        written=len(emitted),
        pushed=pushed,
        board_pushes=board_pushes,
    )


def _push_board_updates(
    session, result: matching_service.RecomputeResult, cutoffs: dict[uuid.UUID, float]
) -> int:
    """One `NEW_MATCH` frame per (recruiter, job) that gained a Tier A or B
    pair — collapsed per job rather than per candidate, because the frame
    only names which board to refresh.

    Resolved through `recruiter_profiles.company_id`, so every recruiter at
    the owning company gets it, not only whoever happened to create the job.
    A job posting belongs to a company (`job_postings.company_id`); the board
    it feeds is the company's.
    """
    tiered_job_ids = {
        pair.job_posting_id
        for pair in result.newly_matched
        if tiers.resolve_tier(pair.match_score, cutoff_b=cutoffs[pair.job_posting_id]) is not None
    }
    if not tiered_job_ids:
        return 0

    rows = session.execute(
        select(JobPosting.id, RecruiterProfile.user_id)
        .join(RecruiterProfile, RecruiterProfile.company_id == JobPosting.company_id)
        .where(JobPosting.id.in_(tiered_job_ids))
    ).all()

    return sum(
        1
        for job_id, user_id in rows
        if realtime.publish_to_user(
            user_id, NotificationType.NEW_MATCH, {"job_posting_id": str(job_id), "scope": "recruiter_board"}
        )
    )


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
