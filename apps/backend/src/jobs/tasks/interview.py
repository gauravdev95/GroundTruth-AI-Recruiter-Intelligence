"""Interview question generation and answer evaluation — the two Celery
tasks behind the AI interview, both on the `extraction` queue
(`jobs/celery_app.py` — same kind of work as resume extraction).

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

from src.db.database import SessionLocal
from src.domains.ai.exceptions import (
    LLMMalformedOutput,
    LLMNotConfigured,
    LLMOutputTruncated,
    LLMRefused,
)
from src.domains.ai.llm import get_interview_answer_evaluator, get_interview_question_generator
from src.domains.interview import service as interview_service
from src.domains.interview.models import (
    Interview,
    InterviewQuestion,
    InterviewScore,
    InterviewStatus,
    get_rubric_weights,
)
from src.domains.student.models import Project
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
                )
            )
        interview.question_count = len(question_set.questions)
        interview.status = InterviewStatus.IN_PROGRESS
        interview.started_at = _utcnow()
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


@celery_app.task(base=DatabaseTask, bind=True, name="src.jobs.tasks.interview.evaluate_interview_task")
def evaluate_interview_task(self: DatabaseTask, async_job_id: str) -> dict[str, str]:
    interview_id = _load_interview_id(async_job_id)

    with SessionLocal() as session:
        interview = session.get(Interview, interview_id)
        if interview is None:
            raise NonRetryableJobError(f"Interview {interview_id} no longer exists")
        # Read inside the session — the row is not available after it closes,
        # and evaluation below must use the rubric this attempt was generated
        # under rather than whatever is configured now.
        rubric_version = interview.rubric_version
        repository_context = interview_service.build_interview_context(session, interview)
        questions = sorted(interview.questions, key=lambda q: q.sequence)
        # Snapshot everything needed for evaluation before the session
        # closes — evaluation itself makes N sequential LLM calls and must
        # not hold a DB session open across all of them.
        snapshot = [
            {
                "question_id": q.id,
                "sequence": q.sequence,
                "prompt": q.prompt,
                "grounded_in": q.grounded_in,
                "transcript": q.answer.transcript if q.answer else "",
                "time_taken_seconds": q.answer.time_taken_seconds if q.answer else None,
                "exceeded_time_limit": q.answer.exceeded_time_limit if q.answer else False,
                "answer_id": q.answer.id if q.answer else None,
            }
            for q in questions
        ]

    evaluator = get_interview_answer_evaluator()
    # Resolved once for the whole evaluation, from the version stored on the
    # interview row rather than the currently-configured rubric: an interview
    # that was generated under one rubric must be scored under that same one
    # even if the operator changed the weights while the candidate was sitting
    # it. Every answer in one attempt is therefore weighted identically.
    rubric = get_rubric_weights(rubric_version)

    graded: list[dict] = []
    try:
        for item in snapshot:
            evaluation = evaluator.evaluate_answer(
                question=item["prompt"],
                answer_transcript=item["transcript"],
                repository_context=repository_context,
            )
            scores_by_dimension = {s.dimension: s for s in evaluation.scores}
            missing = set(rubric) - set(scores_by_dimension)
            if missing:
                # A provider that returns a partial rubric would otherwise
                # KeyError mid-loop after burning the whole evaluation's
                # tokens; naming the gap makes it a diagnosable, non-retryable
                # failure rather than an opaque crash.
                raise NonRetryableJobError(
                    f"Evaluator omitted rubric dimension(s): {', '.join(sorted(missing))}"
                )
            weighted_score = sum(
                float(scores_by_dimension[dim].score) * weight for dim, weight in rubric.items()
            )
            graded.append(
                {
                    **item,
                    "scores": [
                        {
                            "dimension": dim,
                            "weight": weight,
                            "score": float(scores_by_dimension[dim].score),
                            "rationale": scores_by_dimension[dim].rationale,
                        }
                        for dim, weight in rubric.items()
                    ],
                    "weighted_score": round(weighted_score, 2),
                }
            )
    except _DETERMINISTIC_ERRORS as exc:
        message = getattr(exc, "message", str(exc))
        _fail_interview(interview_id, message)
        logger.warning("interview_evaluation_failed", interview_id=str(interview_id), error=message)
        raise NonRetryableJobError(message) from exc
    except Exception as exc:
        if _exhausted(self):
            _fail_interview(interview_id, f"{type(exc).__name__}: {exc}")
        logger.warning("interview_evaluation_retrying", interview_id=str(interview_id), error=str(exc))
        raise

    total_score = round(sum(q["weighted_score"] for q in graded) / len(graded), 2) if graded else 0.0

    with SessionLocal() as session:
        interview = session.get(Interview, interview_id)
        if interview is None:
            return {"status": "missing"}

        for item in graded:
            if item["answer_id"] is None:
                continue
            for score in item["scores"]:
                session.add(
                    InterviewScore(
                        interview_answer_id=item["answer_id"],
                        dimension=score["dimension"],
                        weight=score["weight"],
                        score=score["score"],
                        rationale=score["rationale"],
                    )
                )

        interview.total_score = total_score
        interview.evidence_report = {
            "questions": [
                {
                    "sequence": q["sequence"],
                    "prompt": q["prompt"],
                    "grounded_in": q["grounded_in"],
                    "transcript": q["transcript"],
                    "time_taken_seconds": q["time_taken_seconds"],
                    "exceeded_time_limit": q["exceeded_time_limit"],
                    "scores": q["scores"],
                    "weighted_score": q["weighted_score"],
                }
                for q in graded
            ]
        }
        interview.status = InterviewStatus.COMPLETED
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

    logger.info("interview_evaluated", interview_id=str(interview_id), total_score=total_score)
    return {"status": "completed", "total_score": str(total_score)}
