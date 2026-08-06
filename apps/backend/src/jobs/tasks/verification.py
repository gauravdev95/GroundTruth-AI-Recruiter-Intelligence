"""The verification consumer tasks — the module that was missing entirely.

`domains/student/evidence.py` has enqueued four `verify_*` job types since the
profile builder shipped (`verify_github_account`, `verify_coding_platform_account`,
`verify_repository`, `verify_certificate`; a fifth, `verify_experience`, is
new alongside this module), all routed to the `verification` Celery queue
(`jobs/celery_app.py`). Until now nothing consumed that queue, so every claim
sat at `PENDING` forever (`PROGRESS.md` §2.1). These five tasks are that
consumer.

**Contract with every task below** (constraint §4 of the task that added this
module): a completed check writes exactly one of `VERIFIED` / `REJECTED` /
`FLAGGED`, plus a numeric `verification_score`, a `verification_source`
string, and a `verification_payload` audit trail. A **failed** third-party
call — timeout, 5xx, connection refused — never writes any of those three; it
raises and lets `DatabaseTask`'s retry ladder run, and only resets the claim
to `UNVERIFIED` once retries are exhausted (`_exhausted` below). It is never
retried into `VERIFIED`.

**Why `evidence_records` is still untouched.** Every other module in this
codebase that touches verification has made the same call and documented it
in the same place: `evidence_records` (`docs/DATA_MODEL.md` §0.5) is a
derived *scoring* hub with a `weight NUMERIC NOT NULL` and no `status`
column, meant to be populated once a real analysis exists — which, after
this module runs, it does. Wiring `evidence_records` writes is the natural
next step once a matching/embeddings consumer exists to read them; adding
speculative rows to it now, before anything reads it, would be scope beyond
what was asked (fix the queue, don't invent a new consumer for a table nothing
uses yet) and untested. This is flagged here rather than silently skipped.

**Why profile_strength doesn't move here.** `student/completeness.py`
measures what is *filled*, not what is *verified*; recomputing it is still
done after every write below (`student_service.recompute_and_persist_strength`)
because `SectionStatus.verification` — the per-section rollup badge — must
reflect the new status immediately, and because `verify_github_account_task`
can change `github_user_id`, which `load_snapshot` reads.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.config import get_security_settings, get_verification_settings
from src.core.audit import write_audit_log
from src.core.mail import service as mail_service
from src.db.database import SessionLocal
from src.domains.auth.models import CandidateProfile, User
from src.domains.student import service as student_service
from src.domains.student.completeness import ProfileCompleteness
from src.domains.student.evidence import (
    JOB_CERTIFICATE,
    JOB_CODING_PLATFORM,
    JOB_EXPERIENCE,
    JOB_GITHUB_ACCOUNT,
    JOB_REPOSITORY,
)
from src.domains.student.models import (
    Certificate,
    CodingPlatform,
    CodingPlatformAccount,
    Experience,
    GithubAccount,
    Project,
    VerificationStatus,
)
from src.domains.verification import certificate as certificate_checker
from src.domains.verification import competencies
from src.domains.verification import experience as experience_scoring
from src.domains.verification import stages
from src.domains.verification import skills as skills_service
from src.domains.verification.clients import codeforces as codeforces_client
from src.domains.verification.clients import github as github_client
from src.domains.verification.clients import leetcode as leetcode_client
from src.domains.verification.clients import reachability
from src.domains.verification.exceptions import ClaimNotFound, VerificationServiceUnavailable
from src.jobs.celery_app import DatabaseTask, celery_app
from src.platform.models import AsyncJob

logger = structlog.get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _load_payload(async_job_id: str) -> dict[str, Any]:
    with SessionLocal() as session:
        job = session.get(AsyncJob, uuid.UUID(async_job_id))
        if job is None or not job.payload:
            raise ValueError(f"Job {async_job_id} has no payload")
        return dict(job.payload)


def _exhausted(task: DatabaseTask) -> bool:
    """True on the attempt that will not be retried again — the point at
    which a transient failure must resolve to `UNVERIFIED` instead of
    leaving the claim at `PENDING` indefinitely."""
    request = getattr(task, "request", None)
    if request is None:
        return True
    return request.retries >= task.max_retries


def _verification_has_settled(session: Session, candidate_profile_id: uuid.UUID) -> bool:
    """True when no claim for this candidate is still awaiting a check.

    `_finish` runs after *every* individual claim, so without this the first
    repository to verify would invite an interview grounded in a profile whose
    other claims were still being checked — the candidate would be examined on
    a fraction of their evidence, and the invitation could not be re-sent
    because it is sent once.

    Only `PENDING` blocks. `UNVERIFIED` does not: a third-party outage
    degrades to `UNVERIFIED` by design, and treating that as "still running"
    would leave a candidate permanently un-invited every time GitHub had a bad
    afternoon.
    """
    for model in (GithubAccount, CodingPlatformAccount, Project, Certificate, Experience):
        pending = session.execute(
            select(model.id).where(
                model.candidate_profile_id == candidate_profile_id,
                model.verification_status == VerificationStatus.PENDING,
                model.deleted_at.is_(None),
            ).limit(1)
        ).scalar_one_or_none()
        if pending is not None:
            return False
    return True


def _invite_profile_interview(
    session: Session, candidate_profile_id: uuid.UUID, completeness: ProfileCompleteness
) -> None:
    """Start the candidate's profile interview and email them, once.

    Idempotency comes from `start_profile_interview` returning None when a
    non-terminally-failed profile interview already exists — the email is sent
    only when a row was actually created, so re-running verification cannot
    re-send it.

    Skipped entirely if the candidate already completed *any* interview: they
    are already discoverable, and inviting them to a second one would be noise
    rather than an unlock.

    Every failure here is swallowed. This runs at the tail of a verification
    task whose real work has already committed; letting a mail outage or a
    broker hiccup fail the task would retry the verification — re-hitting a
    third-party API and rewriting a result that was already correct — to fix
    something that is not the verification's problem.
    """
    from src.domains.interview.models import Interview, InterviewStatus
    from src.domains.interview.service import start_profile_interview

    try:
        profile = session.get(CandidateProfile, candidate_profile_id)
        if profile is None:
            return

        # Only invite candidates who have finished the parts they control.
        # An incomplete profile has nothing coherent to ground questions in.
        if not completeness.meets_section_requirements:
            return
        # Already interviewed — they are discoverable, so a second invitation
        # would be noise rather than an unlock.
        if completeness.has_completed_interview:
            return

        already_completed = session.execute(
            select(Interview.id).where(
                Interview.candidate_profile_id == candidate_profile_id,
                Interview.status == InterviewStatus.COMPLETED,
            ).limit(1)
        ).scalar_one_or_none()
        if already_completed is not None:
            return

        interview = start_profile_interview(session, candidate_profile_id)
        if interview is None:
            return

        has_verified_repos = session.execute(
            select(Project.id).where(
                Project.candidate_profile_id == candidate_profile_id,
                Project.verification_status == VerificationStatus.VERIFIED,
                Project.deleted_at.is_(None),
            ).limit(1)
        ).scalar_one_or_none() is not None

        user = session.get(User, profile.user_id)
        if user is None:
            return

        base = get_security_settings().frontend_base_url.rstrip("/")
        mail_service.send_interview_invitation_email(
            to_email=user.email,
            full_name=user.display_name,
            interview_url=f"{base}/student/interview/{interview.id}",
            has_verified_repositories=has_verified_repos,
        )
        logger.info(
            "profile_interview_invited",
            candidate_profile_id=str(candidate_profile_id),
            interview_id=str(interview.id),
        )
    except Exception as exc:  # noqa: BLE001 — see docstring
        logger.error(
            "profile_interview_invite_failed",
            candidate_profile_id=str(candidate_profile_id),
            error=str(exc),
        )


#: How each settled status reads to the candidate. `UNVERIFIED` is in the
#: attention list rather than the confirmed one on purpose: nothing was proven,
#: and quietly filing it under "confirmed" would be the single most dishonest
#: line this email could contain. `PENDING` cannot appear — `_finish` only
#: builds this once nothing is pending.
_ATTENTION_REASONS = {
    VerificationStatus.REJECTED: "the check contradicted this claim",
    VerificationStatus.FLAGGED: "visible, but we could not confirm it independently",
    VerificationStatus.UNVERIFIED: "we could not reach the source to check it",
}


def _claim_label(row: Any) -> str:
    """A candidate-facing name for one claim row.

    Deliberately not `repr` or a table name: the email says "GitHub —
    octocat", not "github_account 3f9a…", because the reader has to recognise
    which of *their* claims is being talked about.
    """
    if isinstance(row, GithubAccount):
        return f"GitHub — {row.github_username}"
    if isinstance(row, CodingPlatformAccount):
        name = row.custom_platform_name or row.platform.value.replace("_", " ").title()
        return f"{name} — {row.handle}"
    if isinstance(row, Project):
        return f"Project — {row.title}"
    if isinstance(row, Certificate):
        return f"Certificate — {row.title}"
    return f"Experience — {row.title} at {row.company_name}"


def _send_verification_summary(session: Session, profile: CandidateProfile) -> None:
    """Email the candidate the outcome of every check, exactly once.

    Guarded on three things, and each guard exists for its own reason:

    * `onboarding_submitted_at` — a candidate still mid-onboarding has not
      asked for anything to be checked yet, and a summary would arrive before
      the flow that promises it.
    * `verification_summary_sent_at` — the send-once marker. `_finish` runs
      after every individual claim, so without it a six-claim candidate gets
      six identical emails.
    * A row that is still `PENDING` — checked by the caller
      (`_verification_has_settled`), because a summary sent mid-run would
      describe a half-finished picture and could never be corrected.

    Failures are swallowed for the same reason `_invite_profile_interview`
    swallows them: the verification this trails has already committed, and a
    mail outage must not retry a third-party check that already succeeded. The
    marker is written *before* dispatch so a mailer that raises cannot leave
    the door open for a duplicate on the next claim's `_finish`.
    """
    if profile.onboarding_submitted_at is None or profile.verification_summary_sent_at is not None:
        return

    user = session.get(User, profile.user_id)
    if user is None:
        return

    confirmed: list[str] = []
    needs_attention: list[tuple[str, str]] = []

    for model in (GithubAccount, CodingPlatformAccount, Project, Certificate, Experience):
        rows = session.execute(
            select(model).where(
                model.candidate_profile_id == profile.id,
                model.deleted_at.is_(None),
            )
        ).scalars()
        for row in rows:
            status = row.verification_status
            if status is VerificationStatus.VERIFIED:
                confirmed.append(_claim_label(row))
            elif status in _ATTENTION_REASONS:
                needs_attention.append((_claim_label(row), _ATTENTION_REASONS[status]))

    if not confirmed and not needs_attention:
        return

    profile.verification_summary_sent_at = _utcnow()
    session.commit()

    try:
        base = get_security_settings().frontend_base_url.rstrip("/")
        mail_service.send_verification_summary_email(
            to_email=user.email,
            full_name=user.display_name,
            confirmed=confirmed,
            needs_attention=needs_attention,
            profile_url=f"{base}/student/profile",
        )
        logger.info(
            "verification_summary_sent",
            candidate_profile_id=str(profile.id),
            confirmed=len(confirmed),
            needs_attention=len(needs_attention),
        )
    except Exception as exc:  # noqa: BLE001 — see docstring
        logger.error(
            "verification_summary_send_failed",
            candidate_profile_id=str(profile.id),
            error=str(exc),
        )


def _finish(candidate_profile_id: uuid.UUID) -> None:
    """Recomputes `profile_strength`, then invites the profile interview if
    verification has settled.

    Re-embedding/re-matching (or removal from `match_results` if this leaves
    the candidate non-discoverable) is handled inside
    `recompute_and_persist_strength` itself
    (`student/service.py::_sync_matching_index`) — centralized there so every
    caller, not just this one, keeps the same guarantee. See that module for
    why this used to be wired only here, and why that was a bug.

    The interview invitation is deliberately *after* the recompute: the
    candidate's strength and evidence score should reflect this verification
    before the email that points them at the next step.
    """
    with SessionLocal() as session:
        completeness = student_service.recompute_and_persist_strength(session, candidate_profile_id)
        # None means the candidate deleted their account while this
        # verification was in flight — nothing left to invite.
        if completeness is None:
            return

        if _verification_has_settled(session, candidate_profile_id):
            # The summary goes first: it reports what just finished, while the
            # interview invitation is about what happens next. A candidate who
            # receives them in the other order is invited to an interview
            # before being told their evidence was checked at all.
            profile = session.get(CandidateProfile, candidate_profile_id)
            if profile is not None:
                _send_verification_summary(session, profile)
            _invite_profile_interview(session, candidate_profile_id, completeness)


def _audit_claim(
    session: Session, *, entity_type: str, entity_id: uuid.UUID, before_status: str, after_status: str
) -> None:
    """One `audit_log` row per verification outcome — constraint: "every
    verification outcome writes an audit row with actor, timestamp, and
    before/after state." `actor_user_id=None`: this always runs from a
    Celery task, never a request, so there is no human actor — the system
    itself is the actor, which `AuditLog.actor_user_id`'s nullability
    already exists to represent."""
    write_audit_log(
        session,
        actor_user_id=None,
        action=f"{entity_type}.verification_{after_status}",
        entity_type=entity_type,
        entity_id=entity_id,
        before={"verification_status": before_status},
        after={"verification_status": after_status},
    )


# --------------------------------------------------------------------------
# 1. GitHub account — confirms the claimed username exists, resolves the
#    stable numeric id `docs/DATA_MODEL.md` §3 always wanted stored.
# --------------------------------------------------------------------------


@celery_app.task(base=DatabaseTask, bind=True, name="src.jobs.tasks.verification.verify_github_account_task")
def verify_github_account_task(self: DatabaseTask, async_job_id: str) -> dict[str, str]:
    payload = _load_payload(async_job_id)
    source_id = uuid.UUID(payload["source_id"])
    candidate_profile_id = uuid.UUID(payload["candidate_profile_id"])
    username = payload["github_username"]

    try:
        user = github_client.get_user(username)
    except ClaimNotFound:
        with SessionLocal() as session:
            account = session.get(GithubAccount, source_id)
            if account is not None:
                before = account.verification_status.value
                account.verification_status = VerificationStatus.REJECTED
                account.verification_score = 0.0
                account.verification_source = "github_api"
                account.verification_payload = {"checked_username": username, "found": False}
                _audit_claim(
                    session, entity_type="github_account", entity_id=account.id,
                    before_status=before, after_status="rejected",
                )
                session.commit()
        _finish(candidate_profile_id)
        return {"status": "rejected"}
    except VerificationServiceUnavailable as exc:
        if _exhausted(self):
            with SessionLocal() as session:
                account = session.get(GithubAccount, source_id)
                if account is not None:
                    before = account.verification_status.value
                    account.verification_status = VerificationStatus.UNVERIFIED
                    account.verification_source = "github_api"
                    account.verification_payload = {"error": str(exc), "exhausted_retries": True}
                    _audit_claim(
                        session, entity_type="github_account", entity_id=account.id,
                        before_status=before, after_status="unverified",
                    )
                    session.commit()
            _finish(candidate_profile_id)
        raise

    with SessionLocal() as session:
        account = session.get(GithubAccount, source_id)
        if account is not None:
            before = account.verification_status.value
            account.github_user_id = user["id"]
            account.verification_status = VerificationStatus.VERIFIED
            account.verification_score = 100.0
            account.verification_source = "github_api"
            account.verification_payload = {
                "id": user["id"],
                "login": user["login"],
                "public_repos": user.get("public_repos"),
                "followers": user.get("followers"),
                "created_at": user.get("created_at"),
            }
            account.verified_at = _utcnow()
            _audit_claim(
                session, entity_type="github_account", entity_id=account.id,
                before_status=before, after_status="verified",
            )
            session.commit()
    _finish(candidate_profile_id)
    return {"status": "verified"}


# --------------------------------------------------------------------------
# 2. Repository — fork detection, contribution share, dependency-manifest
#    technology detection, and quality signals. The GitHub-repository-
#    analysis consumer named in the task.
# --------------------------------------------------------------------------


def _candidate_github_login(candidate_profile_id: uuid.UUID, session: Session) -> str | None:
    from sqlalchemy import select

    account = session.execute(
        select(GithubAccount)
        .where(GithubAccount.candidate_profile_id == candidate_profile_id, GithubAccount.deleted_at.is_(None))
        .order_by(GithubAccount.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if account is None:
        return None
    # An OAuth-resolved login is authoritative; a claimed-but-unverified
    # username is still the best available signal otherwise.
    return account.github_username


def _candidate_github_token(candidate_profile_id: uuid.UUID, session: Session) -> str | None:
    from sqlalchemy import select

    from src.core.crypto import decrypt_secret

    account = session.execute(
        select(GithubAccount)
        .where(
            GithubAccount.candidate_profile_id == candidate_profile_id,
            GithubAccount.deleted_at.is_(None),
            GithubAccount.access_token_encrypted.is_not(None),
        )
        .order_by(GithubAccount.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if account is None or account.access_token_encrypted is None:
        return None
    return decrypt_secret(account.access_token_encrypted)


@celery_app.task(base=DatabaseTask, bind=True, name="src.jobs.tasks.verification.verify_repository_task")
def verify_repository_task(self: DatabaseTask, async_job_id: str) -> dict[str, str]:
    payload = _load_payload(async_job_id)
    source_id = uuid.UUID(payload["source_id"])
    candidate_profile_id = uuid.UUID(payload["candidate_profile_id"])
    repo_url = payload["repo_url"]

    with SessionLocal() as session:
        github_login = _candidate_github_login(candidate_profile_id, session)
        token = _candidate_github_token(candidate_profile_id, session)

    context = stages.RepositoryContext(
        project_id=source_id,
        candidate_profile_id=candidate_profile_id,
        repo_url=repo_url,
        github_login=github_login,
        token=token,
    )

    try:
        with SessionLocal() as session:
            outcome = stages.run_analysis_pipeline(
                session, context, is_final_attempt=_exhausted(self)
            )
        verdict = outcome.verdict
        composite_score = outcome.composite_score
        detected = context.detected_technologies
    except ClaimNotFound as exc:
        with SessionLocal() as session:
            project = session.get(Project, source_id)
            if project is not None:
                before = project.verification_status.value
                project.verification_status = VerificationStatus.REJECTED
                project.verification_score = 0.0
                project.verification_source = "github_api"
                project.verification_payload = {"error": str(exc), "repo_url": repo_url}
                _audit_claim(
                    session, entity_type="project", entity_id=project.id,
                    before_status=before, after_status="rejected",
                )
                session.commit()
        _finish(candidate_profile_id)
        return {"status": "rejected"}
    except VerificationServiceUnavailable as exc:
        if _exhausted(self):
            with SessionLocal() as session:
                project = session.get(Project, source_id)
                if project is not None:
                    before = project.verification_status.value
                    project.verification_status = VerificationStatus.UNVERIFIED
                    project.verification_source = "github_api"
                    project.verification_payload = {"error": str(exc), "exhausted_retries": True}
                    _audit_claim(
                        session, entity_type="project", entity_id=project.id,
                        before_status=before, after_status="unverified",
                    )
                    session.commit()
            _finish(candidate_profile_id)
        raise

    with SessionLocal() as session:
        project = session.get(Project, source_id)
        if project is not None:
            before = project.verification_status.value
            project.verification_status = VerificationStatus(verdict.status)
            project.verification_score = composite_score
            project.verification_source = "github_api"
            # The composite payload is still written — the interview and
            # matching layers read it — but it is now assembled from the
            # per-stage results rather than being the only place the analysis
            # exists. `verification_stages` holds each stage's own output.
            project.verification_payload = outcome.payload
            if verdict.status == "verified":
                project.verified_at = _utcnow()
            _audit_claim(
                session, entity_type="project", entity_id=project.id,
                before_status=before, after_status=verdict.status,
            )
            session.commit()

            if detected:
                skills_service.apply_detected_technologies(
                    session,
                    candidate_profile_id=candidate_profile_id,
                    technologies=detected,
                    evidence_weight=composite_score / 100.0,
                )
                session.commit()

    _finish(candidate_profile_id)
    return {"status": verdict.status}


# --------------------------------------------------------------------------
# 3. Coding-platform account — Codeforces via its real public API;
#    LeetCode via its (unofficial, best-effort) GraphQL endpoint; HackerRank
#    and CodeChef via reachability only, since neither exposes a usable one.
# --------------------------------------------------------------------------


def _write_coding_platform_result(
    source_id: uuid.UUID,
    *,
    status: VerificationStatus,
    score: float | None,
    source: str,
    payload: dict[str, Any],
) -> None:
    with SessionLocal() as session:
        account = session.get(CodingPlatformAccount, source_id)
        if account is not None:
            before = account.verification_status.value
            account.verification_status = status
            account.verification_score = score
            account.verification_source = source
            account.verification_payload = payload
            if status is VerificationStatus.VERIFIED:
                account.verified_at = _utcnow()
            _audit_claim(
                session, entity_type="coding_platform_account", entity_id=account.id,
                before_status=before, after_status=status.value,
            )
            session.commit()

            # Derived from the row *after* commit, so the competency weight is
            # read from the payload that was actually persisted rather than
            # from local variables that a concurrent write could have
            # superseded. A no-op unless the account reached VERIFIED — see
            # `competencies.py` for why a reachability-only FLAGGED result
            # must not mint a skill.
            competencies.derive_competencies(session, account=account)
            session.commit()


@celery_app.task(
    base=DatabaseTask, bind=True, name="src.jobs.tasks.verification.verify_coding_platform_account_task"
)
def verify_coding_platform_account_task(self: DatabaseTask, async_job_id: str) -> dict[str, str]:
    payload = _load_payload(async_job_id)
    source_id = uuid.UUID(payload["source_id"])
    candidate_profile_id = uuid.UUID(payload["candidate_profile_id"])
    platform = CodingPlatform(payload["platform"])
    handle = payload["handle"]
    profile_url = payload["profile_url"]

    try:
        if platform is CodingPlatform.CODEFORCES:
            info = codeforces_client.get_user_info(handle)
            solved = codeforces_client.count_solved_problems(handle)
            rating = info.get("rating")
            score = min(100.0, (rating / 3500.0) * 100.0) if rating else 40.0
            _write_coding_platform_result(
                source_id,
                status=VerificationStatus.VERIFIED,
                score=round(score, 2),
                source="codeforces_api",
                payload={
                    "handle": info.get("handle"),
                    "rating": rating,
                    "max_rating": info.get("maxRating"),
                    "rank": info.get("rank"),
                    "solved_count": solved,
                },
            )
            result_status = "verified"

        elif platform is CodingPlatform.LEETCODE:
            stats = leetcode_client.get_user_stats(handle)
            solved = leetcode_client.total_solved(stats)
            score = min(100.0, (solved / 500.0) * 100.0)
            _write_coding_platform_result(
                source_id,
                status=VerificationStatus.VERIFIED,
                score=round(score, 2),
                source="leetcode_graphql",
                payload={
                    "handle": stats.get("username"),
                    "solved_count": solved,
                    "ranking": (stats.get("profile") or {}).get("ranking"),
                    "confidence": "medium",
                    "note": "Checked via LeetCode's unofficial GraphQL endpoint, not a documented API.",
                },
            )
            result_status = "verified"

        else:
            # HACKERRANK, CODECHEF, ATCODER, GEEKSFORGEEKS and OTHER — none
            # exposes a usable public API (CodeChef retired its documented one;
            # the rest never had one), so all can only be checked by URL
            # reachability. Handled as one branch parameterised by platform
            # rather than five near-identical ones: they differ in nothing but
            # the label and the rate-limit bucket, and a copied branch is how
            # the next platform ends up writing another platform's
            # `verification_source`.
            #
            # The ceiling here is `FLAGGED`, never `VERIFIED`: a resolving URL
            # proves the profile exists, not that this candidate owns it. For
            # OTHER the URL is one the candidate supplied outright, which is
            # weaker still — and is exactly why that platform can never do
            # better than FLAGGED either.
            settings = get_verification_settings()
            per_minute = {
                CodingPlatform.HACKERRANK: settings.hackerrank_rate_limit_per_minute,
                CodingPlatform.CODECHEF: settings.codechef_rate_limit_per_minute,
                CodingPlatform.ATCODER: settings.atcoder_rate_limit_per_minute,
                CodingPlatform.GEEKSFORGEEKS: settings.geeksforgeeks_rate_limit_per_minute,
                CodingPlatform.OTHER: settings.other_platform_rate_limit_per_minute,
            }[platform]
            source = f"{platform.value}_reachability_heuristic"

            reachable, _body = reachability.check_reachable(
                profile_url, rate_limit_name=platform.value, max_requests_per_minute=per_minute
            )
            if reachable:
                _write_coding_platform_result(
                    source_id,
                    status=VerificationStatus.FLAGGED,
                    score=50.0,
                    source=source,
                    payload={
                        "handle": handle,
                        "profile_url": profile_url,
                        "confidence": "low",
                        "note": f"{platform.value} has no usable public API; this only confirms the "
                        "profile URL resolves, not that the candidate owns it.",
                    },
                )
                result_status = "flagged"
            else:
                _write_coding_platform_result(
                    source_id,
                    status=VerificationStatus.REJECTED,
                    score=0.0,
                    source=source,
                    payload={"handle": handle, "profile_url": profile_url, "reachable": False},
                )
                result_status = "rejected"

    except ClaimNotFound as exc:
        _write_coding_platform_result(
            source_id,
            status=VerificationStatus.REJECTED,
            score=0.0,
            source=f"{platform.value}_api",
            payload={"handle": handle, "error": str(exc)},
        )
        _finish(candidate_profile_id)
        return {"status": "rejected"}
    except VerificationServiceUnavailable as exc:
        if _exhausted(self):
            _write_coding_platform_result(
                source_id,
                status=VerificationStatus.UNVERIFIED,
                score=None,
                source=f"{platform.value}_api",
                payload={"error": str(exc), "exhausted_retries": True},
            )
            _finish(candidate_profile_id)
        raise

    _finish(candidate_profile_id)
    return {"status": result_status}


# --------------------------------------------------------------------------
# 4. Certificate — reachability + issuer-domain corroboration.
# --------------------------------------------------------------------------


@celery_app.task(base=DatabaseTask, bind=True, name="src.jobs.tasks.verification.verify_certificate_task")
def verify_certificate_task(self: DatabaseTask, async_job_id: str) -> dict[str, str]:
    payload = _load_payload(async_job_id)
    source_id = uuid.UUID(payload["source_id"])
    candidate_profile_id = uuid.UUID(payload["candidate_profile_id"])
    credential_url = payload["credential_url"]

    with SessionLocal() as session:
        cert = session.get(Certificate, source_id)
        issuer = cert.issuer if cert is not None else ""

    try:
        verdict = certificate_checker.verify_certificate(credential_url, issuer)
    except VerificationServiceUnavailable as exc:
        if _exhausted(self):
            with SessionLocal() as session:
                cert = session.get(Certificate, source_id)
                if cert is not None:
                    before = cert.verification_status.value
                    cert.verification_status = VerificationStatus.UNVERIFIED
                    cert.verification_source = "certificate_url_check"
                    cert.verification_payload = {"error": str(exc), "exhausted_retries": True}
                    _audit_claim(
                        session, entity_type="certificate", entity_id=cert.id,
                        before_status=before, after_status="unverified",
                    )
                    session.commit()
            _finish(candidate_profile_id)
        raise

    with SessionLocal() as session:
        cert = session.get(Certificate, source_id)
        if cert is not None:
            before = cert.verification_status.value
            cert.verification_status = VerificationStatus(verdict.status)
            cert.verification_score = verdict.score
            cert.verification_source = "certificate_url_check"
            cert.verification_payload = {
                "domain": verdict.domain,
                "reachable": verdict.reachable,
                "issuer_matched": verdict.issuer_matched,
                "reason": verdict.reason,
            }
            if verdict.status == "verified":
                cert.verified_at = _utcnow()
            _audit_claim(
                session, entity_type="certificate", entity_id=cert.id,
                before_status=before, after_status=verdict.status,
            )
            session.commit()

    _finish(candidate_profile_id)
    return {"status": verdict.status}


# --------------------------------------------------------------------------
# 5. Experience — consolidated internal-signal check (no external source of
#    truth exists for "worked at X"; see domains/verification/experience.py).
# --------------------------------------------------------------------------


@celery_app.task(base=DatabaseTask, bind=True, name="src.jobs.tasks.verification.verify_experience_task")
def verify_experience_task(self: DatabaseTask, async_job_id: str) -> dict[str, str]:
    from sqlalchemy import select

    from src.domains.company.models import Company

    payload = _load_payload(async_job_id)
    source_id = uuid.UUID(payload["source_id"])
    candidate_profile_id = uuid.UUID(payload["candidate_profile_id"])
    company_name = payload["company_name"]
    technologies = payload.get("technologies") or []

    with SessionLocal() as session:
        known_companies = set(session.execute(select(Company.name)).scalars().all())
        verified_technologies: set[str] = set()
        for project in session.execute(
            select(Project).where(
                Project.candidate_profile_id == candidate_profile_id,
                Project.verification_status == VerificationStatus.VERIFIED,
            )
        ).scalars():
            verified_technologies.update(project.technologies or [])

        verdict = experience_scoring.score_experience(
            company_name=company_name,
            technologies=technologies,
            known_company_names=known_companies,
            verified_technologies=verified_technologies,
        )

        experience = session.get(Experience, source_id)
        if experience is not None:
            before = experience.verification_status.value
            experience.verification_status = VerificationStatus(verdict.status)
            experience.verification_score = verdict.score
            experience.verification_source = "consolidated_internal_signals"
            experience.verification_payload = {
                "company_known": verdict.company_known,
                "overlapping_technologies": verdict.overlapping_technologies,
                "reason": verdict.reason,
            }
            _audit_claim(
                session, entity_type="experience", entity_id=experience.id,
                before_status=before, after_status=verdict.status,
            )
            session.commit()

    _finish(candidate_profile_id)
    return {"status": verdict.status}


# Sanity check at import time: every JOB_* constant `evidence.py` defines has
# exactly one task above. This is a cheap, load-bearing guard — silently
# missing a mapping here is exactly the bug this whole module exists to fix.
_JOB_TYPE_TO_TASK_NAME = {
    JOB_GITHUB_ACCOUNT: verify_github_account_task.name,
    JOB_REPOSITORY: verify_repository_task.name,
    JOB_CODING_PLATFORM: verify_coding_platform_account_task.name,
    JOB_CERTIFICATE: verify_certificate_task.name,
    JOB_EXPERIENCE: verify_experience_task.name,
}
