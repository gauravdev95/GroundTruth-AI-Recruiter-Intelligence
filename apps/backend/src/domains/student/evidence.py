"""Queues verification work for the claims a student submits.

When a student saves a GitHub username, a coding-platform handle, a repo URL,
a certificate credential URL, or (as of this module's `queue_experience`) an
experience entry, two things happen inside the same transaction as the
section write:

1. the claim row's `verification_status` is set to `PENDING`, and
2. an `AsyncJob` row is enqueued with `status=PENDING` for the worker that
   will actually fetch and judge it (`src/jobs/tasks/verification.py`).

Why `AsyncJob` and not `evidence_records`: `evidence_records`
(`docs/DATA_MODEL.md` §3) is a derived *scoring* hub. It carries
`weight NUMERIC NOT NULL` and a `source_type` that names finished artifacts
(`repository_analysis`, `coding_platform_snapshot`) — none of which exist at
claim time — and it has no `status` column at all. Writing speculative rows
into it would break the §0.5 guarantee that every evidence record traces back
to concrete analyzed evidence. `evidence_records` stays unbuilt; this layer's
own `verification_score`/`verification_source`/`verification_payload`
columns (added alongside `verify_*` consumers) are where the check's outcome
and its audit trail live instead.

**This module never writes `VERIFIED`, `REJECTED`, or `FLAGGED`.** Only
`PENDING` — the statement below is the only status assignment in the whole
builder layer. Those three are written exclusively by the consumers in
`src/jobs/tasks/verification.py`.

**Enqueue vs. dispatch.** `queue_*` only writes the `AsyncJob` row inside the
caller's transaction — it does not publish to Celery, for the same reason
`resume/service.py::create_upload` publishes only after `db.commit()`: a
publish that races ahead of the row it depends on is worse than a job that
sits `PENDING` for a moment. `dispatch_all()` below is the second half of
that contract; callers (`student/service.py`) call it once, after the section
save has committed, with every `QueuedVerification` the save produced.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

import structlog

from src.domains.student.models import (
    Certificate,
    CodingPlatformAccount,
    Experience,
    GithubAccount,
    Project,
    VerificationStatus,
)
from src.platform.models import AsyncJob, AsyncJobStatus

logger = structlog.get_logger(__name__)

JOB_GITHUB_ACCOUNT = "verify_github_account"
JOB_CODING_PLATFORM = "verify_coding_platform_account"
JOB_REPOSITORY = "verify_repository"
JOB_CERTIFICATE = "verify_certificate"
JOB_EXPERIENCE = "verify_experience"

# Source-table discriminators recorded in the job payload so a worker can
# find its target row without a polymorphic FK. Mirrors the naming
# `evidence_records.source_type` will use in Phase II.
SOURCE_GITHUB_ACCOUNT = "github_account"
SOURCE_CODING_PLATFORM_ACCOUNT = "coding_platform_account"
SOURCE_PROJECT = "project"
SOURCE_CERTIFICATE = "certificate"
SOURCE_EXPERIENCE = "experience"


@dataclass(frozen=True)
class QueuedVerification:
    async_job_id: uuid.UUID
    job_type: str
    source_type: str
    source_id: uuid.UUID


def _has_open_job(db: Session, *, job_type: str, source_id: uuid.UUID) -> bool:
    """True when this exact claim already has unfinished work queued.

    Re-saving a section that didn't change must not pile up duplicate jobs,
    so an existing pending/running job for the same source row suppresses a
    new one. Keyed on the JSONB payload's `source_id` rather than a column,
    since `async_jobs` is deliberately schemaless about its subject
    (`docs/DATA_MODEL.md` §7).
    """
    stmt = (
        select(AsyncJob.id)
        .where(
            AsyncJob.job_type == job_type,
            AsyncJob.status.in_((AsyncJobStatus.PENDING, AsyncJobStatus.RUNNING)),
            AsyncJob.payload["source_id"].astext == str(source_id),
        )
        .limit(1)
    )
    return db.execute(stmt).first() is not None


def _enqueue(
    db: Session,
    *,
    job_type: str,
    source_type: str,
    source_id: uuid.UUID,
    candidate_profile_id: uuid.UUID,
    target: dict[str, object],
) -> QueuedVerification | None:
    if _has_open_job(db, job_type=job_type, source_id=source_id):
        return None

    job = AsyncJob(
        job_type=job_type,
        status=AsyncJobStatus.PENDING,
        payload={
            "source_type": source_type,
            "source_id": str(source_id),
            "candidate_profile_id": str(candidate_profile_id),
            **target,
        },
    )
    db.add(job)
    db.flush()  # assign job.id so the caller can dispatch it after commit
    return QueuedVerification(
        async_job_id=job.id, job_type=job_type, source_type=source_type, source_id=source_id
    )


def queue_github_account(db: Session, account: GithubAccount) -> QueuedVerification | None:
    """Insertion point 1 — a submitted GitHub username/URL."""
    account.verification_status = VerificationStatus.PENDING
    return _enqueue(
        db,
        job_type=JOB_GITHUB_ACCOUNT,
        source_type=SOURCE_GITHUB_ACCOUNT,
        source_id=account.id,
        candidate_profile_id=account.candidate_profile_id,
        target={"github_username": account.github_username, "profile_url": account.profile_url},
    )


def queue_coding_platform_account(db: Session, account: CodingPlatformAccount) -> QueuedVerification | None:
    """Insertion point 2 — a submitted competitive-programming handle."""
    account.verification_status = VerificationStatus.PENDING
    return _enqueue(
        db,
        job_type=JOB_CODING_PLATFORM,
        source_type=SOURCE_CODING_PLATFORM_ACCOUNT,
        source_id=account.id,
        candidate_profile_id=account.candidate_profile_id,
        target={
            "platform": account.platform.value,
            "handle": account.handle,
            "profile_url": account.profile_url,
        },
    )


def queue_project_repository(db: Session, project: Project) -> QueuedVerification | None:
    """Insertion point 3 — a submitted repository URL.

    Only repository-kind projects are queued: a described project has no URL
    to fetch, so it stays `UNVERIFIED` rather than pending forever.
    """
    if not project.repo_url:
        return None
    project.verification_status = VerificationStatus.PENDING
    return _enqueue(
        db,
        job_type=JOB_REPOSITORY,
        source_type=SOURCE_PROJECT,
        source_id=project.id,
        candidate_profile_id=project.candidate_profile_id,
        target={"repo_url": project.repo_url},
    )


def queue_certificate(db: Session, certificate: Certificate) -> QueuedVerification | None:
    """Insertion point 4 — a submitted certificate credential URL.

    A certificate with no credential URL has nothing to check, so it stays
    `UNVERIFIED`.
    """
    if not certificate.credential_url:
        return None
    certificate.verification_status = VerificationStatus.PENDING
    return _enqueue(
        db,
        job_type=JOB_CERTIFICATE,
        source_type=SOURCE_CERTIFICATE,
        source_id=certificate.id,
        candidate_profile_id=certificate.candidate_profile_id,
        target={"credential_url": certificate.credential_url},
    )


def queue_experience(db: Session, experience: Experience) -> QueuedVerification | None:
    """Insertion point 5 — an experience entry.

    Added alongside the other four `verify_*` consumers: unlike them,
    `experiences` previously carried no verification state at all. There is
    no external source of truth for "worked at X", so `verify_experience_task`
    can only ever move this to `FLAGGED` (weak internal corroboration found)
    or leave it `UNVERIFIED` — it is queued anyway, both for the badge
    consistency the stepper UI expects across all five sections and because
    "consolidated handling" (the technology-overlap and known-company checks
    the task runs) still has genuine information value even without a
    verdict as strong as `VERIFIED`.
    """
    experience.verification_status = VerificationStatus.PENDING
    return _enqueue(
        db,
        job_type=JOB_EXPERIENCE,
        source_type=SOURCE_EXPERIENCE,
        source_id=experience.id,
        candidate_profile_id=experience.candidate_profile_id,
        target={
            "company_name": experience.company_name,
            "title": experience.title,
            "technologies": list(experience.technologies),
        },
    )


# --------------------------------------------------------------------------
# Dispatch — the second half of the enqueue contract
# --------------------------------------------------------------------------

# job_type -> queue is fixed at import time inside `dispatch_all` (not at
# module scope) purely to avoid a circular import: `jobs/tasks/verification.py`
# does not import this module, but importing it eagerly here would still
# force `src.jobs.celery_app` to load before `src.domains.student.evidence`
# does, which is the same ordering hazard `resume/service.py::create_upload`
# avoids by importing its task inside the function body.


def dispatch_all(queued: list[QueuedVerification | None]) -> None:
    """Publish every queued verification job to Celery.

    Call this **after** the transaction that produced `queued` has committed
    — never before, and never instead of committing first. Each `AsyncJob`
    row already exists (see `_enqueue`); this only makes the broker aware of
    it. A publish failure is logged and swallowed by
    `jobs.dispatch.dispatch()` itself, so a Redis outage degrades to "the job
    sits `PENDING` until a requeue", not a failed profile save.
    """
    from src.jobs import dispatch as job_dispatch
    from src.jobs.celery_app import QUEUE_VERIFICATION
    from src.jobs.tasks.verification import (
        verify_certificate_task,
        verify_coding_platform_account_task,
        verify_experience_task,
        verify_github_account_task,
        verify_repository_task,
    )

    task_by_job_type = {
        JOB_GITHUB_ACCOUNT: verify_github_account_task,
        JOB_CODING_PLATFORM: verify_coding_platform_account_task,
        JOB_REPOSITORY: verify_repository_task,
        JOB_CERTIFICATE: verify_certificate_task,
        JOB_EXPERIENCE: verify_experience_task,
    }

    for item in queued:
        if item is None:
            continue
        task = task_by_job_type.get(item.job_type)
        if task is None:
            # Defensive only — every JOB_* constant above has an entry.
            logger.error("verification_dispatch_unknown_job_type", job_type=item.job_type)
            continue
        job_dispatch.dispatch(
            _AsyncJobRef(item.async_job_id), task, queue=QUEUE_VERIFICATION
        )


class _AsyncJobRef:
    """Duck-types the one attribute `jobs.dispatch.dispatch()` reads off a job.

    `dispatch()` takes the full `AsyncJob` ORM object in the resume-upload
    call site because that caller already has it in hand. Here, `_enqueue`
    only threads the id back out through `QueuedVerification` (the row itself
    is flushed, not re-fetched), so this is a minimal stand-in rather than an
    extra round trip to reload a row this function never otherwise needs.
    """

    def __init__(self, job_id: uuid.UUID) -> None:
        self.id = job_id
