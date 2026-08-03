"""Integration tests for the code-grounded AI interview
(`domains/interview/`, `jobs/tasks/interview.py`).

The Anthropic-backed question generator/evaluator are stubbed (same pattern
as `test_resume_import.py::stub_extractor`) — this is not a test of the LLM,
it's a test of the state machine: a repository must be `VERIFIED` before an
interview can start, one attempt is allowed per repository, resuming returns
the same next-unanswered question, and evaluation produces a rubric-weighted
report that is never overwritten.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domains.ai.interview_schema import AnswerEvaluation, GeneratedQuestion, GeneratedQuestionSet
from src.domains.auth import service as auth_service
from src.domains.auth.models import CandidateProfile
from src.domains.auth.schemas import CandidateRegisterRequest
from src.domains.auth.security import create_access_token
from src.domains.interview.models import Interview, InterviewStatus
from src.domains.student.models import Project, ProjectKind, VerificationStatus

INTERVIEW_BASE = "/api/v1/student/interview"


@pytest.fixture(autouse=True)
def stub_broker(monkeypatch):
    monkeypatch.setattr("src.jobs.dispatch.dispatch", lambda job, task, *, queue, args=None: None)


class _SessionProxy:
    def __init__(self, session: Session) -> None:
        self._session = session

    def __enter__(self) -> Session:
        return self._session

    def __exit__(self, *_: object) -> bool:
        return False


@pytest.fixture(autouse=True)
def worker_sessions(monkeypatch, db_session: Session):
    factory = lambda: _SessionProxy(db_session)  # noqa: E731
    monkeypatch.setattr("src.jobs.tasks.interview.SessionLocal", factory)
    monkeypatch.setattr("src.jobs.celery_app.SessionLocal", factory)


QUESTION_SET = GeneratedQuestionSet(
    questions=[
        GeneratedQuestion(prompt=f"Question {i} about the repository?", grounded_in=f"file_{i}.py")
        for i in range(1, 6)
    ]
)


@pytest.fixture()
def stub_question_generator(monkeypatch):
    class _Stub:
        def generate_questions(self, *, repository_context):
            return QUESTION_SET

    stub = _Stub()
    monkeypatch.setattr("src.jobs.tasks.interview.get_interview_question_generator", lambda: stub)
    return stub


@pytest.fixture()
def stub_answer_evaluator(monkeypatch):
    class _Stub:
        def evaluate_answer(self, *, question, answer_transcript, repository_context):
            return AnswerEvaluation(
                scores=[
                    {"dimension": "technical_accuracy", "score": 80, "rationale": "Solid technical grasp of the concept."},
                    {"dimension": "depth_of_reasoning", "score": 70, "rationale": "Reasonable depth, could go further."},
                    {"dimension": "codebase_specificity", "score": 60, "rationale": "Specific enough to this repository."},
                    {"dimension": "repository_consistency", "score": 90, "rationale": "Consistent with the stored analysis."},
                ]
            )

    stub = _Stub()
    monkeypatch.setattr("src.jobs.tasks.interview.get_interview_answer_evaluator", lambda: stub)
    return stub


def _candidate(db_session: Session, email: str = "interview.me@example.com") -> tuple[str, CandidateProfile]:
    user, otp, _ = auth_service.register_candidate(
        db_session,
        CandidateRegisterRequest(
            full_name="Ada Lovelace",
            email=email,
            phone_number="+14155552671",
            password="StrongPass1!",
            confirm_password="StrongPass1!",
            captcha_token="test",
            accept_terms=True,
        ),
    )
    auth_service.confirm_email_otp(db_session, user.email, otp)
    token = create_access_token(user_id=user.id, role=user.role.value)
    profile = db_session.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == user.id)
    ).scalar_one()
    return token, profile


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _verified_project(db_session: Session, profile: CandidateProfile) -> Project:
    project = Project(
        candidate_profile_id=profile.id,
        kind=ProjectKind.REPOSITORY,
        title="My App",
        repo_url="https://github.com/ada/myapp",
        technologies=["Python"],
        verification_status=VerificationStatus.VERIFIED,
        verification_score=86.0,
        verification_source="github_api",
        verification_payload={
            "owner": "ada",
            "repo": "myapp",
            "is_fork": False,
            "contribution_share": 0.9,
            "detected_technologies": ["Python", "fastapi"],
            "file_paths_sample": ["app.py", "requirements.txt", "tests/test_app.py"],
        },
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


def _unverified_project(db_session: Session, profile: CandidateProfile) -> Project:
    project = Project(
        candidate_profile_id=profile.id,
        kind=ProjectKind.REPOSITORY,
        title="Unverified App",
        repo_url="https://github.com/ada/unverified",
        technologies=[],
        verification_status=VerificationStatus.UNVERIFIED,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


def test_starting_an_interview_requires_a_verified_repository(client: TestClient, db_session: Session):
    token, profile = _candidate(db_session)
    project = _unverified_project(db_session, profile)

    resp = client.post(f"{INTERVIEW_BASE}/projects/{project.id}/start", headers=_auth(token))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "REPOSITORY_NOT_VERIFIED"


def test_full_interview_flow_start_answer_evaluate_report(
    client: TestClient, db_session: Session, stub_question_generator, stub_answer_evaluator
):
    from src.jobs.tasks.interview import evaluate_interview_task, generate_interview_questions_task
    from src.platform.models import AsyncJob

    token, profile = _candidate(db_session)
    project = _verified_project(db_session, profile)

    start_resp = client.post(f"{INTERVIEW_BASE}/projects/{project.id}/start", headers=_auth(token))
    assert start_resp.status_code == 200, start_resp.text
    interview_id = start_resp.json()["id"]
    assert start_resp.json()["status"] == "pending"

    # Starting again while the first attempt is in flight is rejected.
    again = client.post(f"{INTERVIEW_BASE}/projects/{project.id}/start", headers=_auth(token))
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "INTERVIEW_ALREADY_EXISTS"

    gen_job = db_session.execute(
        select(AsyncJob).where(AsyncJob.job_type == "generate_interview_questions")
    ).scalars().first()
    assert gen_job is not None
    generate_interview_questions_task.run(str(gen_job.id))

    state = client.get(f"{INTERVIEW_BASE}/{interview_id}", headers=_auth(token)).json()
    assert state["interview"]["status"] == "in_progress"
    assert state["interview"]["question_count"] == 5
    assert state["current_question"] is not None
    assert state["current_question"]["sequence"] == 1
    assert state["current_question"]["presented_at"] is not None

    # Answer every question in sequence; resuming (re-GET) always returns the
    # next unanswered one.
    for expected_sequence in range(1, 6):
        state = client.get(f"{INTERVIEW_BASE}/{interview_id}", headers=_auth(token)).json()
        assert state["current_question"]["sequence"] == expected_sequence
        question_id = state["current_question"]["id"]

        answer_resp = client.post(
            f"{INTERVIEW_BASE}/{interview_id}/questions/{question_id}/answer",
            json={"transcript": f"My answer to question {expected_sequence}.", "time_taken_seconds": 60},
            headers=_auth(token),
        )
        assert answer_resp.status_code == 200, answer_resp.text

        # Answering the same question twice is rejected.
        repeat = client.post(
            f"{INTERVIEW_BASE}/{interview_id}/questions/{question_id}/answer",
            json={"transcript": "again", "time_taken_seconds": 10},
            headers=_auth(token),
        )
        assert repeat.status_code in (409, 404)  # 404 once status is no longer in_progress

    final_state = client.get(f"{INTERVIEW_BASE}/{interview_id}", headers=_auth(token)).json()
    assert final_state["interview"]["status"] == "evaluating"
    assert final_state["current_question"] is None

    eval_job = db_session.execute(
        select(AsyncJob).where(AsyncJob.job_type == "evaluate_interview")
    ).scalars().first()
    assert eval_job is not None
    evaluate_interview_task.run(str(eval_job.id))

    report_resp = client.get(f"{INTERVIEW_BASE}/{interview_id}/report", headers=_auth(token))
    assert report_resp.status_code == 200, report_resp.text
    report = report_resp.json()
    assert len(report["questions"]) == 5
    # (0.4*80 + 0.25*70 + 0.2*60 + 0.15*90) = 32+17.5+12+13.5 = 75.0 per question
    assert report["questions"][0]["weighted_score"] == pytest.approx(75.0)
    assert report["total_score"] == pytest.approx(75.0)
    assert report["rubric_weights"]["technical_accuracy"] == 0.40

    interview = db_session.get(Interview, interview_id)
    assert interview.status is InterviewStatus.COMPLETED
    assert interview.total_score == pytest.approx(75.0)


def test_report_is_not_available_before_evaluation_completes(
    client: TestClient, db_session: Session, stub_question_generator
):
    from src.platform.models import AsyncJob

    token, profile = _candidate(db_session, "early.report@example.com")
    project = _verified_project(db_session, profile)

    start_resp = client.post(f"{INTERVIEW_BASE}/projects/{project.id}/start", headers=_auth(token))
    interview_id = start_resp.json()["id"]

    report_resp = client.get(f"{INTERVIEW_BASE}/{interview_id}/report", headers=_auth(token))
    assert report_resp.status_code == 409
    assert report_resp.json()["error"]["code"] == "INTERVIEW_NOT_COMPLETE"


def test_a_candidate_cannot_access_another_candidates_interview(client: TestClient, db_session: Session):
    token_a, profile_a = _candidate(db_session, "owner.interview@example.com")
    project = _verified_project(db_session, profile_a)
    start_resp = client.post(f"{INTERVIEW_BASE}/projects/{project.id}/start", headers=_auth(token_a))
    interview_id = start_resp.json()["id"]

    token_b, _profile_b = _candidate(db_session, "other.interview@example.com")
    resp = client.get(f"{INTERVIEW_BASE}/{interview_id}", headers=_auth(token_b))
    assert resp.status_code == 403
