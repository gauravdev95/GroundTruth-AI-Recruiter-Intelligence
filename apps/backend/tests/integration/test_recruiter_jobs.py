"""Integration tests for recruiter job postings — company activation, the
job state machine, and authorization. The LLM extractor is stubbed (same
pattern as `test_resume_import.py::stub_extractor`); this is not a test of
Gemini, it's a test of the state machine and the confirmation gate.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domains.ai.job_extraction_schema import ExtractedSkill, JobRequirementExtraction
from src.domains.auth import service as auth_service
from src.domains.auth.models import CandidateProfile, RecruiterProfile
from src.domains.auth.schemas import CandidateRegisterRequest, RecruiterRegisterRequest
from src.domains.auth.security import create_access_token
from src.domains.company.models import Company
from src.domains.recruiter.models import JobPosting, JobStatus
from src.platform.models import AsyncJob

JOBS_BASE = "/api/v1/recruiter/jobs"

VALID_CREATE = {
    "title": "Backend Engineer Intern",
    "description": "Build APIs in Python. Must know FastAPI and PostgreSQL. Docker is a plus.",
    "job_type": "internship",
    "experience_level": "entry",
    "location": "Bangalore",
    "is_remote": False,
}

EXTRACTION = JobRequirementExtraction(
    must_have_skills=[
        ExtractedSkill(name="Python", min_proficiency="advanced"),
        ExtractedSkill(name="FastAPI", min_proficiency="intermediate"),
    ],
    desirable_skills=[ExtractedSkill(name="Docker", min_proficiency="novice")],
    seniority="entry",
    role_type="Backend Engineer",
    is_remote=False,
    location_constraints="Bangalore",
)


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
    monkeypatch.setattr("src.jobs.tasks.job_extraction.SessionLocal", factory)
    monkeypatch.setattr("src.jobs.celery_app.SessionLocal", factory)


@pytest.fixture()
def stub_extractor(monkeypatch):
    class _Stub:
        def __init__(self) -> None:
            self.error: Exception | None = None

        def extract_requirements(self, *, title, description):
            if self.error is not None:
                raise self.error
            return EXTRACTION

    stub = _Stub()
    monkeypatch.setattr("src.jobs.tasks.job_extraction.get_job_requirement_extractor", lambda: stub)
    return stub


def _recruiter(db_session: Session, email: str = "hiring@acme.com") -> tuple[str, RecruiterProfile]:
    user = auth_service.register_recruiter(
        db_session,
        RecruiterRegisterRequest(
            full_name="Grace Hopper",
            company_name="Acme Corp",
            company_email=email,
            password="StrongPass1!",
            confirm_password="StrongPass1!",
            captcha_token="test",
            accept_terms=True,
        ),
    )
    token = create_access_token(user_id=user.id, role=user.role.value)
    profile = db_session.execute(
        select(RecruiterProfile).where(RecruiterProfile.user_id == user.id)
    ).scalar_one()
    return token, profile


def _candidate(db_session: Session, email: str = "student@example.com") -> str:
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
    return create_access_token(user_id=user.id, role=user.role.value)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------
# Company activation
# --------------------------------------------------------------------------


def test_recruiter_registration_creates_and_links_a_company(db_session: Session) -> None:
    _token, profile = _recruiter(db_session, "first@newco.com")
    assert profile.company_id is not None

    company = db_session.get(Company, profile.company_id)
    assert company is not None
    assert company.name == "Acme Corp"
    assert company.domain == "newco.com"


def test_two_recruiters_with_the_same_company_name_share_one_company_row(db_session: Session) -> None:
    _t1, profile1 = _recruiter(db_session, "one@acme.com")
    _t2, profile2 = _recruiter(db_session, "two@acme.com")
    assert profile1.company_id == profile2.company_id


# --------------------------------------------------------------------------
# Job state machine
# --------------------------------------------------------------------------


def test_create_job_starts_as_draft(client: TestClient, db_session: Session) -> None:
    token, _profile = _recruiter(db_session, "draft@acme.com")
    resp = client.post(JOBS_BASE, json=VALID_CREATE, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "draft"


def test_full_lifecycle_draft_to_published_to_closed_to_reopened(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    from sqlalchemy import select as sa_select

    from src.jobs.tasks.job_extraction import extract_job_requirements_task

    token, _profile = _recruiter(db_session, "lifecycle@acme.com")

    created = client.post(JOBS_BASE, json=VALID_CREATE, headers=_auth(token)).json()
    job_id = created["id"]

    submit = client.post(f"{JOBS_BASE}/{job_id}/submit", headers=_auth(token))
    assert submit.status_code == 202, submit.text
    assert submit.json()["job"]["status"] == "extracting"

    async_job = db_session.execute(
        sa_select(AsyncJob).where(AsyncJob.job_type == "extract_job_requirements")
    ).scalars().first()
    assert async_job is not None
    extract_job_requirements_task.run(str(async_job.id))

    detail = client.get(f"{JOBS_BASE}/{job_id}", headers=_auth(token)).json()
    assert detail["job"]["status"] == "awaiting_confirmation"
    assert detail["extracted_requirements"]["must_have_skills"][0]["name"] == "Python"

    confirm_payload = {
        "seniority": "entry",
        "skills": [
            {"skill_name": "Python", "min_proficiency": "advanced", "is_required": True, "weight": 1.0},
            {"skill_name": "FastAPI", "min_proficiency": "intermediate", "is_required": True, "weight": 0.8},
            {"skill_name": "Docker", "min_proficiency": "novice", "is_required": False, "weight": 0.3},
        ],
    }
    confirmed = client.post(f"{JOBS_BASE}/{job_id}/confirm", json=confirm_payload, headers=_auth(token))
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["job"]["status"] == "published"
    assert len(confirmed.json()["requirements"]) == 3

    closed = client.post(f"{JOBS_BASE}/{job_id}/close", headers=_auth(token))
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    reopened = client.post(f"{JOBS_BASE}/{job_id}/reopen", headers=_auth(token))
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "published"


def test_extraction_failure_reverts_job_to_draft_with_error(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    from sqlalchemy import select as sa_select

    from src.domains.ai.exceptions import LLMRefused
    from src.jobs.celery_app import NonRetryableJobError
    from src.jobs.tasks.job_extraction import extract_job_requirements_task

    token, _profile = _recruiter(db_session, "failure@acme.com")
    stub_extractor.error = LLMRefused("nope")

    created = client.post(JOBS_BASE, json=VALID_CREATE, headers=_auth(token)).json()
    client.post(f"{JOBS_BASE}/{created['id']}/submit", headers=_auth(token))

    async_job = db_session.execute(
        sa_select(AsyncJob).where(AsyncJob.job_type == "extract_job_requirements")
    ).scalars().first()

    with pytest.raises(NonRetryableJobError):
        extract_job_requirements_task.run(str(async_job.id))

    job = db_session.get(JobPosting, created["id"])
    assert job.status is JobStatus.DRAFT
    assert job.extraction_error is not None


def test_cannot_confirm_a_job_that_isnt_awaiting_confirmation(client: TestClient, db_session: Session) -> None:
    token, _profile = _recruiter(db_session, "wrongstate@acme.com")
    created = client.post(JOBS_BASE, json=VALID_CREATE, headers=_auth(token)).json()

    resp = client.post(
        f"{JOBS_BASE}/{created['id']}/confirm",
        json={"seniority": "entry", "skills": [{"skill_name": "Python", "min_proficiency": "advanced"}]},
        headers=_auth(token),
    )
    assert resp.status_code == 409


# --------------------------------------------------------------------------
# Authorization
# --------------------------------------------------------------------------


def test_student_is_forbidden_from_every_recruiter_job_endpoint(client: TestClient, db_session: Session) -> None:
    student_token = _candidate(db_session)
    assert client.get(JOBS_BASE, headers=_auth(student_token)).status_code == 403
    assert client.post(JOBS_BASE, json=VALID_CREATE, headers=_auth(student_token)).status_code == 403


def test_recruiter_cannot_see_another_recruiters_job(client: TestClient, db_session: Session) -> None:
    token_a, _profile_a = _recruiter(db_session, "owner@acme.com")
    created = client.post(JOBS_BASE, json=VALID_CREATE, headers=_auth(token_a)).json()

    token_b, _profile_b = _recruiter(db_session, "other@othercorp.com")
    resp = client.get(f"{JOBS_BASE}/{created['id']}", headers=_auth(token_b))
    assert resp.status_code == 403


def test_job_list_only_returns_the_callers_own_jobs(client: TestClient, db_session: Session) -> None:
    token_a, _profile_a = _recruiter(db_session, "lister@acme.com")
    client.post(JOBS_BASE, json=VALID_CREATE, headers=_auth(token_a))

    token_b, _profile_b = _recruiter(db_session, "other2@othercorp.com")
    client.post(JOBS_BASE, json={**VALID_CREATE, "title": "Other job"}, headers=_auth(token_b))

    resp = client.get(JOBS_BASE, headers=_auth(token_a))
    titles = {job["title"] for job in resp.json()["jobs"]}
    assert titles == {"Backend Engineer Intern"}
