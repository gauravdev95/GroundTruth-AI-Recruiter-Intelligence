"""Business logic for the code-grounded AI interview.

`start_interview` is the only place `RepositoryNotVerified`/
`InterviewAlreadyExists` are raised — every other function here trusts that
an `Interview` row it's given already passed those checks, since a row only
exists once `start_interview` created it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.exceptions import Forbidden, NotFound
from src.domains.auth.models import CandidateProfile
from src.domains.interview.exceptions import (
    InterviewAlreadyExists,
    InterviewNotComplete,
    InterviewNotReady,
    QuestionAlreadyAnswered,
    RepositoryNotVerified,
)
from src.domains.interview.models import (
    RUBRIC_WEIGHTS,
    Interview,
    InterviewAnswer,
    InterviewQuestion,
    InterviewScore,
    InterviewStatus,
)
from src.domains.interview.schemas import (
    AnsweredQuestionReport,
    DimensionScoreResponse,
    EvidenceReportResponse,
    InterviewQuestionResponse,
    InterviewStateResponse,
    InterviewSummaryResponse,
)
from src.domains.student.models import Project, ProjectKind, VerificationStatus

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
    """The stored analysis every question/evaluation is grounded in —
    exactly what `Project.verification_payload` holds, nothing re-fetched
    from GitHub at interview time. See `verify_repository_task`'s payload
    write in `jobs/tasks/verification.py` for the shape."""
    payload = dict(project.verification_payload or {})
    payload["title"] = project.title
    payload["repo_url"] = project.repo_url
    return payload


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

    interview = Interview(
        candidate_profile_id=profile.id,
        project_id=project_id,
        status=InterviewStatus.PENDING,
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

    logger.info("interview_started", interview_id=str(interview.id), project_id=str(project_id))
    return interview


def _load_questions(db: Session, interview_id: uuid.UUID) -> list[InterviewQuestion]:
    return list(
        db.execute(
            select(InterviewQuestion)
            .where(InterviewQuestion.interview_id == interview_id)
            .order_by(InterviewQuestion.sequence)
        ).scalars()
    )


def _answered_question_ids(db: Session, question_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """Explicit query rather than `question.answer`/`interview.questions`
    relationship access — this session can live across several calls within
    one request (`get_state` is called again at the end of `submit_answer`),
    and a relationship attribute, once lazy-loaded, does not refresh itself
    just because a later `db.flush()` changed the underlying row. A fresh
    `select()` always reflects what was actually just written, the same
    reasoning `student/service.py`'s `_active_*` helpers already follow."""
    if not question_ids:
        return set()
    return set(
        db.execute(
            select(InterviewAnswer.interview_question_id).where(
                InterviewAnswer.interview_question_id.in_(question_ids)
            )
        ).scalars()
    )


def _question_response(
    question: InterviewQuestion, *, is_answered: bool, mark_presented: bool
) -> InterviewQuestionResponse:
    if mark_presented and question.presented_at is None:
        question.presented_at = _utcnow()
    return InterviewQuestionResponse(
        id=question.id,
        sequence=question.sequence,
        prompt=question.prompt,
        time_limit_seconds=question.time_limit_seconds,
        presented_at=question.presented_at,
        is_answered=is_answered,
    )


def get_state(db: Session, profile: CandidateProfile, interview_id: uuid.UUID) -> InterviewStateResponse:
    interview = _get_owned_interview(db, profile, interview_id)
    questions = _load_questions(db, interview.id)
    answered_ids = _answered_question_ids(db, [q.id for q in questions])

    current: InterviewQuestionResponse | None = None
    if interview.status is InterviewStatus.IN_PROGRESS:
        next_question = next((q for q in questions if q.id not in answered_ids), None)
        if next_question is not None:
            current = _question_response(next_question, is_answered=False, mark_presented=True)
            db.commit()

    return InterviewStateResponse(
        interview=InterviewSummaryResponse.model_validate(interview),
        current_question=current,
        answered_count=len(answered_ids),
    )


def submit_answer(
    db: Session,
    profile: CandidateProfile,
    interview_id: uuid.UUID,
    question_id: uuid.UUID,
    *,
    transcript: str,
    time_taken_seconds: int,
) -> InterviewStateResponse:
    interview = _get_owned_interview(db, profile, interview_id)
    if interview.status is not InterviewStatus.IN_PROGRESS:
        raise InterviewNotReady()

    question = db.execute(
        select(InterviewQuestion).where(
            InterviewQuestion.id == question_id, InterviewQuestion.interview_id == interview.id
        )
    ).scalar_one_or_none()
    if question is None:
        raise NotFound("Interview question not found")

    already_answered = db.execute(
        select(InterviewAnswer.id).where(InterviewAnswer.interview_question_id == question.id)
    ).scalar_one_or_none()
    if already_answered is not None:
        raise QuestionAlreadyAnswered()

    exceeded = time_taken_seconds > question.time_limit_seconds
    answer = InterviewAnswer(
        interview_question_id=question.id,
        transcript=transcript,
        time_taken_seconds=time_taken_seconds,
        exceeded_time_limit=exceeded,
    )
    db.add(answer)
    db.flush()

    all_questions = _load_questions(db, interview.id)
    answered_ids = _answered_question_ids(db, [q.id for q in all_questions])
    remaining = [q for q in all_questions if q.id not in answered_ids]
    if not remaining:
        interview.status = InterviewStatus.EVALUATING
        db.commit()

        from src.jobs import dispatch as job_dispatch
        from src.jobs.celery_app import QUEUE_EXTRACTION
        from src.jobs.tasks.interview import evaluate_interview_task

        job = job_dispatch.create_job(
            db, job_type="evaluate_interview", payload={"interview_id": str(interview.id)}
        )
        job_dispatch.dispatch(job, evaluate_interview_task, queue=QUEUE_EXTRACTION)
    else:
        db.commit()

    return get_state(db, profile, interview_id)


def get_report(db: Session, profile: CandidateProfile, interview_id: uuid.UUID) -> EvidenceReportResponse:
    interview = _get_owned_interview(db, profile, interview_id)
    if interview.status is not InterviewStatus.COMPLETED or interview.evidence_report is None:
        raise InterviewNotComplete()

    report = interview.evidence_report
    return EvidenceReportResponse(
        interview_id=interview.id,
        project_id=interview.project_id,
        total_score=float(interview.total_score or 0),
        rubric_weights=dict(RUBRIC_WEIGHTS),
        questions=[
            AnsweredQuestionReport(
                sequence=q["sequence"],
                prompt=q["prompt"],
                grounded_in=q.get("grounded_in"),
                transcript=q["transcript"],
                time_taken_seconds=q.get("time_taken_seconds"),
                exceeded_time_limit=q.get("exceeded_time_limit", False),
                scores=[DimensionScoreResponse(**s) for s in q["scores"]],
                weighted_score=q["weighted_score"],
            )
            for q in report["questions"]
        ],
        completed_at=interview.completed_at or _utcnow(),
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
