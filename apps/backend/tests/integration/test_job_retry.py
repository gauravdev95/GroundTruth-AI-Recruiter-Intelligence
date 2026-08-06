"""Integration tests for the dead-letter surface's retry action
(`POST /api/v1/jobs/{id}/retry`, `GET /api/v1/jobs`).

`AsyncJob` rows are constructed directly via the ORM to simulate a job that
already exhausted retries and was dead-lettered by
`jobs/tasks/dead_letter.py::record_dead_letter` — that task itself has no
HTTP surface, so it isn't re-tested here.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.domains.auth import service as auth_service
from src.domains.auth.models import CandidateProfile
from src.domains.auth.schemas import CandidateRegisterRequest
from src.domains.auth.security import create_access_token
from src.platform.models import AsyncJob, AsyncJobStatus


@pytest.fixture(autouse=True)
def stub_broker(monkeypatch):
    monkeypatch.setattr("src.jobs.dispatch.dispatch", lambda job, task, *, queue, args=None: None)


def _candidate(db_session: Session, email: str) -> tuple[str, CandidateProfile]:
    user = auth_service.register_candidate(
        db_session,
        CandidateRegisterRequest(
            full_name="Ada Lovelace", email=email, phone_number="+14155552671",
            password="StrongPass1!", confirm_password="StrongPass1!", captcha_token="test", accept_terms=True,
        ),
    )
    token = create_access_token(user_id=user.id, role=user.role.value)
    from sqlalchemy import select

    profile = db_session.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id)).scalar_one()
    return token, profile


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _dead_lettered_job(db_session: Session, candidate_profile_id) -> AsyncJob:
    job = AsyncJob(
        job_type="extract_resume",
        status=AsyncJobStatus.FAILED,
        payload={"candidate_profile_id": str(candidate_profile_id)},
        error="LLM provider timed out after 3 attempts",
        attempts=3,
        dead_lettered_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def test_retry_requeues_a_dead_lettered_job(client: TestClient, db_session: Session) -> None:
    token, profile = _candidate(db_session, "retry.owner@example.com")
    job = _dead_lettered_job(db_session, profile.id)

    resp = client.post(f"/api/v1/jobs/{job.id}/retry", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["is_dead_lettered"] is False
    assert body["error"] is None
    assert body["attempts"] == 0


def test_retry_is_forbidden_for_a_non_owner(client: TestClient, db_session: Session) -> None:
    owner_token, profile = _candidate(db_session, "retry.real-owner@example.com")
    other_token, _other_profile = _candidate(db_session, "retry.stranger@example.com")
    job = _dead_lettered_job(db_session, profile.id)

    resp = client.post(f"/api/v1/jobs/{job.id}/retry", headers=_auth(other_token))
    assert resp.status_code == 403


def test_retry_rejects_a_job_that_is_not_dead_lettered(client: TestClient, db_session: Session) -> None:
    token, profile = _candidate(db_session, "retry.notdead@example.com")
    job = AsyncJob(
        job_type="extract_resume",
        status=AsyncJobStatus.SUCCEEDED,
        payload={"candidate_profile_id": str(profile.id)},
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    resp = client.post(f"/api/v1/jobs/{job.id}/retry", headers=_auth(token))
    assert resp.status_code == 409


def test_list_my_jobs_is_scoped_to_the_caller(client: TestClient, db_session: Session) -> None:
    token, profile = _candidate(db_session, "retry.list-owner@example.com")
    _other_token, other_profile = _candidate(db_session, "retry.list-other@example.com")
    mine = _dead_lettered_job(db_session, profile.id)
    _dead_lettered_job(db_session, other_profile.id)

    resp = client.get("/api/v1/jobs", headers=_auth(token))
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.json()}
    assert str(mine.id) in ids
    assert len(resp.json()) == 1
