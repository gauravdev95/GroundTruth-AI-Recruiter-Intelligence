"""Business logic for the live code-grounded AI interview.

`start_interview` is the only place `RepositoryNotVerified`/
`InterviewAlreadyExists` are raised — every other function here trusts that
an `Interview` row it's given already passed those checks, since a row only
exists once `start_interview` created it.

`advance` is the heart of the live session: one call, one turn. It is the only
function that writes conversation rows, which is what keeps the graph's nodes
free of database work (see `graph/nodes.py`) and means a turn either lands
completely or not at all.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session

from src.core.exceptions import Forbidden, NotFound
from src.domains.auth.models import CandidateProfile
from src.domains.interview.exceptions import (
    InterviewAlreadyExists,
    InterviewFinished,
    InterviewNotComplete,
    InterviewNotReady,
    InterviewTurnInProgress,
    RepositoryNotVerified,
)
from src.domains.interview.graph import run_turn
from src.domains.interview.models import (
    CandidateComfort,
    Interview,
    InterviewDimensionScore,
    InterviewGrounding,
    InterviewIntegrityEvent,
    InterviewQuestion,
    InterviewStage,
    InterviewStatus,
    InterviewTurn,
    InterviewVerificationFlag,
    TurnRole,
    get_current_rubric_version,
    get_rubric_weights,
)
from src.domains.interview.schemas import (
    DimensionScoreResponse,
    EvidenceReportResponse,
    IntegrityEventRequest,
    IntegrityEventResponse,
    IntegritySummaryResponse,
    InterviewStateResponse,
    InterviewSummaryResponse,
    TurnResponse,
)
from src.domains.skills.models import CandidateSkill, Skill
from src.domains.student.models import (
    Certificate,
    CodingPlatformAccount,
    Experience,
    Project,
    ProjectKind,
    VerificationStatus,
)

logger = structlog.get_logger(__name__)

# Non-terminal-failure statuses: a row in one of these blocks a new attempt
# at the same repository. `FAILED` does not — see `models.py`'s module
# docstring for why a failed attempt must not permanently lock the repo out.
_BLOCKING_STATUSES = (
    InterviewStatus.PENDING,
    InterviewStatus.IN_PROGRESS,
    InterviewStatus.EVALUATING,
    InterviewStatus.COMPLETED,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_owned_project(db: Session, profile: CandidateProfile, project_id: uuid.UUID) -> Project:
    project = db.execute(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    ).scalar_one_or_none()
    if project is None:
        raise NotFound("Project not found")
    if project.candidate_profile_id != profile.id:
        raise Forbidden()
    return project


def _get_owned_interview(db: Session, profile: CandidateProfile, interview_id: uuid.UUID) -> Interview:
    interview = db.get(Interview, interview_id)
    if interview is None:
        raise NotFound("Interview not found")
    if interview.candidate_profile_id != profile.id:
        raise Forbidden()
    return interview


def build_repository_context(project: Project) -> dict:
    """The stored analysis every question, check and score is grounded in —
    exactly what `Project.verification_payload` holds, nothing re-fetched
    from GitHub at interview time. See `verify_repository_task`'s payload
    write in `jobs/tasks/verification.py` for the shape."""
    payload = dict(project.verification_payload or {})
    payload["title"] = project.title
    payload["repo_url"] = project.repo_url
    payload["grounding"] = InterviewGrounding.REPOSITORY.value
    return payload


def build_profile_context(db: Session, candidate_profile_id: uuid.UUID) -> dict:
    """The candidate-level evidence a profile interview is grounded in.

    Assembled from *verified* rows only — the same bar the rest of the platform
    applies. A profile interview that could ask about an unverified claim would
    let a candidate be examined on, and credited for, something nobody checked,
    which is the failure mode this whole system exists to prevent.

    Deliberately mirrors `build_repository_context`'s flat-dict shape so both
    satisfy the one `repository_context` parameter on the provider protocols
    (`domains/ai/llm.py`) without a second code path through the adapters.
    """
    projects = list(
        db.execute(
            select(Project).where(
                Project.candidate_profile_id == candidate_profile_id,
                Project.verification_status == VerificationStatus.VERIFIED,
                Project.deleted_at.is_(None),
            )
        ).scalars()
    )
    coding_accounts = list(
        db.execute(
            select(CodingPlatformAccount).where(
                CodingPlatformAccount.candidate_profile_id == candidate_profile_id,
                CodingPlatformAccount.verification_status == VerificationStatus.VERIFIED,
                CodingPlatformAccount.deleted_at.is_(None),
            )
        ).scalars()
    )
    # Certificates and experience are included at FLAGGED as well as VERIFIED:
    # neither can reach VERIFIED in every legitimate case (an experience never
    # can — no third-party source of truth exists), and excluding them would
    # make a profile interview unable to ask about a candidate's actual work
    # history. They are labelled with their status so the generator can weight
    # them accordingly rather than treating them as proven.
    corroborated = (VerificationStatus.VERIFIED, VerificationStatus.FLAGGED)
    certificates = list(
        db.execute(
            select(Certificate).where(
                Certificate.candidate_profile_id == candidate_profile_id,
                Certificate.verification_status.in_(corroborated),
                Certificate.deleted_at.is_(None),
            )
        ).scalars()
    )
    experiences = list(
        db.execute(
            select(Experience).where(
                Experience.candidate_profile_id == candidate_profile_id,
                Experience.verification_status.in_(corroborated),
                Experience.deleted_at.is_(None),
            )
        ).scalars()
    )
    skills = db.execute(
        select(Skill.name, CandidateSkill.proficiency, CandidateSkill.evidence_weight)
        .join(CandidateSkill, CandidateSkill.skill_id == Skill.id)
        .where(CandidateSkill.candidate_profile_id == candidate_profile_id)
        .order_by(CandidateSkill.evidence_weight.desc())
    ).all()

    return {
        "grounding": InterviewGrounding.PROFILE.value,
        "title": "Candidate profile",
        "repositories": [
            {
                "title": p.title,
                "repo_url": p.repo_url,
                "analysis": p.verification_payload or {},
            }
            for p in projects
        ],
        "coding_profiles": [
            {
                "platform": a.platform.value,
                "handle": a.handle,
                "stats": a.verification_payload or {},
            }
            for a in coding_accounts
        ],
        "verified_skills": [
            {"name": name, "proficiency": prof.value, "evidence_weight": float(weight)}
            for name, prof, weight in skills
        ],
        "certificates": [
            {
                "title": c.title,
                "issuer": c.issuer,
                "verification_status": c.verification_status.value,
            }
            for c in certificates
        ],
        "experience": [
            {
                "company_name": e.company_name,
                "title": e.title,
                "employment_type": e.employment_type.value,
                "technologies": list(e.technologies or []),
                "verification_status": e.verification_status.value,
            }
            for e in experiences
        ],
    }


def build_interview_context(db: Session, interview: Interview) -> dict:
    """Dispatch to the right grounding builder for `interview`.

    The single entry point every agent's caller uses, so neither the graph nor
    the worker has to know which shape it is dealing with — adding a third
    grounding means adding a branch here, not editing three call sites.
    """
    if interview.grounding is InterviewGrounding.PROFILE:
        return build_profile_context(db, interview.candidate_profile_id)

    project = db.get(Project, interview.project_id) if interview.project_id else None
    if project is None:
        raise NotFound(f"Project {interview.project_id} no longer exists")
    return build_repository_context(project)


def start_interview(db: Session, profile: CandidateProfile, project_id: uuid.UUID) -> Interview:
    project = _get_owned_project(db, profile, project_id)

    # The authorship gate, enforced here as well as in the pipeline. A repo
    # that failed stage 2 is never `VERIFIED`, so this check already covers it
    # — but the interview is the one thing the flow explicitly says must not
    # be generated for unauthored code, and it is worth the check being
    # legible at the point of generation rather than inferred two modules away.
    if (
        project.kind is not ProjectKind.REPOSITORY
        or project.verification_status is not VerificationStatus.VERIFIED
        or not project.verification_payload
    ):
        raise RepositoryNotVerified()

    existing = db.execute(
        select(Interview).where(
            Interview.candidate_profile_id == profile.id,
            Interview.project_id == project_id,
            Interview.status.in_(_BLOCKING_STATUSES),
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise InterviewAlreadyExists()

    return _create_and_dispatch(
        db,
        candidate_profile_id=profile.id,
        grounding=InterviewGrounding.REPOSITORY,
        project_id=project_id,
    )


def _create_and_dispatch(
    db: Session,
    *,
    candidate_profile_id: uuid.UUID,
    grounding: InterviewGrounding,
    project_id: uuid.UUID | None,
) -> Interview:
    """Persist the interview row, then queue question generation.

    Shared by both entry points so the row and the job can never diverge.
    `rubric_version` and `time_limit_seconds` are both stamped here, at
    creation, so an attempt is scored under the rubric and held to the clock
    that were in force when it was generated — an operator changing either
    mid-interview must not reach a session already underway.
    """
    from src.config.config import get_interview_settings

    interview = Interview(
        candidate_profile_id=candidate_profile_id,
        project_id=project_id,
        grounding=grounding,
        rubric_version=get_current_rubric_version(),
        time_limit_seconds=get_interview_settings().interview_time_limit_seconds,
        status=InterviewStatus.PENDING,
        stage=InterviewStage.WARMUP,
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)

    from src.jobs import dispatch as job_dispatch
    from src.jobs.celery_app import QUEUE_EXTRACTION
    from src.jobs.tasks.interview import generate_interview_questions_task

    job = job_dispatch.create_job(
        db,
        job_type="generate_interview_questions",
        payload={"interview_id": str(interview.id)},
    )
    job_dispatch.dispatch(job, generate_interview_questions_task, queue=QUEUE_EXTRACTION)

    logger.info(
        "interview_started",
        interview_id=str(interview.id),
        grounding=grounding.value,
        project_id=str(project_id) if project_id else None,
    )
    return interview


def start_profile_interview(db: Session, candidate_profile_id: uuid.UUID) -> Interview | None:
    """Start the candidate-level interview, or return None if one already exists.

    Returns rather than raises on "already exists" because the only caller is
    the verification worker (`jobs/tasks/verification.py::_finish`), which runs
    every time *any* claim finishes verifying. Raising would turn the ordinary
    second, third and fourth verification of the same candidate into a failed
    job — the condition is expected, not exceptional.

    No `RepositoryNotVerified` gate: this interview exists precisely for
    candidates who have no verified repository. Its grounding comes from
    whatever verified evidence they do have (`build_profile_context`).
    """
    existing = db.execute(
        select(Interview).where(
            Interview.candidate_profile_id == candidate_profile_id,
            Interview.grounding == InterviewGrounding.PROFILE,
            Interview.status.in_(_BLOCKING_STATUSES),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None

    return _create_and_dispatch(
        db,
        candidate_profile_id=candidate_profile_id,
        grounding=InterviewGrounding.PROFILE,
        project_id=None,
    )


# ---------------------------------------------------------------------------
# The live session
# ---------------------------------------------------------------------------


def _load_turns(db: Session, interview_id: uuid.UUID) -> list[InterviewTurn]:
    """Explicit query rather than relationship access — this session lives
    across several statements within one turn, and a relationship attribute,
    once lazy-loaded, does not refresh itself just because a later flush
    changed the underlying rows. The same reasoning `student/service.py`'s
    `_active_*` helpers already follow."""
    return list(
        db.execute(
            select(InterviewTurn)
            .where(InterviewTurn.interview_id == interview_id)
            .order_by(InterviewTurn.sequence)
        ).scalars()
    )


def _load_questions(db: Session, interview_id: uuid.UUID) -> list[InterviewQuestion]:
    return list(
        db.execute(
            select(InterviewQuestion)
            .where(InterviewQuestion.interview_id == interview_id)
            .order_by(InterviewQuestion.sequence)
        ).scalars()
    )


def transcript_dicts(turns: list[InterviewTurn]) -> list[dict]:
    """The transcript in the shape every agent reads it in."""
    return [
        {
            "role": turn.role.value,
            "text": turn.text,
            "question_index": turn.question_index,
            "internal_notes": turn.internal_notes,
            "ts": turn.spoken_at.timestamp() if turn.spoken_at else None,
        }
        for turn in turns
    ]


def question_dicts(questions: list[InterviewQuestion]) -> list[dict]:
    return [
        {
            "sequence": question.sequence,
            "prompt": question.prompt,
            "grounded_in": question.grounded_in,
            "expected_signals": question.expected_signals or [],
        }
        for question in questions
    ]


def load_transcript(db: Session, interview_id: uuid.UUID) -> list[dict]:
    """The whole conversation, agent-ready. The worker's entry point — it
    scores from the same shape the live agents read, so what the Scorer sees is
    what the Interviewer saw."""
    return transcript_dicts(_load_turns(db, interview_id))


def load_question_payload(db: Session, interview_id: uuid.UUID) -> list[dict]:
    return question_dicts(_load_questions(db, interview_id))


def _lock_session(db: Session, interview_id: uuid.UUID) -> Interview:
    """Take the session row for the duration of one turn.

    `NOWAIT` rather than a plain lock: a second tab arriving mid-turn should be
    told so immediately, not left holding a connection until a model call
    finishes. Two participants in one interview is not a case to serialise.
    """
    try:
        interview = db.execute(
            select(Interview).where(Interview.id == interview_id).with_for_update(nowait=True)
        ).scalar_one_or_none()
    except (OperationalError, DBAPIError) as exc:
        db.rollback()
        raise InterviewTurnInProgress() from exc
    if interview is None:
        raise NotFound("Interview not found")
    return interview


def _next_sequence(db: Session, interview_id: uuid.UUID) -> int:
    highest = db.execute(
        select(func.max(InterviewTurn.sequence)).where(InterviewTurn.interview_id == interview_id)
    ).scalar()
    return (highest or 0) + 1


def advance(
    db: Session,
    profile: CandidateProfile,
    interview_id: uuid.UUID,
    *,
    message: str | None,
) -> InterviewStateResponse:
    """Run exactly one turn of the conversation.

    `message=None` opens the interview; every later call carries what the
    candidate said. The whole turn — the candidate's words, the verification
    flags they produced, the interviewer's reply, and the session bookkeeping —
    commits together, so a model call that fails halfway leaves the
    conversation exactly where it was rather than half-advanced.
    """
    interview = _get_owned_interview(db, profile, interview_id)
    if interview.status is InterviewStatus.PENDING:
        raise InterviewNotReady()
    if interview.status is not InterviewStatus.IN_PROGRESS or interview.stage is InterviewStage.DONE:
        raise InterviewFinished()

    interview = _lock_session(db, interview_id)
    turns = _load_turns(db, interview_id)
    questions = _load_questions(db, interview_id)

    if message is None and turns:
        # The opener has already been spoken. A client that reconnects should
        # read the transcript, not ask for a second opening.
        raise InterviewFinished()

    candidate_turn: InterviewTurn | None = None
    if message is not None:
        candidate_turn = InterviewTurn(
            interview_id=interview.id,
            sequence=_next_sequence(db, interview.id),
            role=TurnRole.CANDIDATE,
            text=message,
            question_index=interview.current_question_index,
        )
        db.add(candidate_turn)
        db.flush()
        turns = [*turns, candidate_turn]

    if interview.started_at is None:
        interview.started_at = _utcnow()

    context = build_interview_context(db, interview)
    existing_flags = [
        {"claim": flag.claim, "evidence": flag.evidence, "status": flag.status, "severity": flag.severity}
        for flag in db.execute(
            select(InterviewVerificationFlag).where(
                InterviewVerificationFlag.interview_id == interview.id
            )
        ).scalars()
    ]

    result = run_turn(
        {
            "candidate_id": str(interview.candidate_profile_id),
            "session_id": str(interview.id),
            "candidate_name": _first_name(profile),
            "repo_analysis": context,
            "pre_generated_questions": question_dicts(questions),
            "transcript": transcript_dicts(turns),
            "current_question_index": interview.current_question_index,
            "follow_up_count": interview.follow_up_count,
            "latest_answer": message,
            "verification_flags": existing_flags,
            "stage": interview.stage.value,
            "time_elapsed_sec": interview.elapsed_seconds(),
            "time_limit_sec": float(interview.time_limit_seconds),
            "candidate_comfort": interview.candidate_comfort.value,
        }
    )

    for flag in result.get("new_flags", []):
        db.add(
            InterviewVerificationFlag(
                interview_id=interview.id,
                turn_id=candidate_turn.id if candidate_turn else None,
                claim=flag["claim"],
                evidence=flag["evidence"],
                status=flag["status"],
                severity=flag.get("severity", "none"),
            )
        )

    emitted = result.get("emitted")
    if emitted is not None:
        db.add(
            InterviewTurn(
                interview_id=interview.id,
                sequence=_next_sequence(db, interview.id),
                role=TurnRole.INTERVIEWER,
                text=emitted["text"],
                action=emitted.get("action"),
                question_index=emitted.get("question_index"),
                internal_notes=emitted.get("internal_notes") or None,
            )
        )

    interview.stage = InterviewStage(result.get("stage", interview.stage.value))
    interview.current_question_index = result.get(
        "current_question_index", interview.current_question_index
    )
    interview.follow_up_count = result.get("follow_up_count", interview.follow_up_count)
    interview.candidate_comfort = CandidateComfort(
        result.get("candidate_comfort", interview.candidate_comfort.value)
    )

    finished = interview.stage is InterviewStage.DONE
    if finished:
        interview.status = InterviewStatus.EVALUATING

    db.commit()

    if finished:
        _dispatch_scoring(db, interview)

    return get_state(db, profile, interview_id)


def _first_name(profile: CandidateProfile) -> str | None:
    """Just the first name, and only for the greeting.

    A full legal name in the opener reads like a form letter being read aloud,
    which is the exact impression the live interview exists to avoid. Returns
    None rather than a fallback when the student has not given a name: the
    Interviewer is told to greet them without one, which is better than
    `User.display_name`'s "there" spoken aloud as if it were a name.
    """
    full = ((profile.user.full_name if profile.user else None) or "").strip()
    return full.split()[0] if full else None


def _dispatch_scoring(db: Session, interview: Interview) -> None:
    from src.jobs import dispatch as job_dispatch
    from src.jobs.celery_app import QUEUE_EXTRACTION
    from src.jobs.tasks.interview import score_interview_task

    job = job_dispatch.create_job(
        db, job_type="score_interview", payload={"interview_id": str(interview.id)}
    )
    job_dispatch.dispatch(job, score_interview_task, queue=QUEUE_EXTRACTION)


def get_state(db: Session, profile: CandidateProfile, interview_id: uuid.UUID) -> InterviewStateResponse:
    """The whole session as the client should render it.

    Returns the full transcript rather than a delta: reconnecting is the normal
    case in a live interview, and a client that has to reassemble a
    conversation from deltas it may have missed is a client that will
    eventually show a candidate a transcript with a hole in it.
    """
    interview = _get_owned_interview(db, profile, interview_id)
    turns = _load_turns(db, interview.id)

    awaiting = (
        interview.status is InterviewStatus.IN_PROGRESS
        and interview.stage is not InterviewStage.DONE
        # The candidate answers *after* the interviewer has spoken. Before the
        # opener lands there is nothing to answer.
        and bool(turns)
        and turns[-1].role is TurnRole.INTERVIEWER
    )

    return InterviewStateResponse(
        interview=InterviewSummaryResponse.model_validate(interview),
        transcript=[TurnResponse.model_validate(turn) for turn in turns],
        time_remaining_seconds=interview.time_remaining_seconds(),
        awaiting_candidate=awaiting,
    )


def get_report(db: Session, profile: CandidateProfile, interview_id: uuid.UUID) -> EvidenceReportResponse:
    interview = _get_owned_interview(db, profile, interview_id)
    if interview.status is not InterviewStatus.COMPLETED or interview.evidence_report is None:
        raise InterviewNotComplete()

    report = interview.evidence_report
    scores = list(
        db.execute(
            select(InterviewDimensionScore).where(
                InterviewDimensionScore.interview_id == interview.id
            )
        ).scalars()
    )

    return EvidenceReportResponse(
        interview_id=interview.id,
        project_id=interview.project_id,
        total_score=float(interview.total_score or 0),
        # This attempt's own rubric, not the currently-configured one — the
        # report must explain the score it actually shows. A v2 interview
        # renders v2 dimensions and v2 weights forever.
        rubric_weights=get_rubric_weights(interview.rubric_version),
        dimensions=[
            DimensionScoreResponse(
                dimension=score.dimension,
                weight=float(score.weight),
                score=float(score.score),
                evidence=score.evidence,
                confidence=float(score.confidence),
            )
            for score in scores
        ],
        transcript=[TurnResponse.model_validate(turn) for turn in _load_turns(db, interview.id)],
        verified_claims=report.get("verified_claims", []),
        contradicted_claims=report.get("contradicted_claims", []),
        unsupported_claims=report.get("unsupported_claims", []),
        strengths=report.get("strengths", []),
        concerns=report.get("concerns", []),
        summary=report.get("summary", ""),
        completed_at=interview.completed_at or _utcnow(),
    )


# ---------------------------------------------------------------------------
# Interview integrity
# ---------------------------------------------------------------------------


def record_integrity_events(
    db: Session,
    profile: CandidateProfile,
    interview_id: uuid.UUID,
    events: list[IntegrityEventRequest],
) -> IntegritySummaryResponse:
    """Store what the room observed about the session's conditions.

    Deliberately outside `advance`, and deliberately not a socket frame. These
    arrive on their own schedule — a tab hidden for two minutes produces an
    event with nobody taking a turn — and folding them into the turn path would
    mean an integrity flush could take the session lock and block a real answer
    behind a model call.

    `ON CONFLICT DO NOTHING` on `(interview_id, client_sequence)` makes a
    replayed batch a no-op. The room flushes on unload, which fires twice on
    some browsers, so at-least-once delivery is the design and not an edge case.

    No status check: events are accepted for an interview in *any* state,
    including one that has already moved to `EVALUATING`. The last flush of a
    session races the wrap-up turn by construction, and dropping it would lose
    precisely the events from the end of the interview.
    """
    interview = _get_owned_interview(db, profile, interview_id)
    if not events:
        return get_integrity_summary(db, profile, interview_id)

    db.execute(
        pg_insert(InterviewIntegrityEvent)
        .values(
            [
                {
                    "interview_id": interview.id,
                    "client_sequence": event.client_sequence,
                    "event_type": event.event_type,
                    "elapsed_seconds": event.elapsed_seconds,
                    "duration_seconds": event.duration_seconds,
                    "detail": event.detail,
                }
                for event in events
            ]
        )
        .on_conflict_do_nothing(constraint="uq_interview_integrity_sequence")
    )
    db.commit()

    return get_integrity_summary(db, profile, interview_id)


def get_integrity_summary(
    db: Session, profile: CandidateProfile, interview_id: uuid.UUID
) -> IntegritySummaryResponse:
    interview = _get_owned_interview(db, profile, interview_id)
    events = list(
        db.execute(
            select(InterviewIntegrityEvent)
            .where(InterviewIntegrityEvent.interview_id == interview.id)
            .order_by(InterviewIntegrityEvent.client_sequence)
        ).scalars()
    )

    counts: dict[str, int] = {}
    for event in events:
        counts[event.event_type] = counts.get(event.event_type, 0) + 1

    return IntegritySummaryResponse(
        interview_id=interview.id,
        counts=counts,
        total=len(events),
        events=[IntegrityEventResponse.model_validate(event) for event in events],
    )


def get_latest_for_project(
    db: Session, profile: CandidateProfile, project_id: uuid.UUID
) -> Interview | None:
    _get_owned_project(db, profile, project_id)
    return db.execute(
        select(Interview)
        .where(Interview.candidate_profile_id == profile.id, Interview.project_id == project_id)
        .order_by(Interview.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
