"""Cross-tenant authorization: the specific hardening pass this file exists
for is asserting 403/404 *actually happens* at the query layer, not just
that the code looks like it should. Every check here executes two real
accounts against a real HTTP request — never a code-reading exercise.

Marketplace-loop authz for messaging, notes, and the evidence card already
has coverage in `test_marketplace_pipeline.py`; this file covers the
remaining pipeline-domain surfaces that didn't yet have a dedicated
cross-tenant test: a candidate's own application detail/messages, and a
recruiter's Kanban pipeline board.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domains.ai.job_extraction_schema import ExtractedSkill, JobRequirementExtraction
from src.domains.auth import service as auth_service
from src.domains.auth.models import CandidateProfile, RecruiterProfile
from src.domains.auth.schemas import CandidateRegisterRequest, RecruiterRegisterRequest
from src.domains.auth.security import create_access_token
from src.domains.matching.embeddings import EmbeddableEntityType
from src.domains.pipeline.models import Application
from src.domains.skills.models import CandidateSkill, ProficiencyLevel, Skill, SkillCategory
from src.platform.models import AsyncJob

JOBS_BASE = "/api/v1/recruiter/jobs"
STUDENT_BASE = "/api/v1/student"
RECRUITER_BASE = "/api/v1/recruiter"

VALID_CREATE = {
    "title": "Backend Engineer Intern",
    "description": "Build APIs in Python using FastAPI.",
    "job_type": "internship",
    "experience_level": "entry",
    "location": "Bangalore",
    "is_remote": False,
}
EXTRACTION = JobRequirementExtraction(
    must_have_skills=[ExtractedSkill(name="Python", min_proficiency="intermediate")], desirable_skills=[]
)
FIXED_VECTOR = [0.1] * 1536


class _FixedEmbedder:
    def embed(self, text: str) -> list[float]:
        return FIXED_VECTOR


class _SessionProxy:
    def __init__(self, session: Session) -> None:
        self._session = session

    def __enter__(self) -> Session:
        return self._session

    def __exit__(self, *_: object) -> bool:
        return False


@pytest.fixture(autouse=True)
def stub_broker(monkeypatch):
    monkeypatch.setattr("src.jobs.dispatch.dispatch", lambda job, task, *, queue, args=None: None)


@pytest.fixture(autouse=True)
def worker_sessions(monkeypatch, db_session: Session):
    factory = lambda: _SessionProxy(db_session)  # noqa: E731
    monkeypatch.setattr("src.jobs.tasks.job_extraction.SessionLocal", factory)
    monkeypatch.setattr("src.jobs.tasks.matching.SessionLocal", factory)
    monkeypatch.setattr("src.jobs.celery_app.SessionLocal", factory)


@pytest.fixture(autouse=True)
def stub_embedder(monkeypatch):
    monkeypatch.setattr("src.domains.matching.embeddings.get_embedder", lambda: _FixedEmbedder())


@pytest.fixture()
def stub_extractor(monkeypatch):
    monkeypatch.setattr(
        "src.jobs.tasks.job_extraction.get_job_requirement_extractor",
        lambda: type("S", (), {"extract_requirements": staticmethod(lambda **kw: EXTRACTION)})(),
    )


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _recruiter(db_session: Session, email: str, company_name: str = "Acme Corp") -> tuple[str, RecruiterProfile]:
    user, otp, _ = auth_service.register_recruiter(
        db_session,
        RecruiterRegisterRequest(
            full_name="Grace Hopper", company_name=company_name, company_email=email,
            password="StrongPass1!", confirm_password="StrongPass1!", captcha_token="test", accept_terms=True,
        ),
    )
    auth_service.confirm_email_otp(db_session, user.email, otp)
    token = create_access_token(user_id=user.id, role=user.role.value)
    profile = db_session.execute(select(RecruiterProfile).where(RecruiterProfile.user_id == user.id)).scalar_one()
    return token, profile


def _candidate(db_session: Session, email: str) -> tuple[str, CandidateProfile]:
    user, otp, _ = auth_service.register_candidate(
        db_session,
        CandidateRegisterRequest(
            full_name="Ada Lovelace", email=email, phone_number="+14155552671",
            password="StrongPass1!", confirm_password="StrongPass1!", captcha_token="test", accept_terms=True,
        ),
    )
    auth_service.confirm_email_otp(db_session, user.email, otp)
    token = create_access_token(user_id=user.id, role=user.role.value)
    profile = db_session.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id)).scalar_one()

    profile.is_discoverable = True
    profile.profile_strength = 80
    profile.graduation_year = datetime.now(timezone.utc).year

    skill = db_session.execute(select(Skill).where(Skill.name == "Python")).scalar_one_or_none()
    if skill is None:
        skill = Skill(name="Python", category=SkillCategory.LANGUAGE)
        db_session.add(skill)
        db_session.flush()
    db_session.add(
        CandidateSkill(
            candidate_profile_id=profile.id, skill_id=skill.id,
            proficiency=ProficiencyLevel.ADVANCED, evidence_weight=0.8,
        )
    )
    db_session.commit()
    return token, profile


def _matched_and_applied_job(
    client: TestClient, db_session: Session, recruiter_token: str, candidate_token: str, candidate_profile: CandidateProfile
) -> tuple[str, str]:
    """Returns (job_id, application_id) — a candidate fully applied to a
    published, matched job, so there's a real `Application` row to probe."""
    from src.domains.matching import embeddings, service as matching_service
    from src.jobs.tasks.job_extraction import extract_job_requirements_task
    from src.jobs.tasks.matching import embed_and_match_job_task

    embeddings.embed_candidate_profile(db_session, candidate_profile)
    db_session.commit()

    created = client.post(JOBS_BASE, json=VALID_CREATE, headers=_auth(recruiter_token)).json()
    client.post(f"{JOBS_BASE}/{created['id']}/submit", headers=_auth(recruiter_token))
    extraction_job = db_session.execute(
        select(AsyncJob).where(AsyncJob.job_type == "extract_job_requirements")
    ).scalars().first()
    extract_job_requirements_task.run(str(extraction_job.id))

    client.post(
        f"{JOBS_BASE}/{created['id']}/confirm",
        json={"seniority": "entry", "skills": [{"skill_name": "Python", "min_proficiency": "intermediate", "is_required": True, "weight": 1.0}]},
        headers=_auth(recruiter_token),
    )
    match_job = db_session.execute(select(AsyncJob).where(AsyncJob.job_type == "embed_and_match_job")).scalars().first()
    embed_and_match_job_task.run(str(match_job.id))
    matching_service.recompute_for_candidate(db_session, candidate_profile)

    job_id = created["id"]
    client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))
    application_id = str(
        db_session.execute(select(Application).where(Application.job_posting_id == job_id)).scalar_one().id
    )
    return job_id, application_id


# --------------------------------------------------------------------------
# Student A cannot reach Student B's application
# --------------------------------------------------------------------------


def test_student_cannot_read_another_students_application_detail(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    recruiter_token, _rp = _recruiter(db_session, "authz.recruiter@acme.com")
    owner_token, owner_profile = _candidate(db_session, "authz.owner@example.com")
    _job_id, application_id = _matched_and_applied_job(client, db_session, recruiter_token, owner_token, owner_profile)

    intruder_token, _intruder_profile = _candidate(db_session, "authz.intruder@example.com")

    resp = client.get(f"{STUDENT_BASE}/applications/{application_id}", headers=_auth(intruder_token))
    assert resp.status_code in (403, 404)

    # The rightful owner can still read it — proves the check is about
    # identity, not a blanket lockout.
    own_resp = client.get(f"{STUDENT_BASE}/applications/{application_id}", headers=_auth(owner_token))
    assert own_resp.status_code == 200


def test_student_cannot_read_another_students_application_messages(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    recruiter_token, _rp = _recruiter(db_session, "authz.msg-recruiter@acme.com")
    owner_token, owner_profile = _candidate(db_session, "authz.msg-owner@example.com")
    _job_id, application_id = _matched_and_applied_job(client, db_session, recruiter_token, owner_token, owner_profile)

    intruder_token, _intruder_profile = _candidate(db_session, "authz.msg-intruder@example.com")

    read_resp = client.get(f"{STUDENT_BASE}/applications/{application_id}/messages", headers=_auth(intruder_token))
    assert read_resp.status_code in (403, 404)

    send_resp = client.post(
        f"{STUDENT_BASE}/applications/{application_id}/messages",
        json={"body": "I shouldn't be able to send this."},
        headers=_auth(intruder_token),
    )
    assert send_resp.status_code in (403, 404)


# --------------------------------------------------------------------------
# Recruiter A cannot reach Recruiter B's Kanban pipeline
# --------------------------------------------------------------------------


def test_recruiter_cannot_read_another_recruiters_pipeline_board(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    owner_token, _op = _recruiter(db_session, "authz.pipeline-owner@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "authz.pipeline-candidate@example.com")
    job_id, _application_id = _matched_and_applied_job(
        client, db_session, owner_token, candidate_token, candidate_profile
    )

    outsider_token, _outp = _recruiter(db_session, "authz.pipeline-outsider@othercorp.com", company_name="Other Corp")

    resp = client.get(f"{JOBS_BASE}/{job_id}/pipeline", headers=_auth(outsider_token))
    assert resp.status_code == 403

    own_resp = client.get(f"{JOBS_BASE}/{job_id}/pipeline", headers=_auth(owner_token))
    assert own_resp.status_code == 200
    assert len(own_resp.json()["applied"]) == 1


# --------------------------------------------------------------------------
# Role gate: a candidate token cannot reach recruiter-only pipeline surfaces
# --------------------------------------------------------------------------


def test_candidate_is_forbidden_from_recruiter_pipeline_endpoints(client: TestClient, db_session: Session) -> None:
    candidate_token, _profile = _candidate(db_session, "authz.role-gate@example.com")

    import uuid

    random_id = uuid.uuid4()
    assert client.get(f"{JOBS_BASE}/{random_id}/pipeline", headers=_auth(candidate_token)).status_code in (403, 404)
    assert client.get(f"{RECRUITER_BASE}/analytics/funnel", headers=_auth(candidate_token)).status_code == 403
    assert client.get(f"{RECRUITER_BASE}/candidates/{random_id}/evidence", headers=_auth(candidate_token)).status_code in (403, 404)
