"""The live analysis feed — what the student watches while workers run.

`GET /api/v1/student/onboarding/activity` returns one row per background
stage, each with a real state and a real timestamp. It is the data behind
the "Repository Analysis / Finding technologies… / Analyzing commits…"
screen: a build log, not a spinner.

THE ONE RULE THIS MODULE EXISTS TO ENFORCE: NEVER INVENT PROGRESS

The obvious way to build a satisfying loading screen is a bar that fills on
a timer and a list of stage captions that advance on their own. It is also a
lie, and it is a lie this particular product cannot afford to tell. The
entire proposition is that every claim on a student's profile traces to
something real; a progress bar that advances while nothing is happening is
the same category of dishonesty as a green badge on an unverified claim,
applied to the loading state.

So every field below is derived from a row that a worker actually wrote:

* A stage that has not been enqueued reports `pending` — not "0%".
* A stage that is running reports `running` with the time it started, and
  the client renders elapsed time from that. No percentage is returned,
  because none of these workers can report one: they are third-party API
  calls whose duration is unknown until they finish.
* A stage that failed reports `failed` with the reason, and the UI shows it.
  Hiding a failure behind a spinner that never resolves is the worst
  outcome available here.

WHY DISCRETE STAGES RATHER THAN A PERCENTAGE

A percentage implies a denominator, and the denominator here is genuinely
unknowable at the start: how many repository analyses run depends on how
many repositories the student added, and whether the interview stage runs at
all depends on whether verification settles with anything verified. Discrete
stages with honest states describe that accurately; a single number cannot.

RELATIONSHIP TO `setup_state.py`

`setup_state.py` answers "what has the student filled in", which is about
their own actions and is what the stepper renders. This module answers "what
is the platform doing about it", which is about workers. They are separate
because they change at different times and for different reasons — a student
can complete every section (setup_state fully green) while every
verification is still pending (activity fully in flight).
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domains.interview.models import Interview, InterviewStatus
from src.domains.matching.models import EmbeddableEntityType, Embedding
from src.domains.student.evidence import (
    JOB_CERTIFICATE,
    JOB_CODING_PLATFORM,
    JOB_EXPERIENCE,
    JOB_GITHUB_ACCOUNT,
    JOB_REPOSITORY,
)
from src.domains.student.models import (
    Certificate,
    CodingPlatformAccount,
    Experience,
    GithubAccount,
    Project,
    VerificationStatus,
)
from src.platform.models import AsyncJob, AsyncJobStatus


class StageState(str, enum.Enum):
    """What one stage is doing.

    `SKIPPED` is a real, non-failure outcome and is distinct from `PENDING`:
    a student with no certificates has no certificate stage to run, and
    showing that row as permanently "queued" would leave the screen looking
    stuck forever on work that will never happen.
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    #: Ran to completion, but what it found did not confirm the claim. Not a
    #: failure of the *stage* — the check worked; the evidence did not hold.
    #: The UI renders this amber, never red.
    INCONCLUSIVE = "inconclusive"
    FAILED = "failed"
    SKIPPED = "skipped"


#: Stage identity. Ordered as the pipeline actually runs, which is the order
#: the client renders — a log that lists its lines out of causal order is
#: harder to read than one with no order at all.
class StageKey(str, enum.Enum):
    GITHUB_ACCOUNT = "github_account"
    REPOSITORIES = "repositories"
    CODING_PROFILES = "coding_profiles"
    CERTIFICATES = "certificates"
    EXPERIENCE = "experience"
    #: Not a verification. Runs after the section requirements are met and is
    #: what makes a profile findable at all, so the student is shown it.
    INDEXING = "indexing"
    INTERVIEW = "interview"


@dataclass(frozen=True)
class Stage:
    key: StageKey
    #: Shown as the log line's title. Present tense while running, past tense
    #: once settled — resolved on the client, which is why both the state and
    #: the raw counts are returned rather than a pre-rendered sentence.
    label: str
    state: StageState
    #: How many claims this stage covers. `0` with state `SKIPPED` is the
    #: "nothing to check" case.
    total: int = 0
    settled: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    #: Present only on `FAILED`. Student-facing, never a stack trace.
    detail: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.state in (
            StageState.SUCCEEDED,
            StageState.INCONCLUSIVE,
            StageState.FAILED,
            StageState.SKIPPED,
        )


@dataclass(frozen=True)
class ActivityFeed:
    stages: tuple[Stage, ...]
    #: True while any stage is still pending or running. The client stops
    #: polling on false — derived here rather than client-side so there is
    #: one definition of "finished" and the poll cannot outlive the work.
    is_running: bool
    #: Server time at which this snapshot was taken. The client computes
    #: elapsed time against this rather than against its own clock, so a
    #: device with a skewed clock does not render negative durations.
    as_of: datetime


#: Claim model + job type for each verification stage. One table rather than
#: five near-identical query blocks: they differ only in these two values,
#: and a copied block is how the certificate stage ends up reporting the
#: experience stage's counts.
_VERIFICATION_STAGES: tuple[tuple[StageKey, str, type, str], ...] = (
    (StageKey.GITHUB_ACCOUNT, "GitHub account", GithubAccount, JOB_GITHUB_ACCOUNT),
    (StageKey.REPOSITORIES, "Repository analysis", Project, JOB_REPOSITORY),
    (StageKey.CODING_PROFILES, "Coding profiles", CodingPlatformAccount, JOB_CODING_PLATFORM),
    (StageKey.CERTIFICATES, "Certificates", Certificate, JOB_CERTIFICATE),
    (StageKey.EXPERIENCE, "Experience", Experience, JOB_EXPERIENCE),
)

#: Statuses that mean a check ran and reached a conclusion.
_SETTLED = (
    VerificationStatus.VERIFIED,
    VerificationStatus.REJECTED,
    VerificationStatus.FLAGGED,
    VerificationStatus.UNVERIFIED,
)


def _stage_state(*, total: int, settled: int, verified: int, running: bool) -> StageState:
    """Collapse per-claim outcomes into one stage state.

    `INCONCLUSIVE` when everything settled but nothing verified: the check
    completed and the evidence did not hold, which is a legitimate result the
    student needs to see as distinct from both success and error. Rendering
    it as `SUCCEEDED` would tell them their claims were confirmed when they
    were not — the exact failure this platform exists to prevent, relocated
    into the loading screen.
    """
    if total == 0:
        return StageState.SKIPPED
    if settled < total:
        return StageState.RUNNING if running else StageState.PENDING
    return StageState.SUCCEEDED if verified > 0 else StageState.INCONCLUSIVE


def _jobs_by_type(
    db: Session, candidate_profile_id: uuid.UUID, job_types: tuple[str, ...]
) -> dict[str, list[AsyncJob]]:
    """Every async job of the given types belonging to this candidate.

    `payload` is JSONB and holds `candidate_profile_id` as a string for every
    verification job (`evidence.py` writes it). Filtering in Python rather
    than with a JSONB containment operator is deliberate at this scale: a
    single student has tens of these rows, the query is already bounded by
    `job_type`, and a `->>` filter would need an expression index to be worth
    anything. If this ever runs over all students it must become an indexed
    containment query — flagged here rather than discovered later.
    """
    rows = db.execute(select(AsyncJob).where(AsyncJob.job_type.in_(job_types))).scalars()

    grouped: dict[str, list[AsyncJob]] = {job_type: [] for job_type in job_types}
    wanted = str(candidate_profile_id)
    for row in rows:
        payload = row.payload or {}
        if payload.get("candidate_profile_id") == wanted:
            grouped[row.job_type].append(row)
    return grouped


def build_activity_feed(db: Session, candidate_profile_id: uuid.UUID, *, now: datetime) -> ActivityFeed:
    """Assemble the feed. Read-only; writes nothing, enqueues nothing."""
    job_types = tuple(job_type for _, _, _, job_type in _VERIFICATION_STAGES)
    jobs = _jobs_by_type(db, candidate_profile_id, job_types)

    stages: list[Stage] = []

    for key, label, model, job_type in _VERIFICATION_STAGES:
        claims = list(
            db.execute(
                select(model.verification_status).where(
                    model.candidate_profile_id == candidate_profile_id,
                    model.deleted_at.is_(None),
                )
            ).scalars()
        )
        total = len(claims)
        settled = sum(status in _SETTLED for status in claims)
        verified = sum(status is VerificationStatus.VERIFIED for status in claims)

        stage_jobs = jobs.get(job_type, [])
        running = any(job.status is AsyncJobStatus.RUNNING for job in stage_jobs)
        started = [job.started_at for job in stage_jobs if job.started_at is not None]
        finished = [job.finished_at for job in stage_jobs if job.finished_at is not None]

        # A dead-lettered job is the one case where the *stage* failed rather
        # than the claim being unproven — retries were exhausted without the
        # worker ever reaching a verdict.
        dead = next((job for job in stage_jobs if job.dead_lettered_at is not None), None)

        if dead is not None:
            state = StageState.FAILED
            detail = "We could not reach the source to check this. You can retry from your profile."
        else:
            state = _stage_state(total=total, settled=settled, verified=verified, running=running)
            detail = None

        stages.append(
            Stage(
                key=key,
                label=label,
                state=state,
                total=total,
                settled=settled,
                started_at=min(started) if started else None,
                # Only meaningful once every job for the stage has finished;
                # the max of a partial set would claim the stage ended while
                # one of its checks was still running.
                finished_at=max(finished) if finished and len(finished) == len(stage_jobs) else None,
                detail=detail,
            )
        )

    stages.append(_indexing_stage(db, candidate_profile_id))
    stages.append(_interview_stage(db, candidate_profile_id))

    return ActivityFeed(
        stages=tuple(stages),
        is_running=any(not stage.is_terminal for stage in stages),
        as_of=now,
    )


def _indexing_stage(db: Session, candidate_profile_id: uuid.UUID) -> Stage:
    """Whether a profile vector exists.

    Binary and cheap — the embedding either exists for the current model
    version or it does not. `get_embedding` is not reused here because it
    takes the entity type as an argument and this only ever asks one
    question; importing the matching domain's session helpers for a single
    existence check would couple the two more tightly than the answer is
    worth.
    """
    exists = (
        db.execute(
            select(Embedding.id)
            .where(
                Embedding.entity_type == EmbeddableEntityType.CANDIDATE_PROFILE,
                Embedding.entity_id == candidate_profile_id,
            )
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )
    return Stage(
        key=StageKey.INDEXING,
        label="Profile indexing",
        state=StageState.SUCCEEDED if exists else StageState.PENDING,
        total=1,
        settled=1 if exists else 0,
    )


def _interview_stage(db: Session, candidate_profile_id: uuid.UUID) -> Stage:
    """The interview's own lifecycle, which is not a verification.

    Reported because it is the last thing standing between the student and
    discoverability, and because the invitation arrives by email — a student
    who missed that email has no other way to learn the interview is waiting.
    """
    interview = db.execute(
        select(Interview)
        .where(Interview.candidate_profile_id == candidate_profile_id)
        .order_by(Interview.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if interview is None:
        return Stage(
            key=StageKey.INTERVIEW,
            label="Interview preparation",
            state=StageState.PENDING,
            total=1,
        )

    # PENDING here is the *question generation* job, which is real work the
    # student is waiting on — distinct from "no interview exists yet".
    state = {
        InterviewStatus.PENDING: StageState.RUNNING,
        InterviewStatus.IN_PROGRESS: StageState.SUCCEEDED,
        InterviewStatus.EVALUATING: StageState.SUCCEEDED,
        InterviewStatus.COMPLETED: StageState.SUCCEEDED,
        InterviewStatus.FAILED: StageState.FAILED,
    }.get(interview.status, StageState.PENDING)

    return Stage(
        key=StageKey.INTERVIEW,
        label="Interview preparation",
        state=state,
        total=1,
        settled=1 if state is StageState.SUCCEEDED else 0,
        started_at=interview.created_at,
        detail=(
            "We could not prepare your interview. Our team has been notified."
            if state is StageState.FAILED
            else None
        ),
    )
