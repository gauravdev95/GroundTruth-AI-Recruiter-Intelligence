"""Integration tests for the live code-grounded AI interview
(`domains/interview/`, `jobs/tasks/interview.py`).

All four Gemini-backed agents are stubbed (same pattern as
`test_resume_import.py::stub_extractor`) — this is not a test of the LLM, it is
a test of the machinery around it: a repository must be `VERIFIED` before an
interview can start, one attempt is allowed per repository, the conversation
advances one turn at a time and survives being resumed, and scoring produces a
rubric-weighted report that is never overwritten.

The socket is exercised through `POST /turns` rather than through a WebSocket
client. They are the same code path by construction — the socket handler calls
`service.advance` and nothing else (`interview/router.py`) — and driving the
REST route keeps these tests about the interview instead of about frame
plumbing. `test_realtime_socket.py` is where socket mechanics are covered.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domains.ai.interview_schema import (
    DimensionScore,
    GeneratedQuestion,
    GeneratedQuestionSet,
    InterviewerTurn,
    Scorecard,
    VerificationReport,
)
from src.domains.auth import service as auth_service
from src.domains.auth.models import CandidateProfile
from src.domains.auth.schemas import CandidateRegisterRequest
from src.domains.auth.security import create_access_token
from src.domains.interview.models import (
    Interview,
    InterviewStage,
    InterviewStatus,
    InterviewTurn,
    InterviewVerificationFlag,
    TurnRole,
)
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
        GeneratedQuestion(
            prompt=f"Question {i} about the repository?",
            grounded_in=f"file_{i}.py",
            expected_signals=["names the module", "explains the tradeoff"],
        )
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
def stub_live_agents(monkeypatch):
    """The Interviewer and the Verifier, as the graph calls them.

    Patched on `graph.nodes` rather than on `domains.ai.llm`, because that is
    the namespace the nodes resolve them through — patching the source module
    would leave the already-imported names pointing at the real factories.
    """

    class _Interviewer:
        def __init__(self) -> None:
            self.turns = 0

        def next_turn(self, *, directive=None, **_kwargs):
            self.turns += 1
            action = "ASK_QUESTION"
            if directive and "action=WRAPUP" in directive:
                action = "WRAPUP"
            elif directive and "action=BRIDGE_NEXT" in directive:
                action = "BRIDGE_NEXT"
            elif directive and "action=ASK_FOLLOWUP" in directive:
                action = "ASK_FOLLOWUP"
            return InterviewerTurn(
                interviewer_text=f"Interviewer turn {self.turns}.",
                action=action,
                internal_notes="thin but honest",
            )

    class _Verifier:
        def verify_claims(self, *, candidate_answer, question, repository_context, previous_flags):
            return VerificationReport(
                claims_checked=[
                    {
                        "claim": "uses FastAPI",
                        "evidence": "detected_technologies includes fastapi",
                        "status": "supported",
                        "severity": "none",
                    }
                ],
                # Never probe: this test is about the interview completing, and
                # follow-up routing has its own unit tests
                # (`tests/unit/test_interview_graph.py`).
                follow_up_recommendation="sufficient",
            )

    interviewer = _Interviewer()
    monkeypatch.setattr("src.domains.interview.graph.nodes.get_live_interviewer", lambda: interviewer)
    monkeypatch.setattr("src.domains.interview.graph.nodes.get_claim_verifier", lambda: _Verifier())
    return interviewer


#: The stubbed scorecard. Under v3 weights (0.40/0.25/0.20/0.15):
#:   0.40*80 + 0.25*90 + 0.20*70 + 0.15*65 = 32 + 22.5 + 14 + 9.75 = 78.25
SCORES = {"technical_accuracy": 80.0, "code_understanding": 90.0, "problem_solving": 70.0, "communication": 65.0}
EXPECTED_TOTAL = 78.25


@pytest.fixture()
def stub_scorer(monkeypatch):
    class _Stub:
        def score_interview(self, *, transcript, verification_flags, repository_context, questions):
            return Scorecard(
                dimensions=[
                    DimensionScore(
                        dimension=dimension,
                        score=score,
                        evidence=f"Evidence for {dimension} drawn from the transcript.",
                        confidence=90.0,
                    )
                    for dimension, score in SCORES.items()
                ],
                verified_claims=["uses FastAPI"],
                contradicted_claims=[],
                unsupported_claims=["mentions a cache layer"],
                strengths=["Walked through the request lifecycle unprompted"],
                concerns=["Vague on error handling"],
                summary="Solid understanding of their own service, thinner on failure modes.",
            )

    stub = _Stub()
    monkeypatch.setattr("src.jobs.tasks.interview.get_interview_scorer", lambda: stub)
    return stub


def _candidate(db_session: Session, email: str = "interview.me@example.com") -> tuple[str, CandidateProfile]:
    user = auth_service.register_candidate(
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


def _generate_questions(db_session: Session) -> None:
    from src.jobs.tasks.interview import generate_interview_questions_task
    from src.platform.models import AsyncJob

    job = db_session.execute(
        select(AsyncJob).where(AsyncJob.job_type == "generate_interview_questions")
    ).scalars().first()
    assert job is not None
    generate_interview_questions_task.run(str(job.id))


def _open_conversation(db_session: Session, profile: CandidateProfile, interview_id: str):
    """What connecting does: the interviewer speaks first, unprompted.

    Over the socket this happens on connect
    (`router.py::live_interview_socket` calls `advance(message=None)`). There is
    no REST route for it on purpose — an opening turn is something a session
    does once, not something a client asks for — so it is driven through the
    service here.
    """
    from src.domains.interview import service

    return service.advance(db_session, profile, uuid.UUID(interview_id), message=None)


def test_starting_an_interview_requires_a_verified_repository(client: TestClient, db_session: Session):
    token, profile = _candidate(db_session)
    project = _unverified_project(db_session, profile)

    resp = client.post(f"{INTERVIEW_BASE}/projects/{project.id}/start", headers=_auth(token))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "REPOSITORY_NOT_VERIFIED"


def test_full_interview_flow_start_converse_score_report(
    client: TestClient,
    db_session: Session,
    stub_question_generator,
    stub_live_agents,
    stub_scorer,
):
    from src.domains.interview import service
    from src.platform.models import AsyncJob
    from src.jobs.tasks.interview import score_interview_task

    token, profile = _candidate(db_session)
    project = _verified_project(db_session, profile)

    start_resp = client.post(f"{INTERVIEW_BASE}/projects/{project.id}/start", headers=_auth(token))
    assert start_resp.status_code == 200, start_resp.text
    interview_id = start_resp.json()["id"]
    assert start_resp.json()["status"] == "pending"
    assert start_resp.json()["stage"] == "warmup"

    # Starting again while the first attempt is in flight is rejected.
    again = client.post(f"{INTERVIEW_BASE}/projects/{project.id}/start", headers=_auth(token))
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "INTERVIEW_ALREADY_EXISTS"

    # Speaking before the questions exist is refused rather than queued.
    too_early = client.post(
        f"{INTERVIEW_BASE}/{interview_id}/turns", json={"text": "hello?"}, headers=_auth(token)
    )
    assert too_early.status_code == 409
    assert too_early.json()["error"]["code"] == "INTERVIEW_NOT_READY"

    _generate_questions(db_session)

    state = client.get(f"{INTERVIEW_BASE}/{interview_id}", headers=_auth(token)).json()
    assert state["interview"]["status"] == "in_progress"
    assert state["interview"]["question_count"] == 5
    assert state["transcript"] == []
    # Nothing has been said, so it is not the candidate's turn yet.
    assert state["awaiting_candidate"] is False

    # Connecting opens the conversation: the interviewer speaks first.
    opened = _open_conversation(db_session, profile, interview_id)
    assert len(opened.transcript) == 1
    assert opened.transcript[0].role == "interviewer"
    assert opened.awaiting_candidate is True

    # Then one turn per answer until the interviewer wraps up. The bound is the
    # question count plus warmup plus wrapup — if routing ever loops, this fails
    # here rather than hanging.
    for _ in range(len(QUESTION_SET.questions) + 3):
        state = client.get(f"{INTERVIEW_BASE}/{interview_id}", headers=_auth(token)).json()
        if state["interview"]["status"] != "in_progress":
            break
        resp = client.post(
            f"{INTERVIEW_BASE}/{interview_id}/turns",
            json={"text": "We queue the retry with exponential backoff and a jitter."},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text

    final_state = client.get(f"{INTERVIEW_BASE}/{interview_id}", headers=_auth(token)).json()
    assert final_state["interview"]["status"] == "evaluating"
    assert final_state["interview"]["stage"] == "done"
    assert final_state["awaiting_candidate"] is False

    # The conversation is stored as alternating turns, in order.
    turns = db_session.execute(
        select(InterviewTurn).where(InterviewTurn.interview_id == interview_id).order_by(InterviewTurn.sequence)
    ).scalars().all()
    assert [turn.sequence for turn in turns] == list(range(1, len(turns) + 1))
    assert turns[0].role is TurnRole.INTERVIEWER
    assert turns[-1].action == "WRAPUP"

    # Every candidate turn was verified as it happened.
    flags = db_session.execute(
        select(InterviewVerificationFlag).where(InterviewVerificationFlag.interview_id == interview_id)
    ).scalars().all()
    assert flags, "the Verifier ran on every candidate answer"
    assert all(flag.turn_id is not None for flag in flags)

    # Speaking after the wrapup is refused.
    after = client.post(
        f"{INTERVIEW_BASE}/{interview_id}/turns", json={"text": "one more thing"}, headers=_auth(token)
    )
    assert after.status_code == 409
    assert after.json()["error"]["code"] == "INTERVIEW_FINISHED"

    score_job = db_session.execute(
        select(AsyncJob).where(AsyncJob.job_type == "score_interview")
    ).scalars().first()
    assert score_job is not None
    score_interview_task.run(str(score_job.id))

    report_resp = client.get(f"{INTERVIEW_BASE}/{interview_id}/report", headers=_auth(token))
    assert report_resp.status_code == 200, report_resp.text
    report = report_resp.json()

    assert report["total_score"] == pytest.approx(EXPECTED_TOTAL)
    assert report["rubric_weights"]["technical_accuracy"] == 0.40
    assert {d["dimension"] for d in report["dimensions"]} == set(SCORES)
    assert report["summary"].startswith("Solid understanding")
    assert report["unsupported_claims"] == ["mentions a cache layer"]
    # The report carries the conversation it judged — a scorecard a candidate
    # cannot check against what they said is the thing this product replaces.
    assert len(report["transcript"]) == len(turns)

    interview = db_session.get(Interview, interview_id)
    assert interview.status is InterviewStatus.COMPLETED
    assert interview.stage is InterviewStage.DONE
    assert interview.total_score == pytest.approx(EXPECTED_TOTAL)


def test_reconnecting_resumes_the_same_conversation(
    client: TestClient, db_session: Session, stub_question_generator, stub_live_agents
):
    """The transcript lives in Postgres, so a dropped connection loses nothing
    and — just as importantly — a second connect does not restart the
    interview."""
    from src.domains.interview.exceptions import InterviewFinished

    token, profile = _candidate(db_session, "resume.interview@example.com")
    project = _verified_project(db_session, profile)
    interview_id = client.post(
        f"{INTERVIEW_BASE}/projects/{project.id}/start", headers=_auth(token)
    ).json()["id"]
    _generate_questions(db_session)

    _open_conversation(db_session, profile, interview_id)
    client.post(
        f"{INTERVIEW_BASE}/{interview_id}/turns",
        json={"text": "It retries webhooks."},
        headers=_auth(token),
    )
    before = client.get(f"{INTERVIEW_BASE}/{interview_id}", headers=_auth(token)).json()

    # What a reconnect does: read the state back. It must not re-open.
    after = client.get(f"{INTERVIEW_BASE}/{interview_id}", headers=_auth(token)).json()
    assert [t["id"] for t in after["transcript"]] == [t["id"] for t in before["transcript"]]

    with pytest.raises(InterviewFinished):
        _open_conversation(db_session, profile, interview_id)


def test_report_is_not_available_before_scoring_completes(
    client: TestClient, db_session: Session, stub_question_generator
):
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


def test_a_candidate_cannot_speak_into_another_candidates_interview(
    client: TestClient, db_session: Session, stub_question_generator, stub_live_agents
):
    """The read path's 403 is not enough on its own — the write path is the one
    that would put words in someone else's transcript."""
    token_a, profile_a = _candidate(db_session, "owner.turns@example.com")
    project = _verified_project(db_session, profile_a)
    interview_id = client.post(
        f"{INTERVIEW_BASE}/projects/{project.id}/start", headers=_auth(token_a)
    ).json()["id"]
    _generate_questions(db_session)

    token_b, _ = _candidate(db_session, "intruder.turns@example.com")
    resp = client.post(
        f"{INTERVIEW_BASE}/{interview_id}/turns", json={"text": "hello"}, headers=_auth(token_b)
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Interview integrity
# ---------------------------------------------------------------------------
#
# These cover the room's side channel, not the conversation. The property that
# matters most is the last one: nothing written here may reach the transcript,
# the flags, or the score, because these are observations about a candidate's
# *room* and the interview is meant to be about their code.


def _integrity_event(sequence: int, event_type: str = "tab_hidden", **overrides) -> dict:
    event = {
        "client_sequence": sequence,
        "event_type": event_type,
        "elapsed_seconds": 30 + sequence,
    }
    event.update(overrides)
    return event


def test_integrity_events_are_recorded_and_counted(
    client: TestClient, db_session: Session, stub_question_generator
):
    token, profile = _candidate(db_session, "integrity.counts@example.com")
    project = _verified_project(db_session, profile)
    interview_id = client.post(
        f"{INTERVIEW_BASE}/projects/{project.id}/start", headers=_auth(token)
    ).json()["id"]

    resp = client.post(
        f"{INTERVIEW_BASE}/{interview_id}/integrity",
        json={
            "events": [
                _integrity_event(1, "tab_hidden", duration_seconds=12),
                _integrity_event(2, "window_blur"),
                _integrity_event(3, "tab_hidden"),
                _integrity_event(4, "camera_disabled", detail={"reason": "candidate_toggle"}),
            ]
        },
        headers=_auth(token),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["counts"] == {"tab_hidden": 2, "window_blur": 1, "camera_disabled": 1}
    assert body["total"] == 4
    assert body["events"][0]["duration_seconds"] == 12
    assert body["events"][3]["detail"] == {"reason": "candidate_toggle"}


def test_replayed_integrity_batches_do_not_double_count(
    client: TestClient, db_session: Session, stub_question_generator
):
    """The room flushes on unload, which fires twice on some browsers. Without
    the uniqueness constraint, closing a laptop lid would inflate a candidate's
    own integrity record."""
    token, profile = _candidate(db_session, "integrity.replay@example.com")
    project = _verified_project(db_session, profile)
    interview_id = client.post(
        f"{INTERVIEW_BASE}/projects/{project.id}/start", headers=_auth(token)
    ).json()["id"]

    batch = {"events": [_integrity_event(1), _integrity_event(2, "fullscreen_exit")]}
    client.post(f"{INTERVIEW_BASE}/{interview_id}/integrity", json=batch, headers=_auth(token))
    resp = client.post(f"{INTERVIEW_BASE}/{interview_id}/integrity", json=batch, headers=_auth(token))

    assert resp.json()["total"] == 2


def test_unknown_integrity_event_types_are_rejected(
    client: TestClient, db_session: Session, stub_question_generator
):
    token, profile = _candidate(db_session, "integrity.unknown@example.com")
    project = _verified_project(db_session, profile)
    interview_id = client.post(
        f"{INTERVIEW_BASE}/projects/{project.id}/start", headers=_auth(token)
    ).json()["id"]

    resp = client.post(
        f"{INTERVIEW_BASE}/{interview_id}/integrity",
        json={"events": [_integrity_event(1, "cheating_detected")]},
        headers=_auth(token),
    )
    assert resp.status_code == 422


def test_a_candidate_cannot_write_integrity_events_onto_another_interview(
    client: TestClient, db_session: Session, stub_question_generator
):
    token_a, profile_a = _candidate(db_session, "integrity.owner@example.com")
    project = _verified_project(db_session, profile_a)
    interview_id = client.post(
        f"{INTERVIEW_BASE}/projects/{project.id}/start", headers=_auth(token_a)
    ).json()["id"]

    token_b, _ = _candidate(db_session, "integrity.intruder@example.com")
    resp = client.post(
        f"{INTERVIEW_BASE}/{interview_id}/integrity",
        json={"events": [_integrity_event(1)]},
        headers=_auth(token_b),
    )
    assert resp.status_code == 403
    assert client.get(f"{INTERVIEW_BASE}/{interview_id}/integrity", headers=_auth(token_b)).status_code == 403


def test_integrity_events_are_accepted_after_the_conversation_ends(
    client: TestClient, db_session: Session, stub_question_generator, stub_live_agents
):
    """The final flush races the wrap-up turn by construction. Rejecting it once
    the interview left IN_PROGRESS would drop exactly the events from the end of
    the session, which is where they matter most."""
    from src.domains.interview import service

    token, profile = _candidate(db_session, "integrity.late@example.com")
    project = _verified_project(db_session, profile)
    interview_id = client.post(
        f"{INTERVIEW_BASE}/projects/{project.id}/start", headers=_auth(token)
    ).json()["id"]
    _generate_questions(db_session)
    _open_conversation(db_session, profile, interview_id)

    interview = db_session.get(Interview, uuid.UUID(interview_id))
    interview.stage = InterviewStage.DONE
    interview.status = InterviewStatus.EVALUATING
    db_session.commit()

    resp = client.post(
        f"{INTERVIEW_BASE}/{interview_id}/integrity",
        json={"events": [_integrity_event(9, "connection_lost")]},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["counts"] == {"connection_lost": 1}
    assert service is not None  # import kept meaningful for the reader


def test_integrity_events_never_reach_the_transcript_or_the_score(
    client: TestClient,
    db_session: Session,
    stub_question_generator,
    stub_live_agents,
    stub_scorer,
):
    """The separation the whole design rests on.

    An interview with a wall of integrity events must score identically to one
    with none: the Scorer reads turns and verification flags, and this table is
    not among its inputs.
    """
    from src.jobs.tasks.interview import score_interview_task
    from src.platform.models import AsyncJob

    token, profile = _candidate(db_session, "integrity.isolation@example.com")
    project = _verified_project(db_session, profile)
    interview_id = client.post(
        f"{INTERVIEW_BASE}/projects/{project.id}/start", headers=_auth(token)
    ).json()["id"]
    _generate_questions(db_session)
    _open_conversation(db_session, profile, interview_id)

    client.post(
        f"{INTERVIEW_BASE}/{interview_id}/integrity",
        json={"events": [_integrity_event(i, "tab_hidden") for i in range(1, 11)]},
        headers=_auth(token),
    )

    transcript_before = client.get(f"{INTERVIEW_BASE}/{interview_id}", headers=_auth(token)).json()
    assert all("tab_hidden" not in turn["text"] for turn in transcript_before["transcript"])

    interview = db_session.get(Interview, uuid.UUID(interview_id))
    interview.stage = InterviewStage.DONE
    interview.status = InterviewStatus.EVALUATING
    db_session.commit()

    from src.domains.interview import service as interview_service

    interview_service._dispatch_scoring(db_session, interview)
    job = db_session.execute(
        select(AsyncJob).where(AsyncJob.job_type == "score_interview")
    ).scalars().first()
    score_interview_task.run(str(job.id))

    report = client.get(f"{INTERVIEW_BASE}/{interview_id}/report", headers=_auth(token)).json()
    assert report["total_score"] == EXPECTED_TOTAL
    assert "integrity" not in report
