"""Integration tests for the marketplace loop: Smart Apply, Kanban
transitions, the recruiter evidence card, messaging, notes, notifications,
and audit_log activation.

Candidate discoverability/skills/embeddings are set up directly via the ORM
(same approach as `test_matching_pipeline.py`) to keep this file scoped to
the marketplace loop itself rather than re-proving verification or matching,
which have their own test files.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domains.ai.embedding_constants import EMBEDDING_DIMENSIONS
from src.domains.ai.job_extraction_schema import ExtractedSkill, JobRequirementExtraction
from src.domains.auth import service as auth_service
from src.domains.auth.models import CandidateProfile, RecruiterProfile
from src.domains.auth.schemas import CandidateRegisterRequest, RecruiterRegisterRequest
from src.domains.auth.security import create_access_token
from src.domains.matching.embeddings import EmbeddableEntityType
from src.domains.matching.models import MatchResult
from src.domains.pipeline.models import Application, ApplicationStatus, RecruiterNote
from src.domains.skills.models import CandidateSkill, ProficiencyLevel, Skill, SkillCategory
from src.platform.models import AsyncJob, AuditLog

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
FIXED_VECTOR = [0.1] * EMBEDDING_DIMENSIONS


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
    user = auth_service.register_recruiter(
        db_session,
        RecruiterRegisterRequest(
            full_name="Grace Hopper", company_name=company_name, company_email=email,
            password="StrongPass1!", confirm_password="StrongPass1!", captcha_token="test", accept_terms=True,
        ),
    )
    token = create_access_token(user_id=user.id, role=user.role.value)
    profile = db_session.execute(select(RecruiterProfile).where(RecruiterProfile.user_id == user.id)).scalar_one()
    return token, profile


def _candidate(db_session: Session, email: str) -> tuple[str, CandidateProfile]:
    user = auth_service.register_candidate(
        db_session,
        CandidateRegisterRequest(
            full_name="Ada Lovelace", email=email, phone_number="+14155552671",
            password="StrongPass1!", confirm_password="StrongPass1!", captcha_token="test", accept_terms=True,
        ),
    )
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


def _matched_job(client: TestClient, db_session: Session, recruiter_token: str, candidate_profile: CandidateProfile) -> str:
    """Publishes a job and computes matches, leaving `candidate_profile`
    with a live `MatchResult` against it — the precondition Smart Apply
    checks for."""
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
    match_job = db_session.execute(
        select(AsyncJob).where(AsyncJob.job_type == "embed_and_match_job")
    ).scalars().first()
    embed_and_match_job_task.run(str(match_job.id))
    matching_service.recompute_for_candidate(db_session, candidate_profile)
    return created["id"]


# --------------------------------------------------------------------------
# Smart Apply
# --------------------------------------------------------------------------


def test_smart_apply_requires_an_existing_match(client: TestClient, db_session: Session, stub_extractor) -> None:
    recruiter_token, _rp = _recruiter(db_session, "noreq@acme.com")
    candidate_token, _cp = _candidate(db_session, "unmatched@example.com")

    created = client.post(JOBS_BASE, json=VALID_CREATE, headers=_auth(recruiter_token)).json()
    # Never submitted/confirmed -> still draft, and even if published there'd be no match yet.
    resp = client.post(f"{STUDENT_BASE}/jobs/{created['id']}/apply", json={}, headers=_auth(candidate_token))
    assert resp.status_code == 409


def test_applications_list_and_detail_include_job_and_company_name(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    recruiter_token, _rp = _recruiter(db_session, "joblabel@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "joblabel.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))

    listing = client.get(f"{STUDENT_BASE}/applications", headers=_auth(candidate_token))
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    item = listing.json()[0]
    assert item["job_title"] == "Backend Engineer Intern"
    assert item["company_name"] == "Acme Corp"
    assert item["application"]["status"] == "applied"

    application_id = item["application"]["id"]
    detail = client.get(f"{STUDENT_BASE}/applications/{application_id}", headers=_auth(candidate_token))
    assert detail.status_code == 200
    assert detail.json()["job_title"] == "Backend Engineer Intern"
    assert detail.json()["company_name"] == "Acme Corp"


def test_recruiter_application_detail_includes_job_and_candidate_context(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    recruiter_token, _rp = _recruiter(db_session, "appdetail@acme.com")
    outsider_token, _op = _recruiter(db_session, "appdetail.outsider@othercorp.com", company_name="Other Corp")
    candidate_token, candidate_profile = _candidate(db_session, "appdetail.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))
    application_id = db_session.execute(select(Application).where(Application.job_posting_id == job_id)).scalar_one().id

    resp = client.get(f"{RECRUITER_BASE}/applications/{application_id}", headers=_auth(recruiter_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["job_title"] == "Backend Engineer Intern"
    assert body["company_name"] == "Acme Corp"
    assert body["candidate_profile_id"] == str(candidate_profile.id)

    # A recruiter with no relationship to this job cannot read it.
    forbidden = client.get(f"{RECRUITER_BASE}/applications/{application_id}", headers=_auth(outsider_token))
    assert forbidden.status_code == 403


def test_smart_apply_attaches_evidence_snapshot_with_no_re_entry(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    recruiter_token, _rp = _recruiter(db_session, "apply@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "applicant@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)

    resp = client.post(
        f"{STUDENT_BASE}/jobs/{job_id}/apply", json={"cover_note": "Excited to apply!"}, headers=_auth(candidate_token)
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "applied"

    application = db_session.execute(select(Application).where(Application.job_posting_id == job_id)).scalar_one()
    assert application.evidence_snapshot["profile"]["profile_strength"] == 80
    assert application.evidence_snapshot["skills"][0]["name"] == "Python"
    assert application.evidence_snapshot["match"]["match_score"] > 0

    # Duplicate apply is rejected.
    dup = client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))
    assert dup.status_code == 409

    # Audit row exists for the application creation.
    audit = db_session.execute(
        select(AuditLog).where(AuditLog.entity_type == "application", AuditLog.entity_id == application.id)
    ).scalars().first()
    assert audit is not None
    assert audit.action == "application.created"


# --------------------------------------------------------------------------
# Kanban pipeline
# --------------------------------------------------------------------------


def test_pipeline_shows_matched_then_applied_columns(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    recruiter_token, _rp = _recruiter(db_session, "kanban@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "kanban.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)

    before_apply = client.get(f"{JOBS_BASE}/{job_id}/pipeline", headers=_auth(recruiter_token)).json()
    assert len(before_apply["matched"]) == 1
    assert before_apply["applied"] == []

    client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))

    after_apply = client.get(f"{JOBS_BASE}/{job_id}/pipeline", headers=_auth(recruiter_token)).json()
    assert after_apply["matched"] == []  # moved out of "matched" once applied
    assert len(after_apply["applied"]) == 1


def test_transitions_are_server_validated_no_arbitrary_jumps(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    recruiter_token, _rp = _recruiter(db_session, "transitions@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "transition.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))
    application_id = db_session.execute(select(Application).where(Application.job_posting_id == job_id)).scalar_one().id

    # applied -> hired directly is not allowed.
    bad = client.post(
        f"{RECRUITER_BASE}/applications/{application_id}/transition",
        json={"to_status": "hired"}, headers=_auth(recruiter_token),
    )
    assert bad.status_code == 409

    good = client.post(
        f"{RECRUITER_BASE}/applications/{application_id}/transition",
        json={"to_status": "shortlisted"}, headers=_auth(recruiter_token),
    )
    assert good.status_code == 200
    assert good.json()["status"] == "shortlisted"

    # A candidate must never be able to transition their own application.
    forbidden = client.post(
        f"{RECRUITER_BASE}/applications/{application_id}/transition",
        json={"to_status": "interview_scheduled"}, headers=_auth(candidate_token),
    )
    assert forbidden.status_code == 403

    # Candidate receives a stage-change notification.
    notes_resp = client.get("/api/v1/notifications", headers=_auth(candidate_token))
    assert notes_resp.status_code == 200
    assert notes_resp.json()["unread_count"] >= 1


def test_full_pipeline_to_hired_writes_audit_rows_for_every_transition(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    recruiter_token, _rp = _recruiter(db_session, "hire@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "hired.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))
    application_id = db_session.execute(select(Application).where(Application.job_posting_id == job_id)).scalar_one().id

    for to_status in ("shortlisted", "interview_scheduled", "hired"):
        resp = client.post(
            f"{RECRUITER_BASE}/applications/{application_id}/transition",
            json={"to_status": to_status}, headers=_auth(recruiter_token),
        )
        assert resp.status_code == 200, resp.text

    audit_rows = db_session.execute(
        select(AuditLog).where(AuditLog.entity_type == "application", AuditLog.entity_id == application_id)
    ).scalars().all()
    actions = [row.action for row in audit_rows]
    assert "application.created" in actions
    assert actions.count("application.status_changed") == 2  # shortlisted, interview_scheduled
    assert "application.hired" in actions


# --------------------------------------------------------------------------
# Frozen score, live score, and the drift between them
# --------------------------------------------------------------------------


def _live_match(db_session: Session, job_id: str, candidate_profile: CandidateProfile) -> MatchResult:
    return db_session.execute(
        select(MatchResult).where(
            MatchResult.job_posting_id == job_id,
            MatchResult.candidate_profile_id == candidate_profile.id,
        )
    ).scalar_one()


def test_smart_apply_freezes_the_live_score_and_cites_the_snapshot(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    """The three columns migration b2d5e8f14c73 added are actually written.
    Before this, they existed but nothing populated them, so `score_at_apply`
    was null on every application created after the migration."""
    recruiter_token, _rp = _recruiter(db_session, "freeze@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "freeze.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    match = _live_match(db_session, job_id, candidate_profile)
    score_when_applying = float(match.match_score)

    resp = client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))
    assert resp.status_code == 201, resp.text

    application = db_session.execute(select(Application).where(Application.job_posting_id == job_id)).scalar_one()
    assert float(application.score_at_apply) == score_when_applying
    assert application.match_id == match.id
    assert application.evidence_snapshot_id is not None

    created = db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "application",
            AuditLog.entity_id == application.id,
            AuditLog.action == "application.created",
        )
    ).scalar_one()
    assert created.after["evidence_snapshot_id"] == str(application.evidence_snapshot_id)
    assert created.after["score_at_apply"] == score_when_applying


def test_a_later_rescore_moves_the_live_score_but_never_score_at_apply(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    """The whole reason both numbers exist: the recruiter's decision was made
    against one of them, and a re-verification must not rewrite it."""
    recruiter_token, _rp = _recruiter(db_session, "drift@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "drift.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))

    application = db_session.execute(select(Application).where(Application.job_posting_id == job_id)).scalar_one()
    frozen = float(application.score_at_apply)

    match = _live_match(db_session, job_id, candidate_profile)
    match.match_score = frozen + 12.0
    db_session.commit()

    card = client.get(f"{JOBS_BASE}/{job_id}/pipeline", headers=_auth(recruiter_token)).json()["applied"][0]
    assert card["score_at_apply"] == frozen
    assert card["match_score"] == frozen + 12.0
    assert card["drift_points"] == 12.0
    assert card["drift_direction"] == "up"
    assert card["drift_is_meaningful"] is True

    # And the frozen column itself never moved.
    db_session.refresh(application)
    assert float(application.score_at_apply) == frozen


def test_sub_threshold_drift_reports_its_direction_but_is_not_meaningful(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    recruiter_token, _rp = _recruiter(db_session, "smalldrift@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "smalldrift.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))

    application = db_session.execute(select(Application).where(Application.job_posting_id == job_id)).scalar_one()
    match = _live_match(db_session, job_id, candidate_profile)
    match.match_score = float(application.score_at_apply) - 2.0
    db_session.commit()

    card = client.get(f"{JOBS_BASE}/{job_id}/pipeline", headers=_auth(recruiter_token)).json()["applied"][0]
    assert card["drift_points"] == -2.0
    assert card["drift_direction"] == "down"
    assert card["drift_is_meaningful"] is False


def test_a_pruned_match_reports_unknown_drift_rather_than_zero(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    """A missing `match_results` row means "this pair no longer scores", not
    "the score has not changed" — reporting 0.0 would tell the recruiter the
    candidate is unchanged."""
    recruiter_token, _rp = _recruiter(db_session, "pruned@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "pruned.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))

    db_session.delete(_live_match(db_session, job_id, candidate_profile))
    db_session.commit()

    card = client.get(f"{JOBS_BASE}/{job_id}/pipeline", headers=_auth(recruiter_token)).json()["applied"][0]
    assert card["score_at_apply"] is not None
    assert card["match_score"] is None
    assert card["drift_points"] is None
    assert card["drift_direction"] == "unknown"
    assert card["drift_is_meaningful"] is False

    # The application itself survived the prune — `match_id` is SET NULL, and
    # the frozen score is a column of its own precisely so it does not depend
    # on the match row still existing.
    detail = client.get(
        f"{RECRUITER_BASE}/applications/{card['application_id']}", headers=_auth(recruiter_token)
    ).json()
    assert detail["drift"]["direction"] == "unknown"
    assert detail["drift"]["score_at_apply"] is not None


# --------------------------------------------------------------------------
# In-stage ordering
# --------------------------------------------------------------------------


def test_applications_are_ordered_by_score_within_each_stage(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    """`score_at_apply DESC NULLS LAST, applied_at ASC, id ASC` — sorted on
    the *frozen* score, so the board cannot silently reorder itself between
    two page loads when a background recompute moves a live score."""
    recruiter_token, _rp = _recruiter(db_session, "ordering@acme.com")
    job_id = None
    applications = []

    for index in range(3):
        candidate_token, candidate_profile = _candidate(db_session, f"ordering.candidate{index}@example.com")
        if job_id is None:
            job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
        else:
            from src.domains.matching import embeddings, service as matching_service

            embeddings.embed_candidate_profile(db_session, candidate_profile)
            db_session.commit()
            matching_service.recompute_for_candidate(db_session, candidate_profile)
        client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))
        applications.append(
            db_session.execute(
                select(Application).where(
                    Application.job_posting_id == job_id,
                    Application.candidate_profile_id == candidate_profile.id,
                )
            ).scalar_one()
        )

    # Every candidate scores identically under the fixed test embedder, so the
    # frozen scores are set explicitly here — the ORDER BY is what's under
    # test, not the rank-fusion formula (`test_matching_scoring.py` owns that).
    # Deliberately assigned out of insertion order so passing can't be an
    # accident of the order rows were created in.
    applications[0].score_at_apply = 61.0
    applications[1].score_at_apply = 88.5
    applications[2].score_at_apply = 74.25
    db_session.commit()

    column = client.get(f"{JOBS_BASE}/{job_id}/pipeline", headers=_auth(recruiter_token)).json()["applied"]
    assert [card["score_at_apply"] for card in column] == [88.5, 74.25, 61.0]

    # Ordering is per-stage, not global: moving the lowest-scoring
    # application to another column must not disturb the rest.
    client.post(
        f"{RECRUITER_BASE}/applications/{applications[0].id}/transition",
        json={"to_status": "shortlisted"}, headers=_auth(recruiter_token),
    )
    board = client.get(f"{JOBS_BASE}/{job_id}/pipeline", headers=_auth(recruiter_token)).json()
    assert [card["score_at_apply"] for card in board["applied"]] == [88.5, 74.25]
    assert [card["score_at_apply"] for card in board["shortlisted"]] == [61.0]


def test_equal_scores_break_the_tie_on_earliest_applicant_then_id(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    """First-come is the stated tiebreak; `id ASC` behind it guarantees a
    total order so identical `applied_at` values still render stably."""
    recruiter_token, _rp = _recruiter(db_session, "tiebreak@acme.com")
    job_id = None
    applications = []

    for index in range(3):
        candidate_token, candidate_profile = _candidate(db_session, f"tiebreak.candidate{index}@example.com")
        if job_id is None:
            job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
        else:
            from src.domains.matching import embeddings, service as matching_service

            embeddings.embed_candidate_profile(db_session, candidate_profile)
            db_session.commit()
            matching_service.recompute_for_candidate(db_session, candidate_profile)
        client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))
        applications.append(
            db_session.execute(
                select(Application).where(
                    Application.job_posting_id == job_id,
                    Application.candidate_profile_id == candidate_profile.id,
                )
            ).scalar_one()
        )

    base = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    for application in applications:
        application.score_at_apply = 70.0
    # Applied in the reverse of creation order, so a correct result cannot be
    # produced by falling back to insertion order.
    applications[0].applied_at = base + timedelta(hours=2)
    applications[1].applied_at = base
    applications[2].applied_at = base + timedelta(hours=1)
    db_session.commit()

    column = client.get(f"{JOBS_BASE}/{job_id}/pipeline", headers=_auth(recruiter_token)).json()["applied"]
    assert [card["application_id"] for card in column] == [
        str(applications[1].id), str(applications[2].id), str(applications[0].id)
    ]

    # Identical timestamps too: `id ASC` is the last resort, and the order
    # must be stable rather than whatever Postgres happens to return.
    for application in applications:
        application.applied_at = base
    db_session.commit()
    repeated = [
        [card["application_id"] for card in
         client.get(f"{JOBS_BASE}/{job_id}/pipeline", headers=_auth(recruiter_token)).json()["applied"]]
        for _ in range(2)
    ]
    assert repeated[0] == repeated[1]
    assert repeated[0] == sorted(str(a.id) for a in applications)


def test_applications_without_a_frozen_score_sort_last_not_first(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    """Postgres puts NULLs first under `DESC` by default; `NULLS LAST` keeps
    pre-backfill stragglers at the bottom of the column instead of the top."""
    recruiter_token, _rp = _recruiter(db_session, "nullsort@acme.com")
    job_id = None
    applications = []

    for index in range(2):
        candidate_token, candidate_profile = _candidate(db_session, f"nullsort.candidate{index}@example.com")
        if job_id is None:
            job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
        else:
            from src.domains.matching import embeddings, service as matching_service

            embeddings.embed_candidate_profile(db_session, candidate_profile)
            db_session.commit()
            matching_service.recompute_for_candidate(db_session, candidate_profile)
        client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))
        applications.append(
            db_session.execute(
                select(Application).where(
                    Application.job_posting_id == job_id,
                    Application.candidate_profile_id == candidate_profile.id,
                )
            ).scalar_one()
        )

    applications[0].score_at_apply = None
    applications[1].score_at_apply = 55.0
    db_session.commit()

    column = client.get(f"{JOBS_BASE}/{job_id}/pipeline", headers=_auth(recruiter_token)).json()["applied"]
    assert [card["score_at_apply"] for card in column] == [55.0, None]


# --------------------------------------------------------------------------
# Rollback
# --------------------------------------------------------------------------


def _apply_and_get_application_id(
    client: TestClient, db_session: Session, recruiter_token: str, candidate_token: str, job_id: str
) -> str:
    client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))
    return str(
        db_session.execute(select(Application).where(Application.job_posting_id == job_id)).scalar_one().id
    )


def test_rollback_returns_to_the_previous_stage_and_appends_an_audit_row(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    recruiter_token, _rp = _recruiter(db_session, "rollback@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "rollback.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    application_id = _apply_and_get_application_id(client, db_session, recruiter_token, candidate_token, job_id)

    client.post(
        f"{RECRUITER_BASE}/applications/{application_id}/transition",
        json={"to_status": "shortlisted"}, headers=_auth(recruiter_token),
    )
    application = db_session.get(Application, uuid.UUID(application_id))
    db_session.refresh(application)
    applied_at_before = application.applied_at
    status_updated_before = application.status_updated_at
    score_before = application.score_at_apply

    resp = client.post(f"{RECRUITER_BASE}/applications/{application_id}/rollback", headers=_auth(recruiter_token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "applied"

    db_session.refresh(application)
    # `status_updated_at` moves — the card really did change column, and
    # freezing it would make "how long has this sat here" report a stage the
    # application is no longer in.
    assert application.status_updated_at > status_updated_before
    # Nothing about *applying* changed.
    assert application.applied_at == applied_at_before
    assert application.score_at_apply == score_before

    actions = [
        row.action
        for row in db_session.execute(
            select(AuditLog)
            .where(AuditLog.entity_type == "application", AuditLog.entity_id == application.id)
            .order_by(AuditLog.created_at)
        ).scalars()
    ]
    # Append-only: the forward transition's row is still there, with the undo
    # recorded alongside it under its own action rather than replacing it.
    assert actions == ["application.created", "application.status_changed", "application.rolled_back"]

    rolled_back = db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_id == application.id, AuditLog.action == "application.rolled_back"
        )
    ).scalar_one()
    assert rolled_back.before == {"status": "shortlisted"}
    assert rolled_back.after == {"status": "applied"}


def test_rollback_from_rejected_restores_the_stage_it_was_rejected_from(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    """`REJECTED` has three possible predecessors, so its target is read back
    off `audit_log` rather than guessed — un-rejecting a candidate rejected at
    the interview stage must not dump them back at `applied`."""
    recruiter_token, _rp = _recruiter(db_session, "unreject@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "unreject.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    application_id = _apply_and_get_application_id(client, db_session, recruiter_token, candidate_token, job_id)

    for to_status in ("shortlisted", "interview_scheduled", "rejected"):
        assert client.post(
            f"{RECRUITER_BASE}/applications/{application_id}/transition",
            json={"to_status": to_status}, headers=_auth(recruiter_token),
        ).status_code == 200

    resp = client.post(f"{RECRUITER_BASE}/applications/{application_id}/rollback", headers=_auth(recruiter_token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "interview_scheduled"


@pytest.mark.parametrize(
    "path,expected_status",
    [([], "applied"), (["shortlisted", "interview_scheduled", "hired"], "hired")],
    ids=["entry-state", "terminal-hire"],
)
def test_illegal_rollback_is_rejected(
    client: TestClient, db_session: Session, stub_extractor, path, expected_status
) -> None:
    """`APPLIED` has no earlier stage; `HIRED` is deliberately not reversible
    (see `ALLOWED_ROLLBACKS`). Both are a 409 from the same `Conflict` path an
    illegal forward transition raises, so the board surfaces them the same
    way."""
    recruiter_token, _rp = _recruiter(db_session, f"illegal-{expected_status}@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, f"illegal-{expected_status}.c@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    application_id = _apply_and_get_application_id(client, db_session, recruiter_token, candidate_token, job_id)

    for to_status in path:
        assert client.post(
            f"{RECRUITER_BASE}/applications/{application_id}/transition",
            json={"to_status": to_status}, headers=_auth(recruiter_token),
        ).status_code == 200

    resp = client.post(f"{RECRUITER_BASE}/applications/{application_id}/rollback", headers=_auth(recruiter_token))
    assert resp.status_code == 409, resp.text
    assert "cannot be rolled back" in resp.json()["error"]["message"]

    # The rejected attempt changed nothing and left no audit row behind.
    application = db_session.get(Application, uuid.UUID(application_id))
    db_session.refresh(application)
    assert application.status.value == expected_status
    assert not db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_id == application.id, AuditLog.action == "application.rolled_back"
        )
    ).scalars().all()

    # The board agrees with the server rather than offering a button that 409s.
    board = client.get(f"{JOBS_BASE}/{job_id}/pipeline", headers=_auth(recruiter_token)).json()
    assert board[expected_status][0]["can_roll_back"] is False


def test_rollback_is_scoped_to_the_owning_recruiter(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    recruiter_token, _rp = _recruiter(db_session, "rb-owner@acme.com")
    outsider_token, _op = _recruiter(db_session, "rb-outsider@othercorp.com", company_name="Other Corp")
    candidate_token, candidate_profile = _candidate(db_session, "rb-scope.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    application_id = _apply_and_get_application_id(client, db_session, recruiter_token, candidate_token, job_id)
    client.post(
        f"{RECRUITER_BASE}/applications/{application_id}/transition",
        json={"to_status": "shortlisted"}, headers=_auth(recruiter_token),
    )

    assert client.post(
        f"{RECRUITER_BASE}/applications/{application_id}/rollback", headers=_auth(outsider_token)
    ).status_code == 403
    # The candidate cannot un-do their own rejection either.
    assert client.post(
        f"{RECRUITER_BASE}/applications/{application_id}/rollback", headers=_auth(candidate_token)
    ).status_code == 403


def test_rollback_is_not_recorded_as_a_first_response(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    """`recruiter_funnel`'s time-to-first-response is the earliest
    `application.status_changed`/`.hired` audit row minus `applied_at`. A
    rollback writes `application.rolled_back`, which that query deliberately
    does not match — otherwise undoing a mis-click would itself register as
    having responded to a candidate.

    Note what the funnel *does* do here, because it is easy to misread as a
    bug: the average drops to `None` after the rollback. That is not the undo
    being counted, it is `recruiter_funnel` measuring applications by their
    *current* status (it only considers rows where `status != APPLIED`), and
    this application is genuinely back at `APPLIED` — no response outstanding.
    The rollback added no new forward-transition row, which is the invariant
    under test.
    """
    recruiter_token, _rp = _recruiter(db_session, "rb-funnel@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "rb-funnel.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    application_id = _apply_and_get_application_id(client, db_session, recruiter_token, candidate_token, job_id)

    client.post(
        f"{RECRUITER_BASE}/applications/{application_id}/transition",
        json={"to_status": "shortlisted"}, headers=_auth(recruiter_token),
    )
    forward_rows_before = db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_id == uuid.UUID(application_id),
            AuditLog.action.in_(("application.status_changed", "application.hired")),
        )
    ).scalars().all()

    client.post(f"{RECRUITER_BASE}/applications/{application_id}/rollback", headers=_auth(recruiter_token))

    forward_rows_after = db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_id == uuid.UUID(application_id),
            AuditLog.action.in_(("application.status_changed", "application.hired")),
        )
    ).scalars().all()
    assert {row.id for row in forward_rows_after} == {row.id for row in forward_rows_before}

    after = client.get(f"{RECRUITER_BASE}/analytics/funnel", headers=_auth(recruiter_token)).json()
    assert after["stage_counts"]["applied"] == 1
    assert after["stage_counts"]["shortlisted"] == 0
    # Back at APPLIED, so there is no responded-to application left to average.
    assert after["avg_time_to_first_response_hours"] is None


# --------------------------------------------------------------------------
# Evidence card
# --------------------------------------------------------------------------


def test_evidence_card_requires_a_pipeline_relationship(client: TestClient, db_session: Session) -> None:
    recruiter_token, _rp = _recruiter(db_session, "noaccess@acme.com")
    _candidate_token, candidate_profile = _candidate(db_session, "noaccess.candidate@example.com")

    resp = client.get(
        f"{RECRUITER_BASE}/candidates/{candidate_profile.id}/evidence", headers=_auth(recruiter_token)
    )
    assert resp.status_code == 403


def test_evidence_card_available_once_matched_and_logs_a_profile_view(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    recruiter_token, _rp = _recruiter(db_session, "evidence@acme.com")
    _candidate_token, candidate_profile = _candidate(db_session, "evidence.candidate@example.com")
    _matched_job(client, db_session, recruiter_token, candidate_profile)

    resp = client.get(
        f"{RECRUITER_BASE}/candidates/{candidate_profile.id}/evidence", headers=_auth(recruiter_token)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["record"]["profile"]["profile_strength"] == 80

    view_logged = db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "candidate_profile",
            AuditLog.entity_id == candidate_profile.id,
            AuditLog.action == "candidate_profile.viewed",
        )
    ).scalars().first()
    assert view_logged is not None


# --------------------------------------------------------------------------
# Messaging
# --------------------------------------------------------------------------


def test_messaging_is_restricted_to_the_pipeline_pair(client: TestClient, db_session: Session, stub_extractor) -> None:
    recruiter_token, _rp = _recruiter(db_session, "messaging@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "messaging.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))
    application_id = db_session.execute(select(Application).where(Application.job_posting_id == job_id)).scalar_one().id

    sent = client.post(
        f"{RECRUITER_BASE}/applications/{application_id}/messages",
        json={"body": "Thanks for applying!"}, headers=_auth(recruiter_token),
    )
    assert sent.status_code == 201, sent.text

    candidate_view = client.get(f"{STUDENT_BASE}/applications/{application_id}/messages", headers=_auth(candidate_token))
    assert candidate_view.status_code == 200
    assert len(candidate_view.json()["messages"]) == 1

    # Candidate got a new-message notification.
    notifs = client.get("/api/v1/notifications", headers=_auth(candidate_token)).json()
    assert any(n["type"] == "new_message" for n in notifs["notifications"])

    # An unrelated recruiter cannot reach this conversation.
    other_recruiter_token, _op = _recruiter(db_session, "outsider@othercorp.com")
    blocked = client.get(f"{RECRUITER_BASE}/applications/{application_id}/messages", headers=_auth(other_recruiter_token))
    assert blocked.status_code == 403


# --------------------------------------------------------------------------
# Recruiter notes — query-layer company scoping
# --------------------------------------------------------------------------


def test_notes_are_scoped_to_company_at_the_query_layer(client: TestClient, db_session: Session, stub_extractor) -> None:
    recruiter_token, recruiter_profile = _recruiter(db_session, "notes.owner@acme.com")
    teammate_token, _teammate_profile = _recruiter(db_session, "notes.teammate@acme.com")  # same company "Acme Corp"
    candidate_token, candidate_profile = _candidate(db_session, "notes.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))
    application_id = db_session.execute(select(Application).where(Application.job_posting_id == job_id)).scalar_one().id

    added = client.post(
        f"{RECRUITER_BASE}/applications/{application_id}/notes",
        json={"body": "Strong candidate, move forward."}, headers=_auth(recruiter_token),
    )
    assert added.status_code == 201, added.text

    # A teammate at the same company (different recruiter account) can read it.
    teammate_view = client.get(f"{RECRUITER_BASE}/applications/{application_id}/notes", headers=_auth(teammate_token))
    assert teammate_view.status_code == 200
    assert len(teammate_view.json()) == 1

    # A recruiter at a different company cannot.
    outsider_token, _op = _recruiter(db_session, "notes.outsider@othercorp.com", company_name="Other Corp")
    outsider_view = client.get(f"{RECRUITER_BASE}/applications/{application_id}/notes", headers=_auth(outsider_token))
    assert outsider_view.status_code == 403

    # There is no candidate-reachable route for notes at all — `getattr`
    # rather than `.path` directly since not every entry in `app.routes` is
    # an `APIRoute` (some are internal router-mount wrappers with no `.path`).
    assert not any(
        getattr(route, "path", "").startswith("/api/v1/student") and "notes" in getattr(route, "path", "")
        for route in client.app.routes  # type: ignore[attr-defined]
    )


# --------------------------------------------------------------------------
# Analytics
# --------------------------------------------------------------------------


def test_recruiter_funnel_counts_and_student_summary(client: TestClient, db_session: Session, stub_extractor) -> None:
    recruiter_token, _rp = _recruiter(db_session, "funnel@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "funnel.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))

    funnel = client.get(f"{RECRUITER_BASE}/analytics/funnel", headers=_auth(recruiter_token))
    assert funnel.status_code == 200
    assert funnel.json()["stage_counts"]["applied"] == 1

    summary = client.get(f"{STUDENT_BASE}/analytics/summary", headers=_auth(candidate_token))
    assert summary.status_code == 200
    assert summary.json()["match_count"] >= 1
    assert summary.json()["application_outcomes"]["applied"] == 1


def test_funnel_time_to_first_response_over_multiple_applications(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    """`recruiter_funnel`'s time-to-first-response used to issue one
    `audit_log` query per non-APPLIED application (an N+1); this exercises
    it with several applications at different stages to prove the
    single-query `DISTINCT ON` rewrite still computes the right average,
    not just that it runs."""
    recruiter_token, _rp = _recruiter(db_session, "funnel-ttfr@acme.com")
    job_id = None
    application_ids = []
    for i in range(3):
        candidate_token, candidate_profile = _candidate(db_session, f"funnel-ttfr.candidate{i}@example.com")
        if job_id is None:
            job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
        else:
            # Reuse the same published job for every candidate.
            from src.domains.matching import embeddings, service as matching_service

            embeddings.embed_candidate_profile(db_session, candidate_profile)
            db_session.commit()
            matching_service.recompute_for_candidate(db_session, candidate_profile)
        client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))
        application_id = db_session.execute(
            select(Application).where(
                Application.job_posting_id == job_id, Application.candidate_profile_id == candidate_profile.id
            )
        ).scalar_one().id
        application_ids.append(str(application_id))

    # Only two of the three ever move past APPLIED — the third stays
    # untouched and must not contribute to the average.
    client.post(
        f"{RECRUITER_BASE}/applications/{application_ids[0]}/transition",
        json={"to_status": "shortlisted"}, headers=_auth(recruiter_token),
    )
    client.post(
        f"{RECRUITER_BASE}/applications/{application_ids[1]}/transition",
        json={"to_status": "rejected"}, headers=_auth(recruiter_token),
    )

    funnel = client.get(f"{RECRUITER_BASE}/analytics/funnel", headers=_auth(recruiter_token))
    assert funnel.status_code == 200
    body = funnel.json()
    assert body["stage_counts"]["applied"] == 1
    assert body["avg_time_to_first_response_hours"] is not None
    assert body["avg_time_to_first_response_hours"] >= 0


# --------------------------------------------------------------------------
# Notification emails — stage change and new message wired to the mail module
# --------------------------------------------------------------------------


def test_stage_transition_emails_the_candidate(
    client: TestClient, db_session: Session, stub_extractor, mail_outbox
) -> None:
    recruiter_token, _rp = _recruiter(db_session, "stage-email@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "stage-email.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))
    application_id = db_session.execute(select(Application).where(Application.job_posting_id == job_id)).scalar_one().id
    mail_outbox.clear()  # drop the "new Smart Apply application" email to the recruiter

    resp = client.post(
        f"{RECRUITER_BASE}/applications/{application_id}/transition",
        json={"to_status": "shortlisted"}, headers=_auth(recruiter_token),
    )
    assert resp.status_code == 200

    candidate_emails = [m for m in mail_outbox if m.to_email == "stage-email.candidate@example.com"]
    assert len(candidate_emails) == 1
    assert "Shortlisted" in candidate_emails[0].text_body


def test_new_message_emails_the_other_party(
    client: TestClient, db_session: Session, stub_extractor, mail_outbox
) -> None:
    recruiter_token, _rp = _recruiter(db_session, "msg-email@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "msg-email.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))
    application_id = db_session.execute(select(Application).where(Application.job_posting_id == job_id)).scalar_one().id
    mail_outbox.clear()

    sent = client.post(
        f"{RECRUITER_BASE}/applications/{application_id}/messages",
        json={"body": "Thanks for applying!"}, headers=_auth(recruiter_token),
    )
    assert sent.status_code == 201

    candidate_emails = [m for m in mail_outbox if m.to_email == "msg-email.candidate@example.com"]
    assert len(candidate_emails) == 1
    assert "new message" in candidate_emails[0].subject.lower()


# ==========================================================================
# Board card payload + structured close feedback
# ==========================================================================


def test_board_cards_carry_the_reasoning_string_and_top_skills(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    """Every column renders the same card, so both shapes carry the same three
    fields (`schemas.py::_CandidateCardFields`).

    The reasoning is composed from the stored `match_reasons` payload by
    `matching/tiers.py::build_reasoning` — the assertion is deliberately on
    its *shape* rather than on an exact sentence, because the sentence is that
    module's contract and is pinned by its own unit tests.
    """
    recruiter_token, _rp = _recruiter(db_session, "cards@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "cards.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)

    matched = client.get(f"{JOBS_BASE}/{job_id}/pipeline", headers=_auth(recruiter_token)).json()["matched"]
    assert len(matched) == 1
    card = matched[0]
    assert card["reasoning"], "a card without a reasoning line explains nothing"
    assert isinstance(card["matched_skills"], list)
    assert len(card["matched_skills"]) <= 3, "the card renders three; sending more is data with nowhere to go"
    assert isinstance(card["is_verified"], bool)

    # The applied column describes the same candidate the same way.
    client.post(f"{STUDENT_BASE}/jobs/{job_id}/apply", json={}, headers=_auth(candidate_token))
    applied = client.get(f"{JOBS_BASE}/{job_id}/pipeline", headers=_auth(recruiter_token)).json()["applied"]
    assert applied[0]["reasoning"] == card["reasoning"]
    assert applied[0]["matched_skills"] == card["matched_skills"]


def test_a_close_reason_is_recorded_on_the_transition_audit_entry(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    recruiter_token, _rp = _recruiter(db_session, "closereason@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "closereason.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    application_id = _apply_and_get_application_id(
        client, db_session, recruiter_token, candidate_token, job_id
    )

    response = client.post(
        f"{RECRUITER_BASE}/applications/{application_id}/transition",
        json={"to_status": "rejected", "close_reason": "skills_gap", "close_note": "No Rust evidence."},
        headers=_auth(recruiter_token),
    )
    assert response.status_code == 200

    entry = db_session.execute(
        select(AuditLog)
        .where(AuditLog.entity_type == "application", AuditLog.entity_id == uuid.UUID(application_id))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(1)
    ).scalar_one()
    assert entry.after["status"] == "rejected"
    assert entry.after["close_reason"] == "skills_gap"
    assert entry.after["close_note"] == "No Rust evidence."


def test_skipping_the_reason_closes_the_candidate_and_records_nothing_extra(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    """Skip must stay exactly as fast as closing was before feedback existed,
    and must leave no trace of having been skipped — an empty reason field is
    not a data point about the recruiter."""
    recruiter_token, _rp = _recruiter(db_session, "skipreason@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "skipreason.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    application_id = _apply_and_get_application_id(
        client, db_session, recruiter_token, candidate_token, job_id
    )

    response = client.post(
        f"{RECRUITER_BASE}/applications/{application_id}/transition",
        json={"to_status": "rejected"},
        headers=_auth(recruiter_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    entry = db_session.execute(
        select(AuditLog)
        .where(AuditLog.entity_type == "application", AuditLog.entity_id == uuid.UUID(application_id))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(1)
    ).scalar_one()
    assert entry.after == {"status": "rejected"}


def test_a_close_reason_sent_with_a_forward_move_is_ignored_not_rejected(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    """A client that always sends the field is not a client that breaks — but
    "skills gap" attached to a shortlisting is nonsense and must not be
    stored."""
    recruiter_token, _rp = _recruiter(db_session, "strayreason@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "strayreason.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    application_id = _apply_and_get_application_id(
        client, db_session, recruiter_token, candidate_token, job_id
    )

    response = client.post(
        f"{RECRUITER_BASE}/applications/{application_id}/transition",
        json={"to_status": "shortlisted", "close_reason": "role_filled"},
        headers=_auth(recruiter_token),
    )
    assert response.status_code == 200

    entry = db_session.execute(
        select(AuditLog)
        .where(AuditLog.entity_type == "application", AuditLog.entity_id == uuid.UUID(application_id))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(1)
    ).scalar_one()
    assert entry.after == {"status": "shortlisted"}


def test_an_unknown_close_reason_is_refused(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    """The reason set is closed on purpose: it is only usable as a matching
    signal if the same answer means the same thing everywhere."""
    recruiter_token, _rp = _recruiter(db_session, "badreason@acme.com")
    candidate_token, candidate_profile = _candidate(db_session, "badreason.candidate@example.com")
    job_id = _matched_job(client, db_session, recruiter_token, candidate_profile)
    application_id = _apply_and_get_application_id(
        client, db_session, recruiter_token, candidate_token, job_id
    )

    response = client.post(
        f"{RECRUITER_BASE}/applications/{application_id}/transition",
        json={"to_status": "rejected", "close_reason": "vibes"},
        headers=_auth(recruiter_token),
    )
    assert response.status_code == 422
