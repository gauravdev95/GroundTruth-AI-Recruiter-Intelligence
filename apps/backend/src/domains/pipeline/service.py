"""Business logic for the marketplace loop: Smart Apply, the Kanban
pipeline's server-validated stage transitions, and the recruiter evidence
card. Messaging and notes live in their own modules
(`messaging.py`, `notes.py`) — both still import `dependencies.py`'s
ownership helpers from here so the "who may touch this application" answer
has exactly one implementation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.config import get_security_settings
from src.core.audit import write_audit_log
from src.core.exceptions import Conflict, Forbidden, NotFound
from src.core.mail.service import send_stage_change_email
from src.domains.auth.models import CandidateProfile, User
from src.domains.company.models import Company
from src.domains.matching.models import MatchResult
from src.domains.matching.tiers import build_reasoning
from src.domains.pipeline import notifications
from src.domains.pipeline.drift import ScoreDrift, compute_drift
from src.domains.pipeline.evidence import build_evidence_record
from src.domains.pipeline.models import (
    ALLOWED_ROLLBACKS,
    ALLOWED_TRANSITIONS,
    ROLLBACK_FALLBACK_FROM_REJECTED,
    Application,
    ApplicationStatus,
    NotificationType,
)
from src.domains.recruiter.models import JobPosting
from src.platform.models import AuditLog

#: The `audit_log` actions that record a *forward* stage transition. Read
#: back by `resolve_rollback_target` to answer "which stage was this
#: application rejected from"; `application.rolled_back` is deliberately not
#: in the set, so an undo can never be mistaken for the decision it undid.
FORWARD_TRANSITION_ACTIONS = ("application.status_changed", "application.hired")

logger = structlog.get_logger(__name__)


def _notify_stage_change_by_email(db: Session, *, user_id: uuid.UUID, application_id: uuid.UUID, job_title: str, status_label: str) -> None:
    """Best-effort: a notification email failing (e.g. SMTP outage) must
    never block the stage transition or application it's reporting on —
    same degrade-gracefully principle as third-party verification checks."""
    user = db.get(User, user_id)
    if user is None:
        return
    application_url = f"{get_security_settings().frontend_base_url}/applications/{application_id}"
    try:
        send_stage_change_email(
            to_email=user.email,
            full_name=user.display_name,
            job_title=job_title,
            status_label=status_label,
            application_url=application_url,
        )
    except Exception:
        logger.warning("stage_change_email_failed", user_id=str(user_id), application_id=str(application_id))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_published_job(db: Session, job_posting_id: uuid.UUID) -> JobPosting:
    job = db.get(JobPosting, job_posting_id)
    if job is None:
        raise NotFound("Job not found")
    return job


def apply_to_job(
    db: Session, profile: CandidateProfile, job_posting_id: uuid.UUID, *, cover_note: str | None
) -> Application:
    """Smart Apply: no data re-entry — the evidence snapshot is built from
    what's already verified. Requires an existing `MatchResult` (the job
    must actually be in this candidate's feed): applying to a job you were
    never matched to isn't "Smart Apply", it's a cold application this
    feature doesn't cover.
    """
    job = _get_published_job(db, job_posting_id)
    if job.status.value != "published":
        raise Conflict("This job is not accepting applications")

    match = db.execute(
        select(MatchResult).where(
            MatchResult.job_posting_id == job_posting_id, MatchResult.candidate_profile_id == profile.id
        )
    ).scalar_one_or_none()
    if match is None:
        raise Conflict("You can only Smart Apply to a job you're matched to")

    existing = db.execute(
        select(Application).where(
            Application.job_posting_id == job_posting_id, Application.candidate_profile_id == profile.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise Conflict("You already applied to this job")

    snapshot = build_evidence_record(db, profile, job_posting_id=job_posting_id)
    # The snapshot's own identity, minted here rather than derived from the
    # application id: a re-application (a future feature) would be a second
    # application citing a *different* snapshot, and an id that is just the
    # application id could never express that.
    snapshot_id = uuid.uuid4()
    application = Application(
        job_posting_id=job_posting_id,
        candidate_profile_id=profile.id,
        status=ApplicationStatus.APPLIED,
        cover_note=cover_note,
        evidence_snapshot=snapshot,
        evidence_snapshot_id=snapshot_id,
        # Provenance, frozen at this instant. `match.match_score` will keep
        # moving as either side is re-embedded; `score_at_apply` is the number
        # the recruiter's decision is made against and must not
        # (`domains/pipeline/drift.py`).
        match_id=match.id,
        score_at_apply=float(match.match_score),
    )
    db.add(application)
    db.flush()

    write_audit_log(
        db,
        actor_user_id=profile.user_id,
        action="application.created",
        entity_type="application",
        entity_id=application.id,
        before=None,
        after={
            "status": ApplicationStatus.APPLIED.value,
            "job_posting_id": str(job_posting_id),
            # Cited, not just stored: this names the exact frozen evidence and
            # score any later shortlisting decision was made against, which
            # the inline JSONB alone cannot provide.
            "evidence_snapshot_id": str(snapshot_id),
            "score_at_apply": float(match.match_score),
        },
    )

    if job.created_by_user_id is not None:
        notifications.notify(
            db,
            user_id=job.created_by_user_id,
            type_=NotificationType.STAGE_CHANGE,
            payload={
                "application_id": str(application.id),
                "job_title": job.title,
                "status": ApplicationStatus.APPLIED.value,
                "message": "New Smart Apply application received.",
            },
        )

    db.commit()
    db.refresh(application)

    if job.created_by_user_id is not None:
        _notify_stage_change_by_email(
            db,
            user_id=job.created_by_user_id,
            application_id=application.id,
            job_title=job.title,
            status_label="New Smart Apply application received",
        )

    logger.info("application_created", application_id=str(application.id), job_posting_id=str(job_posting_id))
    return application


def get_application_for_recruiter(db: Session, user: User, application_id: uuid.UUID) -> Application:
    application = db.get(Application, application_id)
    if application is None:
        raise NotFound("Application not found")
    job = db.get(JobPosting, application.job_posting_id)
    if job is None or job.created_by_user_id != user.id:
        raise Forbidden()
    return application


def get_application_for_candidate(db: Session, profile: CandidateProfile, application_id: uuid.UUID) -> Application:
    application = db.get(Application, application_id)
    if application is None or application.candidate_profile_id != profile.id:
        raise NotFound("Application not found")
    return application


@dataclass(frozen=True)
class RecruiterApplicationContext:
    """Everything the standalone recruiter application page needs beyond the
    `Application` row itself. A dataclass rather than the tuple this used to
    return: it now carries seven fields including a nested drift result, and
    positional unpacking of that is a bug waiting to happen."""

    application: Application
    job_title: str
    company_name: str
    candidate_profile_id: uuid.UUID
    candidate_headline: str | None
    drift: ScoreDrift
    rollback_target: ApplicationStatus | None


def live_match_score(db: Session, application: Application) -> float | None:
    """This pair's current `match_results.match_score`, or `None` if the row
    is gone. Looked up by the natural pair rather than `Application.match_id`
    — that FK is `SET NULL` on a prune and would keep reading `None` even
    after a later recompute re-created the pair."""
    score = db.execute(
        select(MatchResult.match_score).where(
            MatchResult.job_posting_id == application.job_posting_id,
            MatchResult.candidate_profile_id == application.candidate_profile_id,
        )
    ).scalar_one_or_none()
    return float(score) if score is not None else None


def application_drift(db: Session, application: Application) -> ScoreDrift:
    """Drift for a single application. The board computes the same thing in
    bulk (`get_pipeline`); both go through `drift.compute_drift`, so the two
    surfaces cannot disagree about what drift means."""
    return compute_drift(
        score_at_apply=(
            float(application.score_at_apply) if application.score_at_apply is not None else None
        ),
        live_score=live_match_score(db, application),
    )


def get_application_for_recruiter_with_context(
    db: Session, user: User, application_id: uuid.UUID
) -> RecruiterApplicationContext:
    """Same ownership check as `get_application_for_recruiter`, plus the
    display fields a standalone application page needs (job title, company
    name, candidate id/headline, score drift, rollback target) — a Kanban
    card already carries these from the pipeline board response, but a direct
    link (e.g. the notification bell) has only the application id."""
    application = get_application_for_recruiter(db, user, application_id)
    job = db.get(JobPosting, application.job_posting_id)
    if job is None:
        raise NotFound("Job not found")
    company = db.get(Company, job.company_id)
    candidate = db.get(CandidateProfile, application.candidate_profile_id)
    return RecruiterApplicationContext(
        application=application,
        job_title=job.title,
        company_name=company.name if company is not None else "",
        candidate_profile_id=application.candidate_profile_id,
        candidate_headline=candidate.headline if candidate is not None else None,
        drift=application_drift(db, application),
        # The exact target, not just the affordance: a detail page has room to
        # name the stage the recruiter is about to restore, and one extra
        # `audit_log` query on a single-application view is not the N+1 the
        # board had to avoid.
        rollback_target=resolve_rollback_target(db, application),
    )


def transition_status(
    db: Session,
    user: User,
    application: Application,
    *,
    to_status: ApplicationStatus,
    close_reason: str | None = None,
    close_note: str | None = None,
) -> Application:
    """Server-validated Kanban transition — no arbitrary jumps
    (`ALLOWED_TRANSITIONS`). Writes an `audit_log` row and notifies the
    candidate, in the same transaction as the status change.

    **Every transition is a recruiter action.** There is no system-initiated
    caller anywhere in this codebase: nothing schedules a rejection, no
    threshold drop triggers one, and a job closing leaves its applications
    where they are. A candidate leaves this pipeline because a human moved
    them.

    `close_reason`/`close_note` are the optional structured feedback the
    rejection modal collects. They ride on the audit entry rather than on a
    column of `applications`, for three reasons: the audit row is already
    the record of *this* decision (a column would be overwritten by the next
    one, losing the reason a rolled-back rejection was made for), it is
    already actor-attributed, and it is already the thing
    `resolve_rollback_target` reads back. Nothing is stored when neither is
    given, so a skipped modal leaves no trace of having been skipped.
    """
    allowed = ALLOWED_TRANSITIONS.get(application.status, frozenset())
    if to_status not in allowed:
        raise Conflict(
            f"Cannot move an application from '{application.status.value}' to '{to_status.value}'"
        )

    before_status = application.status.value
    application.status = to_status
    application.status_updated_at = _utcnow()
    db.flush()

    after: dict = {"status": to_status.value}
    # Recorded only on the transition they describe. A "skills gap" reason
    # attached to a shortlisting would be nonsense, and `_StrictModel` cannot
    # reject the combination without also rejecting clients that send the
    # field unconditionally.
    if to_status is ApplicationStatus.REJECTED:
        if close_reason:
            after["close_reason"] = close_reason
        if close_note:
            after["close_note"] = close_note

    write_audit_log(
        db,
        actor_user_id=user.id,
        action="application.hired" if to_status is ApplicationStatus.HIRED else "application.status_changed",
        entity_type="application",
        entity_id=application.id,
        before={"status": before_status},
        after=after,
    )

    candidate = db.get(CandidateProfile, application.candidate_profile_id)
    job = db.get(JobPosting, application.job_posting_id)
    if candidate is not None:
        notifications.notify(
            db,
            user_id=candidate.user_id,
            type_=NotificationType.STAGE_CHANGE,
            payload={
                "application_id": str(application.id),
                "job_title": job.title if job is not None else None,
                "status": to_status.value,
            },
        )

    db.commit()
    db.refresh(application)

    if candidate is not None:
        _notify_stage_change_by_email(
            db,
            user_id=candidate.user_id,
            application_id=application.id,
            job_title=job.title if job is not None else "your application",
            status_label=to_status.value.replace("_", " ").title(),
        )

    logger.info(
        "application_transitioned", application_id=str(application.id),
        from_status=before_status, to_status=to_status.value,
    )
    return application


def resolve_rollback_target(db: Session, application: Application) -> ApplicationStatus | None:
    """The single stage this application may be rolled back to, or `None` if
    it may not be rolled back at all. The one place rollback legality is
    decided — the board's `can_roll_back` affordance, the detail page's
    `rollback_target`, and `rollback_status`'s own guard all call this rather
    than re-deriving the rule.

    Two cases, both driven by `ALLOWED_ROLLBACKS`' own documentation:

    * A forward-path stage has exactly one predecessor, read straight off the
      static map. `APPLIED` and `HIRED` are absent from it and so return
      `None`.
    * `REJECTED` has three possible predecessors, so the answer comes from
      the `audit_log` row that recorded the rejection — the most recent
      *forward* transition (`FORWARD_TRANSITION_ACTIONS`, which excludes
      rollbacks) whose `after.status` was `rejected`. Its `before.status` is
      where the application actually was, which is the only truthful target.
    """
    if application.status is not ApplicationStatus.REJECTED:
        return ALLOWED_ROLLBACKS.get(application.status)

    row = db.execute(
        select(AuditLog)
        .where(
            AuditLog.entity_type == "application",
            AuditLog.entity_id == application.id,
            AuditLog.action.in_(FORWARD_TRANSITION_ACTIONS),
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    before_status = (row.before or {}).get("status") if row is not None else None
    if before_status is None:
        return ROLLBACK_FALLBACK_FROM_REJECTED

    try:
        restored = ApplicationStatus(before_status)
    except ValueError:
        # An `audit_log` row naming a status this enum no longer has. Trusting
        # it would write an invalid status; the fallback is always valid.
        return ROLLBACK_FALLBACK_FROM_REJECTED

    # A rejection recorded as coming *from* a terminal state would restore the
    # application into a stage the rollback policy says it can never re-enter.
    if restored in (ApplicationStatus.REJECTED, ApplicationStatus.HIRED):
        return ROLLBACK_FALLBACK_FROM_REJECTED
    return restored


def rollback_status(db: Session, user: User, application: Application) -> Application:
    """Undoes the last forward stage transition.

    What moves and what does not:

    * `status` becomes `resolve_rollback_target`'s answer.
    * `status_updated_at` becomes *now*. It is a status update — freezing it
      would make "how long has this card sat in this column" report the age of
      a stage the application is no longer in.
    * `applied_at` and `score_at_apply` are untouched. Neither is a function
      of the current stage, and rewriting the score the original decision was
      made against would defeat the entire point of freezing it.
    * The audit row that recorded the forward transition is **not** deleted or
      amended. `audit_log` is append-only everywhere in this codebase, a new
      `application.rolled_back` row records the undo alongside it, and
      `recruiter_funnel` reads the *earliest* forward transition for
      time-to-first-response — rewriting history would silently move a
      published metric.

    The candidate is notified and emailed on the same path as a forward
    transition. A status they have already been shown changing back without a
    word is strictly worse than being told: their own "My Applications" view
    reads the same column and would show the reversal regardless.
    """
    to_status = resolve_rollback_target(db, application)
    if to_status is None:
        raise Conflict(f"An application at '{application.status.value}' cannot be rolled back")

    before_status = application.status.value
    application.status = to_status
    application.status_updated_at = _utcnow()
    db.flush()

    write_audit_log(
        db,
        actor_user_id=user.id,
        action="application.rolled_back",
        entity_type="application",
        entity_id=application.id,
        before={"status": before_status},
        after={"status": to_status.value},
    )

    candidate = db.get(CandidateProfile, application.candidate_profile_id)
    job = db.get(JobPosting, application.job_posting_id)
    if candidate is not None:
        notifications.notify(
            db,
            user_id=candidate.user_id,
            type_=NotificationType.STAGE_CHANGE,
            payload={
                "application_id": str(application.id),
                "job_title": job.title if job is not None else None,
                "status": to_status.value,
                "rolled_back_from": before_status,
            },
        )

    db.commit()
    db.refresh(application)

    if candidate is not None:
        _notify_stage_change_by_email(
            db,
            user_id=candidate.user_id,
            application_id=application.id,
            job_title=job.title if job is not None else "your application",
            status_label=to_status.value.replace("_", " ").title(),
        )

    logger.info(
        "application_rolled_back", application_id=str(application.id),
        from_status=before_status, to_status=to_status.value,
    )
    return application


def list_candidate_applications(db: Session, profile: CandidateProfile) -> list[Application]:
    return list(
        db.execute(
            select(Application)
            .where(Application.candidate_profile_id == profile.id)
            .order_by(Application.applied_at.desc())
        ).scalars()
    )


def list_candidate_applications_with_job(
    db: Session, profile: CandidateProfile
) -> list[tuple[Application, str, str]]:
    """Same rows as `list_candidate_applications`, plus the job title and
    company name a "My Applications" list needs — `ApplicationResponse`
    itself deliberately carries only `job_posting_id` (an application's own
    identity shouldn't embed another aggregate's display fields), so this is
    a join at the query layer rather than an N+1 job-detail fetch per row."""
    rows = db.execute(
        select(Application, JobPosting.title, Company.name)
        .join(JobPosting, JobPosting.id == Application.job_posting_id)
        .join(Company, Company.id == JobPosting.company_id)
        .where(Application.candidate_profile_id == profile.id)
        .order_by(Application.applied_at.desc())
    ).all()
    return [(application, job_title, company_name) for application, job_title, company_name in rows]


def get_application_for_candidate_with_job(
    db: Session, profile: CandidateProfile, application_id: uuid.UUID
) -> tuple[Application, str, str]:
    application = get_application_for_candidate(db, profile, application_id)
    job = db.get(JobPosting, application.job_posting_id)
    if job is None:
        raise NotFound("Job not found")
    company = db.get(Company, job.company_id)
    return application, job.title, company.name if company is not None else ""


def get_pipeline(db: Session, job: JobPosting) -> dict[str, list]:
    """The Kanban board's data: the `matched` column is derived
    (`MatchResult` rows with no `Application` yet — matching purely by
    computation, no action taken), every other column is a real
    `Application` row grouped by `status`. One query per column, not N+1
    per candidate — `evidence.py` is intentionally not called here (that's
    the single-candidate evidence-card endpoint); the board only needs
    preview-shaped data.

    **Ordering within every application column** is
    `score_at_apply DESC NULLS LAST, applied_at ASC, id ASC`, done in SQL
    (which is what promoting `score_at_apply` out of the evidence snapshot
    and into a column bought — see migration `b2d5e8f14c73`).

    Sorting on the *frozen* score rather than the live one is deliberate. The
    live score moves under the recruiter with no action on their part, so
    ranking by it would silently reorder a board between two page loads
    mid-review; and it is nullable (a pruned match), which would leave part
    of every column in arbitrary order. `score_at_apply` is attached to the
    application itself, is present for every application created through
    Smart Apply, and is the number each card in the column is actually
    comparable on. The live score is shown *next to* it as drift — that is
    what it is for here, not ranking.

    **Tiebreak**, in order:

    1. `applied_at ASC` — the earlier applicant wins a tie. First-come is the
       fair rule when the evidence says two candidates are equally strong,
       and it is the one consistent with time-to-first-response being a
       tracked recruiter metric.
    2. `id ASC` — a total order, so two applications submitted in the same
       transaction (identical `applied_at`) still render in a stable order
       across page loads rather than in whatever order Postgres returns.

    `NULLS LAST` puts the pre-`score_at_apply` backfill stragglers at the
    bottom of their column instead of, per Postgres' default for `DESC`, the
    top.
    """
    applications = list(
        db.execute(
            select(Application)
            .where(Application.job_posting_id == job.id)
            .order_by(
                Application.score_at_apply.desc().nulls_last(),
                Application.applied_at.asc(),
                Application.id.asc(),
            )
        ).scalars()
    )
    applied_candidate_ids = {a.candidate_profile_id for a in applications}

    matched_rows = list(
        db.execute(
            select(MatchResult, CandidateProfile)
            .join(CandidateProfile, CandidateProfile.id == MatchResult.candidate_profile_id)
            .where(MatchResult.job_posting_id == job.id)
            # Same total-order discipline as the application columns: score
            # first, then a stable tiebreak so equal-scoring candidates don't
            # swap places between refreshes.
            .order_by(MatchResult.match_score.desc(), MatchResult.candidate_profile_id.asc())
        ).all()
    )
    matched_column = [
        _candidate_preview(match, candidate)
        for match, candidate in matched_rows
        if candidate.id not in applied_candidate_ids
    ]

    candidate_ids = [a.candidate_profile_id for a in applications]
    candidates_by_id = (
        {
            c.id: c
            for c in db.execute(select(CandidateProfile).where(CandidateProfile.id.in_(candidate_ids))).scalars()
        }
        if candidate_ids
        else {}
    )

    # The live score for every applied candidate, in one query keyed by the
    # natural pair — not by `Application.match_id`, which is `SET NULL` on a
    # pruned match and would report "no live score" for a pair that has since
    # been re-matched and does have one.
    # `match_reasons` rides along on the same query rather than a second one:
    # the applied columns render the identical card as `matched`, so they need
    # the identical evidence line, and fetching it separately would be a
    # second full scan of the same rows.
    live_match_by_candidate = (
        {
            candidate_id: (float(score), reasons)
            for candidate_id, score, reasons in db.execute(
                select(
                    MatchResult.candidate_profile_id,
                    MatchResult.match_score,
                    MatchResult.match_reasons,
                ).where(
                    MatchResult.job_posting_id == job.id,
                    MatchResult.candidate_profile_id.in_(candidate_ids),
                )
            ).all()
        }
        if candidate_ids
        else {}
    )

    columns: dict[str, list] = {"matched": matched_column}
    for status in ApplicationStatus:
        columns[status.value] = []

    for application in applications:
        candidate = candidates_by_id.get(application.candidate_profile_id)
        live_score, live_reasons = live_match_by_candidate.get(
            application.candidate_profile_id, (None, None)
        )
        drift = compute_drift(
            score_at_apply=(
                float(application.score_at_apply) if application.score_at_apply is not None else None
            ),
            live_score=live_score,
        )
        # Falls back to the frozen `evidence_snapshot`'s copy of the match
        # when the live row has been pruned. Without it, an application whose
        # match was pruned (its job closed and reopened, say) would lose the
        # one line explaining why the candidate is on the board at all — and
        # the snapshot is the honest source in that case anyway: it is what
        # was true when they applied.
        reasons = live_reasons if live_reasons is not None else _snapshot_match_reasons(application)
        columns[application.status.value].append(
            {
                "application_id": str(application.id),
                "candidate_profile_id": str(application.candidate_profile_id),
                "headline": candidate.headline if candidate is not None else None,
                "status": application.status.value,
                "applied_at": application.applied_at.isoformat(),
                "status_updated_at": application.status_updated_at.isoformat(),
                "score_at_apply": drift.score_at_apply,
                "match_score": drift.live_score,
                "drift_points": drift.points,
                "drift_direction": drift.direction,
                "drift_is_meaningful": drift.is_meaningful,
                "matched_skills": _verified_skill_names(reasons, CARD_SKILL_COUNT),
                "reasoning": build_reasoning(reasons),
                "is_verified": candidate.is_discoverable if candidate is not None else False,
                # Precomputed here rather than left to the client: the client
                # cannot know `ALLOWED_ROLLBACKS`' `REJECTED` case without the
                # audit trail, and a button that 409s is not a UX.
                "can_roll_back": _board_offers_rollback(application.status),
            }
        )

    return columns


def _snapshot_match_reasons(application: Application) -> dict | None:
    """The `match_reasons`-shaped half of a frozen `evidence_snapshot`.

    `build_evidence_snapshot` stores the match under `"match"` with the two
    halves under their read-path names (`matched_required_skills` /
    `matched_desirable_skills`, see `pipeline/evidence.py`), so this
    translates back to the `{"required": ..., "desirable": ...}` shape the
    formatter takes rather than teaching the formatter a second vocabulary.
    """
    match = (application.evidence_snapshot or {}).get("match")
    if not isinstance(match, dict):
        return None
    return {
        "required": match.get("matched_required_skills") or [],
        "desirable": match.get("matched_desirable_skills") or [],
    }


#: How many matched skill names a board card carries. The card renders them
#: as a single `Rust · Postgres · Distributed` line; the reasoning string
#: underneath already states the full count, so sending more would be data
#: the card has nowhere to put.
CARD_SKILL_COUNT = 3


def _verified_skill_names(match_reasons: dict | None, limit: int) -> list[str]:
    """The must-have skills this candidate has actual evidence for, strongest
    first, then desirables if there is room.

    Ordered by `evidence_weight` rather than by the job's requirement order:
    the card shows three of them, and the three worth showing are the three
    best-evidenced, not the first three the recruiter happened to type.
    """
    reasons = match_reasons or {}
    ranked: list[tuple[float, str]] = []
    # Required first, unconditionally — a desirable skill with perfect
    # evidence still matters less on a screening card than a must-have.
    for bucket, floor in ((reasons.get("required") or [], 1.0), (reasons.get("desirable") or [], 0.0)):
        for reason in bucket:
            if not isinstance(reason, dict) or not reason.get("candidate_has_skill"):
                continue
            name = reason.get("skill_name")
            if not isinstance(name, str) or not name:
                continue
            ranked.append((floor + float(reason.get("evidence_weight") or 0.0), name))

    ranked.sort(key=lambda pair: (-pair[0], pair[1]))
    return [name for _, name in ranked[:limit]]


def _candidate_preview(match: MatchResult, candidate: CandidateProfile) -> dict:
    """One card in the `matched` column.

    Carries the reasoning string and the top matched skills rather than the
    raw `match_reasons` payload: the board renders 5 columns of these and the
    full payload is an order of magnitude larger than the two lines a card
    shows. The single-candidate evidence endpoint
    (`GET /recruiter/candidates/{id}/evidence`) is where the full trail
    lives, and the drawer fetches it on open.

    `is_verified` is `is_discoverable`, renamed for what it means *to a
    recruiter*: that flag already requires verified evidence plus a completed
    code-grounded interview (`domains/student/completeness.py`), which is
    exactly the claim the card's checkmark makes. It is not a second,
    weaker notion of verification invented for this card.
    """
    return {
        "candidate_profile_id": str(candidate.id),
        "headline": candidate.headline,
        "match_score": float(match.match_score),
        "matched_skills": _verified_skill_names(match.match_reasons, CARD_SKILL_COUNT),
        "reasoning": build_reasoning(match.match_reasons),
        "is_verified": candidate.is_discoverable,
    }


def _board_offers_rollback(status: ApplicationStatus) -> bool:
    """Whether the board should render a rollback action for this status.

    Answered from the status alone, deliberately: `resolve_rollback_target`
    is the authority, but for a `REJECTED` application it costs an
    `audit_log` query, and running one per card would reintroduce exactly the
    N+1 this board is written to avoid. `REJECTED` always has a target — the
    fallback (`ROLLBACK_FALLBACK_FROM_REJECTED`) guarantees it — so status is
    a sound answer here, and the mutation re-checks regardless.
    """
    return status is ApplicationStatus.REJECTED or status in ALLOWED_ROLLBACKS
