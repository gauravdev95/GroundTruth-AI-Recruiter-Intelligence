"""Read-only analytics over the marketplace loop's own tables — nothing
here is precomputed or cached; every number is a straight aggregate query,
since these are dashboard-load-frequency reads, not per-request hot paths.

"Time to first response" is answered from `audit_log`, not a dedicated
timestamp column — the first `application.status_changed` row for an
application (`created_at`) minus `Application.applied_at`, which is exactly
what activating `audit_log` for stage transitions buys for free.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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


#: How many days of history the dashboard sparklines plot. Two weeks is
#: enough for a shape to be visible at ~120px wide without each point
#: collapsing into its neighbour.
ACTIVITY_WINDOW_DAYS = 14


def recruiter_activity(db: Session, recruiter: RecruiterProfile, *, days: int = ACTIVITY_WINDOW_DAYS) -> dict:
    """Daily counts of matches found and applications received, for this
    recruiter's jobs.

    **Exists so the dashboard's sparklines plot something real.** A trend line
    is a claim about history, and the funnel above reports only current
    totals — rendering a sparkline from those would mean inventing the shape,
    which is the one thing the product's own rules forbid a number to do
    (`domains/matching/tiers.py` on derived-never-narrated; the
    profile-strength surfaces on never showing an unmeasured percentage).
    Both series here are `count(*) group by date(created_at)` over rows that
    already exist.

    Days with no activity are emitted as zeroes rather than omitted. A
    sparkline that skips empty days compresses a quiet week into a flat line
    that looks like a busy one, which misreports the exact thing the chart is
    for.
    """
    job_ids = list(
        db.execute(
            select(JobPosting.id).where(JobPosting.created_by_user_id == recruiter.user_id)
        ).scalars()
    )

    start = (_utcnow() - timedelta(days=days - 1)).date()
    buckets = [start + timedelta(days=offset) for offset in range(days)]
    matches = {day: 0 for day in buckets}
    applications = {day: 0 for day in buckets}

    if job_ids:
        # `computed_at`, not `updated_at`: this series answers "how many
        # matches were *found* that day". `updated_at` moves on every
        # rescore, so a nightly recompute would redraw the whole fortnight as
        # a spike on today. See `matching/schemas.py` on the two columns.
        match_rows = db.execute(
            select(func.date(MatchResult.computed_at), func.count())
            .where(MatchResult.job_posting_id.in_(job_ids), func.date(MatchResult.computed_at) >= start)
            .group_by(func.date(MatchResult.computed_at))
        ).all()
        for day, count in match_rows:
            if day in matches:
                matches[day] = count

        application_rows = db.execute(
            select(func.date(Application.applied_at), func.count())
            .where(Application.job_posting_id.in_(job_ids), func.date(Application.applied_at) >= start)
            .group_by(func.date(Application.applied_at))
        ).all()
        for day, count in application_rows:
            if day in applications:
                applications[day] = count

    return {
        "window_days": days,
        "series": [
            {"date": day.isoformat(), "matches": matches[day], "applications": applications[day]}
            for day in buckets
        ],
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
