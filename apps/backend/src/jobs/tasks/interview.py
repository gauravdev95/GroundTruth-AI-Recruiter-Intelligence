"""Interview question generation and final scoring — the two Celery tasks
that bracket the live interview, both on the `extraction` queue
(`jobs/celery_app.py` — same kind of work as resume extraction).

The conversation itself does *not* run here. It runs inside the request/socket
handling each turn (`domains/interview/router.py`), because a candidate is
sitting there waiting: a queue hop per utterance would add latency to the one
code path that cannot afford any. What is left for the worker is the work
nobody is waiting on — generating the questions before the session opens, and
scoring the transcript after it closes.

Same deterministic/transient split as `jobs/tasks/resume.py`: malformed LLM
output, a refusal, or missing configuration cannot be fixed by retrying, so
those fail the interview immediately (`status=FAILED`, `NonRetryableJobError`
so Celery doesn't burn the backoff ladder on a doomed retry). Timeouts and
provider errors are retried; on final exhaustion the interview is marked
`FAILED` too, rather than left stuck at `PENDING`/`EVALUATING` forever.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from src.db.database import SessionLocal
from src.domains.ai.exceptions import (
    LLMMalformedOutput,
    LLMNotConfigured,
    LLMOutputTruncated,
    LLMRefused,
)
from src.domains.ai.llm import get_interview_question_generator, get_interview_scorer
from src.domains.interview import service as interview_service
from src.domains.interview.models import (
    Interview,
    InterviewDimensionScore,
    InterviewQuestion,
    InterviewStage,
    InterviewStatus,
    InterviewVerificationFlag,
    get_rubric_weights,
)
from src.domains.student.service import recompute_and_persist_strength
from src.domains.verification import stages as verification_stages
from src.jobs.celery_app import DatabaseTask, NonRetryableJobError, celery_app
from src.platform.models import AsyncJob

logger = structlog.get_logger(__name__)

_DETERMINISTIC_ERRORS = (LLMMalformedOutput, LLMRefused, LLMOutputTruncated, LLMNotConfigured)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _load_interview_id(async_job_id: str) -> uuid.UUID:
    with SessionLocal() as session:
        job = session.get(AsyncJob, uuid.UUID(async_job_id))
        if job is None or not job.payload:
            raise NonRetryableJobError(f"Job {async_job_id} has no payload")
        return uuid.UUID(job.payload["interview_id"])


def _exhausted(task: DatabaseTask) -> bool:
    request = getattr(task, "request", None)
    if request is None:
        return True
    return request.retries >= task.max_retries


def _fail_interview(interview_id: uuid.UUID, message: str) -> None:
    with SessionLocal() as session:
        interview = session.get(Interview, interview_id)
        if interview is None:
            return
        interview.status = InterviewStatus.FAILED
        interview.error = message
        # Stages 6 and 7 of the repository pipeline: the interview is the
        # sixth, and the evidence report it would have produced is the
        # seventh, so a failed interview skips rather than fails the report —
        # that stage never ran.
        if interview.project_id is not None:
            verification_stages.mark_interview_failed(session, interview.project_id, error=message)
        session.commit()
        candidate_profile_id = interview.candidate_profile_id
    recompute_and_persist_strength_in_own_session(candidate_profile_id)


def recompute_and_persist_strength_in_own_session(candidate_profile_id: uuid.UUID) -> None:
    with SessionLocal() as session:
        recompute_and_persist_strength(session, candidate_profile_id)


@celery_app.task(
    base=DatabaseTask, bind=True, name="src.jobs.tasks.interview.generate_interview_questions_task"
)
def generate_interview_questions_task(self: DatabaseTask, async_job_id: str) -> dict[str, str]:
    interview_id = _load_interview_id(async_job_id)

    with SessionLocal() as session:
        interview = session.get(Interview, interview_id)
        if interview is None:
            raise NonRetryableJobError(f"Interview {interview_id} no longer exists")
        repository_context = interview_service.build_interview_context(session, interview)

    try:
        question_set = get_interview_question_generator().generate_questions(
            repository_context=repository_context
        )
    except _DETERMINISTIC_ERRORS as exc:
        message = getattr(exc, "message", str(exc))
        _fail_interview(interview_id, message)
        logger.warning("interview_question_generation_failed", interview_id=str(interview_id), error=message)
        raise NonRetryableJobError(message) from exc
    except Exception as exc:
        if _exhausted(self):
            _fail_interview(interview_id, f"{type(exc).__name__}: {exc}")
        logger.warning(
            "interview_question_generation_retrying", interview_id=str(interview_id), error=str(exc)
        )
        raise

    with SessionLocal() as session:
        interview = session.get(Interview, interview_id)
        if interview is None:
            return {"status": "missing"}
        for sequence, question in enumerate(question_set.questions, start=1):
            session.add(
                InterviewQuestion(
                    interview_id=interview.id,
                    sequence=sequence,
                    prompt=question.prompt,
                    grounded_in={"description": question.grounded_in},
                    expected_signals=list(question.expected_signals),
                )
            )
        interview.question_count = len(question_set.questions)
        # IN_PROGRESS the moment the questions exist: the candidate can now
        # connect, and the conversation opens itself when they do. `stage`
        # stays WARMUP until the Interviewer has actually said hello.
        interview.status = InterviewStatus.IN_PROGRESS
        interview.stage = InterviewStage.WARMUP
        # Only a repository interview advances a repository's stage pipeline.
        # A profile interview is scoped to the candidate and has no project
        # whose CODE_GROUNDED_INTERVIEW stage it could legitimately move.
        if interview.project_id is not None:
            verification_stages.mark_interview_started(session, interview.project_id)
        session.commit()

    logger.info(
        "interview_questions_generated", interview_id=str(interview_id), count=len(question_set.questions)
    )
    return {"status": "in_progress", "question_count": str(len(question_set.questions))}


@celery_app.task(base=DatabaseTask, bind=True, name="src.jobs.tasks.interview.score_interview_task")
def score_interview_task(self: DatabaseTask, async_job_id: str) -> dict[str, str]:
    """Score the finished conversation.

    One model call over the whole transcript, not one per answer — see
    `domains/ai/llm.py::InterviewScorer` for why per-answer scoring misreads a
    conversation. The weighted total is computed here rather than asked for:
    the weights are operator-configurable, so the model cannot know them, and a
    headline number a model did the arithmetic for is a number nobody can
    check.
    """
    interview_id = _load_interview_id(async_job_id)

    with SessionLocal() as session:
        interview = session.get(Interview, interview_id)
        if interview is None:
            raise NonRetryableJobError(f"Interview {interview_id} no longer exists")
        # Read inside the session — these are not available after it closes,
        # and scoring must use the rubric this attempt was generated under
        # rather than whatever is configured now.
        rubric_version = interview.rubric_version
        repository_context = interview_service.build_interview_context(session, interview)
        turns = interview_service.load_transcript(session, interview.id)
        questions = interview_service.load_question_payload(session, interview.id)
        flags = [
            {
                "claim": flag.claim,
                "evidence": flag.evidence,
                "status": flag.status,
                "severity": flag.severity,
            }
            for flag in session.execute(
                select(InterviewVerificationFlag).where(
                    InterviewVerificationFlag.interview_id == interview.id
                )
            ).scalars()
        ]

    # Resolved from the version stored on the interview row rather than the
    # currently-configured rubric: an interview generated under one rubric must
    # be scored under that same one even if the operator changed the weights
    # while the candidate was sitting it.
    rubric = get_rubric_weights(rubric_version)

    try:
        scorecard = get_interview_scorer().score_interview(
            transcript=turns,
            verification_flags=flags,
            repository_context=repository_context,
            questions=questions,
        )
    except _DETERMINISTIC_ERRORS as exc:
        message = getattr(exc, "message", str(exc))
        _fail_interview(interview_id, message)
        logger.warning("interview_scoring_failed", interview_id=str(interview_id), error=message)
        raise NonRetryableJobError(message) from exc
    except Exception as exc:
        if _exhausted(self):
            _fail_interview(interview_id, f"{type(exc).__name__}: {exc}")
        logger.warning("interview_scoring_retrying", interview_id=str(interview_id), error=str(exc))
        raise

    scores_by_dimension = {score.dimension: score for score in scorecard.dimensions}
    missing = set(rubric) - set(scores_by_dimension)
    if missing:
        # A provider that returned a partial rubric would otherwise KeyError
        # below after burning the whole scoring call; naming the gap makes it a
        # diagnosable, non-retryable failure rather than an opaque crash.
        message = f"Scorer omitted rubric dimension(s): {', '.join(sorted(missing))}"
        _fail_interview(interview_id, message)
        raise NonRetryableJobError(message)

    total_score = round(
        sum(float(scores_by_dimension[dim].score) * weight for dim, weight in rubric.items()), 2
    )

    with SessionLocal() as session:
        interview = session.get(Interview, interview_id)
        if interview is None:
            return {"status": "missing"}

        for dimension, weight in rubric.items():
            scored = scores_by_dimension[dimension]
            session.add(
                InterviewDimensionScore(
                    interview_id=interview.id,
                    dimension=dimension,
                    weight=weight,
                    score=float(scored.score),
                    evidence=scored.evidence,
                    confidence=float(scored.confidence),
                )
            )

        interview.total_score = total_score
        # The narrative half of the report. The per-dimension numbers live in
        # their own rows; this holds what cannot be expressed as a number, and
        # the transcript is joined onto it at read time rather than copied in
        # — it is already stored, immutably, one table over.
        interview.evidence_report = {
            "verified_claims": list(scorecard.verified_claims),
            "contradicted_claims": list(scorecard.contradicted_claims),
            "unsupported_claims": list(scorecard.unsupported_claims),
            "strengths": list(scorecard.strengths),
            "concerns": list(scorecard.concerns),
            "summary": scorecard.summary,
        }
        interview.status = InterviewStatus.COMPLETED
        interview.stage = InterviewStage.DONE
        interview.completed_at = _utcnow()
        # Closes stages 6 and 7 together: this same pass both scores the
        # interview and produces the evidence report, so there is no window in
        # which one has landed and the other has not.
        #
        # Repository interviews only — a profile interview belongs to the
        # candidate, not to any one repository, so it has no
        # CODE_GROUNDED_INTERVIEW stage to close. Its completion still opens
        # the discoverability gate via the recompute below, which is what
        # actually matters to the candidate.
        if interview.project_id is not None:
            verification_stages.mark_interview_completed(
                session, interview.project_id, interview_id=interview.id, total_score=total_score
            )
        session.commit()
        candidate_profile_id = interview.candidate_profile_id

    recompute_and_persist_strength_in_own_session(candidate_profile_id)

    logger.info("interview_scored", interview_id=str(interview_id), total_score=total_score)
    return {"status": "completed", "total_score": str(total_score)}
