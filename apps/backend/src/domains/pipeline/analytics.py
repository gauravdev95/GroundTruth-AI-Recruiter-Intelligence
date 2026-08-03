"""Read-only analytics over the marketplace loop's own tables — nothing
here is precomputed or cached; every number is a straight aggregate query,
since these are dashboard-load-frequency reads, not per-request hot paths.

"Time to first response" is answered from `audit_log`, not a dedicated
timestamp column — the first `application.status_changed` row for an
application (`created_at`) minus `Application.applied_at`, which is exactly
what activating `audit_log` for stage transitions buys for free.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.domains.auth.models import CandidateProfile, RecruiterProfile
from src.domains.matching.models import MatchResult
from src.domains.pipeline.models import Application, ApplicationStatus
from src.domains.recruiter.models import JobPosting
from src.platform.models import AuditLog


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def recruiter_funnel(db: Session, recruiter: RecruiterProfile) -> dict:
    job_ids = list(
        db.execute(
            select(JobPosting.id).where(JobPosting.created_by_user_id == recruiter.user_id)
        ).scalars()
    )
    counts = {status.value: 0 for status in ApplicationStatus}
    if not job_ids:
        return {"stage_counts": counts, "conversion": {}, "avg_time_to_first_response_hours": None}

    rows = db.execute(
        select(Application.status, func.count())
        .where(Application.job_posting_id.in_(job_ids))
        .group_by(Application.status)
    ).all()
    for status, count in rows:
        counts[status.value] = count

    total_applied = sum(counts.values())
    conversion: dict[str, float | None] = {}

    # Cumulative funnel: how many applications ever reached at least this
    # stage. Since the forward path is linear (APPLIED -> SHORTLISTED ->
    # INTERVIEW_SCHEDULED -> HIRED, with REJECTED a side-exit from any of
    # them), "reached at least X" = currently at X, further along, or hired
    # — everything except REJECTED-before-X and APPLIED-only-below-X.
    order = [
        ApplicationStatus.APPLIED,
        ApplicationStatus.SHORTLISTED,
        ApplicationStatus.INTERVIEW_SCHEDULED,
        ApplicationStatus.HIRED,
    ]
    # Applications currently sitting at REJECTED don't reveal which stage
    # they were rejected from without replaying audit_log; the funnel below
    # is therefore reported over non-rejected applications' current stage,
    # which undercounts stages a since-rejected application briefly reached.
    # Documented limitation rather than a full audit-log replay, in the
    # interest of one cheap query over an exact historical one.
    reached_at_least = {}
    non_rejected_total = sum(counts[s.value] for s in order)
    running = non_rejected_total
    for status in order:
        reached_at_least[status.value] = running
        running -= counts[status.value]

    for i in range(len(order) - 1):
        current, nxt = order[i], order[i + 1]
        base = reached_at_least[current.value]
        conversion[f"{current.value}_to_{nxt.value}"] = (
            round(reached_at_least[nxt.value] / base, 4) if base else None
        )

    # One query per application here would be an N+1 against `audit_log` —
    # `DISTINCT ON` gets every application's earliest qualifying audit row
    # in a single query instead (the classic Postgres "first row per group").
    applied_at_by_id = {
        application_id: applied_at
        for application_id, applied_at in db.execute(
            select(Application.id, Application.applied_at).where(
                Application.job_posting_id.in_(job_ids), Application.status != ApplicationStatus.APPLIED
            )
        ).all()
    }

    first_response_deltas = []
    if applied_at_by_id:
        first_change_rows = db.execute(
            select(AuditLog.entity_id, AuditLog.created_at)
            .distinct(AuditLog.entity_id)
            .where(
                AuditLog.entity_type == "application",
                AuditLog.entity_id.in_(applied_at_by_id.keys()),
                AuditLog.action.in_(("application.status_changed", "application.hired")),
            )
            .order_by(AuditLog.entity_id, AuditLog.created_at)
        ).all()
        for entity_id, first_change in first_change_rows:
            applied_at = applied_at_by_id[entity_id]
            first_response_deltas.append((first_change - applied_at).total_seconds() / 3600)

    avg_response_hours = round(sum(first_response_deltas) / len(first_response_deltas), 2) if first_response_deltas else None

    return {
        "stage_counts": counts,
        "total_applications": total_applied,
        "conversion": conversion,
        "avg_time_to_first_response_hours": avg_response_hours,
    }


def student_summary(db: Session, profile: CandidateProfile) -> dict:
    match_count = db.execute(
        select(func.count()).select_from(MatchResult).where(MatchResult.candidate_profile_id == profile.id)
    ).scalar_one()

    profile_views = db.execute(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.entity_type == "candidate_profile", AuditLog.entity_id == profile.id, AuditLog.action == "candidate_profile.viewed")
    ).scalar_one()

    outcome_rows = db.execute(
        select(Application.status, func.count())
        .where(Application.candidate_profile_id == profile.id)
        .group_by(Application.status)
    ).all()
    outcomes = {status.value: 0 for status in ApplicationStatus}
    for status, count in outcome_rows:
        outcomes[status.value] = count

    return {
        "match_count": match_count,
        "profile_views": profile_views,
        "application_outcomes": outcomes,
    }
