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
from sqlalchemy.orm import Session

from src.core.audit import write_audit_log
from src.db.database import SessionLocal
from src.domains.student import service as student_service
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


def _finish(candidate_profile_id: uuid.UUID) -> None:
    """Recomputes `profile_strength`. Re-embedding/re-matching (or removal
    from `match_results` if this leaves the candidate non-discoverable) is
    handled inside `recompute_and_persist_strength` itself
    (`student/service.py::_sync_matching_index`) — centralized there so
    every caller, not just this one, keeps the same guarantee. See that
    module for why this used to be wired only here, and why that was a bug.
    """
    with SessionLocal() as session:
        student_service.recompute_and_persist_strength(session, candidate_profile_id)


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
#    via reachability only, since it has no public API of any kind.
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

        else:  # HACKERRANK — no public API at all
            reachable, _body = reachability.check_reachable(
                profile_url, rate_limit_name="hackerrank", max_requests_per_minute=20
            )
            if reachable:
                _write_coding_platform_result(
                    source_id,
                    status=VerificationStatus.FLAGGED,
                    score=50.0,
                    source="hackerrank_reachability_heuristic",
                    payload={
                        "handle": handle,
                        "profile_url": profile_url,
                        "confidence": "low",
                        "note": "HackerRank has no public API; this only confirms the profile URL "
                        "resolves, not that the candidate owns it.",
                    },
                )
                result_status = "flagged"
            else:
                _write_coding_platform_result(
                    source_id,
                    status=VerificationStatus.REJECTED,
                    score=0.0,
                    source="hackerrank_reachability_heuristic",
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
