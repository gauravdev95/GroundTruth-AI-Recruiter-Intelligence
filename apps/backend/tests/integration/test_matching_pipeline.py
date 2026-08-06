"""Integration tests for the matching engine
(`domains/matching/service.py`, `jobs/tasks/matching.py`).

The embedder is stubbed to return a fixed vector (`embed(text) -> FIXED_VECTOR`
regardless of input) — this is not a test of the embedding model or of
semantic quality, and stubbing it also keeps the suite from loading several
hundred megabytes of weights. It's a test of the pipeline: pre-filter ->
pgvector similarity -> rank
fusion -> threshold -> top-K -> persisted once, read identically from both
the recruiter and student endpoints. Candidate discoverability/skills are
set up directly via the ORM rather than through the full section-save and
verification flow (those are covered in `test_student_profile.py` and
`test_verification_tasks.py`); this file is scoped to matching itself.

Requires a real Postgres with the `pgvector` extension and this branch's
migrations applied — `Embedding.vector.cosine_distance(...)` compiles to a
Postgres-only SQL operator with no in-memory equivalent to fall back to.
"""

from __future__ import annotations

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
from src.domains.matching.models import MatchResult
from src.domains.recruiter.models import JobPosting
from src.domains.skills.models import CandidateSkill, ProficiencyLevel, Skill
from src.platform.models import AsyncJob

JOBS_BASE = "/api/v1/recruiter/jobs"

VALID_CREATE = {
    "title": "Backend Engineer Intern",
    "description": "Build APIs in Python using FastAPI.",
    "job_type": "internship",
    "experience_level": "entry",
    "location": "Bangalore",
    "is_remote": False,
}
EXTRACTION = JobRequirementExtraction(
    must_have_skills=[ExtractedSkill(name="Python", min_proficiency="intermediate")],
    desirable_skills=[],
    seniority="entry",
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


def _recruiter(db_session: Session, email: str) -> tuple[str, RecruiterProfile]:
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
    profile = db_session.execute(select(RecruiterProfile).where(RecruiterProfile.user_id == user.id)).scalar_one()
    return token, profile


def _discoverable_candidate(db_session: Session, email: str, *, python_evidence_weight: float = 0.8) -> tuple[str, CandidateProfile]:
    """Bypasses the section-save flow — sets exactly what matching reads:
    `is_discoverable`, `profile_strength`, `graduation_year`, and a
    `candidate_skills` row for "Python"."""
    from datetime import datetime, timezone

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

    profile = db_session.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id)).scalar_one()
    profile.is_discoverable = True
    profile.profile_strength = 80
    profile.graduation_year = datetime.now(timezone.utc).year

    skill = db_session.execute(select(Skill).where(Skill.name == "Python")).scalar_one_or_none()
    if skill is None:
        from src.domains.skills.models import SkillCategory

        skill = Skill(name="Python", category=SkillCategory.LANGUAGE)
        db_session.add(skill)
        db_session.flush()

    db_session.add(
        CandidateSkill(
            candidate_profile_id=profile.id,
            skill_id=skill.id,
            proficiency=ProficiencyLevel.ADVANCED,
            evidence_weight=python_evidence_weight,
        )
    )
    db_session.commit()
    return token, profile


def _publish_job(client: TestClient, db_session: Session, recruiter_token: str) -> str:
    from src.jobs.tasks.job_extraction import extract_job_requirements_task

    created = client.post(JOBS_BASE, json=VALID_CREATE, headers=_auth(recruiter_token)).json()
    client.post(f"{JOBS_BASE}/{created['id']}/submit", headers=_auth(recruiter_token))

    async_job = db_session.execute(
        select(AsyncJob).where(AsyncJob.job_type == "extract_job_requirements")
    ).scalars().first()
    extract_job_requirements_task.run(str(async_job.id))

    confirm_payload = {
        "seniority": "entry",
        "skills": [{"skill_name": "Python", "min_proficiency": "intermediate", "is_required": True, "weight": 1.0}],
    }
    client.post(f"{JOBS_BASE}/{created['id']}/confirm", json=confirm_payload, headers=_auth(recruiter_token))
    return created["id"]


def _run_job_matching(db_session: Session, job_id: str) -> None:
    from src.jobs.tasks.matching import embed_and_match_job_task

    async_job = db_session.execute(
        select(AsyncJob).where(AsyncJob.job_type == "embed_and_match_job")
    ).scalars().first()
    embed_and_match_job_task.run(str(async_job.id))


def _embed_candidate(db_session: Session, candidate_profile: CandidateProfile) -> None:
    """Directly calls the embedding step `embed_and_match_candidate_task`
    normally does — a candidate must have an `embeddings` row before either
    `recompute_for_job` (job-side pool search) or `recompute_for_candidate`
    (candidate-side loop) can find them at all."""
    from src.domains.matching import embeddings

    embeddings.embed_candidate_profile(db_session, candidate_profile)
    db_session.commit()


def _make_section_complete(db_session: Session, profile: CandidateProfile) -> None:
    """Fills every mandatory section for real — the seven basic fields, a
    GitHub account, and one project — so `meets_section_requirements` is
    genuinely true rather than being asserted into place.

    The project is not optional decoration. `completeness.py::_score_projects`
    is mandatory (`is_mandatory=True`, one repository required), and without it
    `embed_and_match_candidate_task` returns `skipped_not_eligible` before it
    ever reaches the embedding call — which looks, from the outside, exactly
    like an embedder that silently produced nothing. The coding-platform handle
    is kept because it is what the competency term scores against; it earns
    points but gates nothing.
    """
    from src.domains.auth.models import Branch, DegreeType, TargetRole
    from src.domains.student.models import (
        CodingPlatform,
        CodingPlatformAccount,
        GithubAccount,
        Project,
        ProjectKind,
        VerificationStatus,
    )

    profile.headline = "Backend engineer"
    profile.college = "IIT Bombay"
    profile.degree = DegreeType.BTECH
    profile.branch = Branch.CSE
    profile.location = "Bangalore"
    profile.target_role = TargetRole.BACKEND

    db_session.add(
        GithubAccount(
            candidate_profile_id=profile.id,
            github_username="ada",
            profile_url="https://github.com/ada",
        )
    )
    db_session.add(
        CodingPlatformAccount(
            candidate_profile_id=profile.id,
            platform=CodingPlatform.LEETCODE,
            handle="ada",
            profile_url="https://leetcode.com/ada",
        )
    )
    db_session.add(
        Project(
            candidate_profile_id=profile.id,
            kind=ProjectKind.REPOSITORY,
            title="payments-api",
            repo_url="https://github.com/ada/payments-api",
            technologies=["Python"],
            verification_status=VerificationStatus.VERIFIED,
        )
    )
    db_session.commit()


def test_matched_candidate_appears_on_both_the_recruiter_and_student_side(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    from src.domains.matching import service as matching_service

    recruiter_token, _recruiter_profile = _recruiter(db_session, "matcher@acme.com")
    candidate_token, candidate_profile = _discoverable_candidate(db_session, "match.me@example.com")
    _embed_candidate(db_session, candidate_profile)

    job_id = _publish_job(client, db_session, recruiter_token)
    _run_job_matching(db_session, job_id)

    # The candidate side of the same computation, run directly (mirrors what
    # `verify_*_task`'s `_finish()` enqueues in production).
    matching_service.recompute_for_candidate(db_session, candidate_profile)

    match_row = db_session.execute(
        select(MatchResult).where(
            MatchResult.job_posting_id == job_id, MatchResult.candidate_profile_id == candidate_profile.id
        )
    ).scalar_one_or_none()
    assert match_row is not None
    assert match_row.match_score >= 50.0

    recruiter_view = client.get(f"{JOBS_BASE}/{job_id}/matches", headers=_auth(recruiter_token))
    assert recruiter_view.status_code == 200
    candidate_ids = [c["candidate"]["candidate_profile_id"] for c in recruiter_view.json()["candidates"]]
    assert str(candidate_profile.id) in candidate_ids
    reasons = recruiter_view.json()["candidates"][0]["matched_required_skills"]
    assert reasons[0]["skill_name"] == "Python"
    assert reasons[0]["candidate_has_skill"] is True

    student_view = client.get("/api/v1/student/matches", headers=_auth(candidate_token))
    assert student_view.status_code == 200
    job_ids = [j["job"]["job_id"] for j in student_view.json()["jobs"]]
    assert job_id in job_ids


def test_non_discoverable_candidate_never_enters_the_index(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    from src.domains.matching import service as matching_service

    recruiter_token, _profile = _recruiter(db_session, "gate@acme.com")
    _candidate_token, candidate_profile = _discoverable_candidate(db_session, "hidden@example.com")
    candidate_profile.is_discoverable = False
    db_session.commit()

    job_id = _publish_job(client, db_session, recruiter_token)
    _run_job_matching(db_session, job_id)
    matching_service.recompute_for_candidate(db_session, candidate_profile)

    match_row = db_session.execute(
        select(MatchResult).where(
            MatchResult.job_posting_id == job_id, MatchResult.candidate_profile_id == candidate_profile.id
        )
    ).scalar_one_or_none()
    assert match_row is None


def test_closing_a_job_removes_its_matches(client: TestClient, db_session: Session, stub_extractor) -> None:
    from src.domains.matching import service as matching_service

    recruiter_token, _profile = _recruiter(db_session, "closer@acme.com")
    _candidate_token, candidate_profile = _discoverable_candidate(db_session, "closed.match@example.com")
    _embed_candidate(db_session, candidate_profile)

    job_id = _publish_job(client, db_session, recruiter_token)
    _run_job_matching(db_session, job_id)
    matching_service.recompute_for_candidate(db_session, candidate_profile)

    assert (
        db_session.execute(select(MatchResult).where(MatchResult.job_posting_id == job_id)).scalar_one_or_none()
        is not None
    )

    client.post(f"{JOBS_BASE}/{job_id}/close", headers=_auth(recruiter_token))
    assert (
        db_session.execute(select(MatchResult).where(MatchResult.job_posting_id == job_id)).scalar_one_or_none()
        is None
    )


def test_embedding_worker_is_what_flips_a_profile_to_indexed(
    client: TestClient, db_session: Session
) -> None:
    """B2's gate, end to end: meeting the section requirements makes a profile
    *eligible*, and only the embedding worker makes it *indexed*.

    The stages must stay distinct or the system deadlocks — embedding is
    enqueued for eligible profiles, so if eligibility itself required an
    embedding nothing would ever be indexed. This walks the real sequence:
    eligible-but-unembedded -> worker runs -> indexed.

    It stops at `is_indexed` on purpose. `is_discoverable` is a *third* stage
    that additionally requires a completed AI interview
    (`student/completeness.py`), so it stays False here — this test drives the
    embedding worker, and the interview is a different worker's job. Asserting
    discoverability at the end of an embedding test was true only under the
    two-stage model that predates the split, and it made this test fail for a
    reason that had nothing to do with embedding.
    """
    from src.domains.matching.embeddings import get_embedding
    from src.domains.matching.models import EmbeddableEntityType
    from src.domains.student import service as student_service
    from src.jobs.tasks.matching import embed_and_match_candidate_task

    _token, profile = _discoverable_candidate(db_session, "gated.candidate@example.com")

    # `_discoverable_candidate` sets the flag directly; undo that and fill the
    # profile in for real, so this test observes the actual transition rather
    # than its own fixture's shortcut.
    profile.is_discoverable = False
    _make_section_complete(db_session, profile)

    assert (
        get_embedding(
            db_session,
            entity_type=EmbeddableEntityType.CANDIDATE_PROFILE,
            entity_id=profile.id,
        )
        is None
    )

    async_job = AsyncJob(
        job_type="embed_and_match_candidate",
        payload={"candidate_profile_id": str(profile.id)},
    )
    db_session.add(async_job)
    db_session.commit()

    embed_and_match_candidate_task.run(str(async_job.id))

    db_session.refresh(profile)
    assert (
        get_embedding(
            db_session,
            entity_type=EmbeddableEntityType.CANDIDATE_PROFILE,
            entity_id=profile.id,
        )
        is not None
    )

    completeness = student_service.get_completeness(db_session, profile)
    assert completeness.meets_section_requirements is True
    assert completeness.is_indexed is True, "the embedding worker's actual output"
    # Still gated on the interview, which this worker does not run.
    assert completeness.is_discoverable is False
    assert profile.is_discoverable is False


def test_ineligible_profile_is_not_embedded_and_is_pruned(
    client: TestClient, db_session: Session
) -> None:
    """The eligibility re-check happens at compute time, not just at enqueue
    time: a student can empty a mandatory field between the two."""
    from src.domains.matching.embeddings import get_embedding
    from src.domains.matching.models import EmbeddableEntityType
    from src.jobs.tasks.matching import embed_and_match_candidate_task

    # Deliberately left without a GitHub account or a coding-platform handle,
    # so section 2 is incomplete and the profile is not eligible.
    _token, profile = _discoverable_candidate(db_session, "ineligible.candidate@example.com")
    profile.is_discoverable = False
    db_session.commit()

    async_job = AsyncJob(
        job_type="embed_and_match_candidate",
        payload={"candidate_profile_id": str(profile.id)},
    )
    db_session.add(async_job)
    db_session.commit()

    result = embed_and_match_candidate_task.run(str(async_job.id))

    assert result["status"] == "skipped_not_eligible"
    db_session.refresh(profile)
    assert profile.is_discoverable is False
    assert (
        get_embedding(
            db_session,
            entity_type=EmbeddableEntityType.CANDIDATE_PROFILE,
            entity_id=profile.id,
        )
        is None
    )


def test_recompute_upserts_the_same_row_instead_of_recreating_it(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    """D2: a recompute updates the pair in place. The old delete-then-reinsert
    gave every pair a new identity on every run, which is why nothing could
    safely reference a match row."""
    from src.domains.matching import service as matching_service

    recruiter_token, _ = _recruiter(db_session, "upsert@acme.com")
    _candidate_token, candidate_profile = _discoverable_candidate(db_session, "upsert.me@example.com")
    _embed_candidate(db_session, candidate_profile)

    job_id = _publish_job(client, db_session, recruiter_token)
    _run_job_matching(db_session, job_id)

    first = db_session.execute(
        select(MatchResult).where(MatchResult.job_posting_id == job_id)
    ).scalar_one()
    original_id = first.id
    original_computed_at = first.computed_at

    job = db_session.get(JobPosting, job_id)
    result = matching_service.recompute_for_job(db_session, job)

    rows = db_session.execute(
        select(MatchResult).where(MatchResult.job_posting_id == job_id)
    ).scalars().all()
    assert len(rows) == 1, "the unique pair must not be duplicated by a recompute"
    assert rows[0].id == original_id, "the row is updated, not replaced"
    # `computed_at` is when the pair first matched and must not drift;
    # `updated_at` carries the rescore.
    assert rows[0].computed_at == original_computed_at
    assert rows[0].updated_at >= original_computed_at
    # Second run: the pair already existed, so it is not "newly matched" and
    # must not produce another notification.
    assert result.newly_matched == ()


def test_a_pair_backing_an_application_survives_a_recompute_that_would_drop_it(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    """D3, the data-loss bug: a candidate re-verifying used to be deleted from
    every recruiter board they were on — including boards where they had
    already applied, whose provenance went with them."""
    from src.domains.matching import service as matching_service
    from src.domains.pipeline.models import Application, ApplicationStatus

    recruiter_token, _ = _recruiter(db_session, "protect@acme.com")
    _candidate_token, candidate_profile = _discoverable_candidate(db_session, "protect.me@example.com")
    _embed_candidate(db_session, candidate_profile)

    job_id = _publish_job(client, db_session, recruiter_token)
    _run_job_matching(db_session, job_id)

    match = db_session.execute(
        select(MatchResult).where(MatchResult.job_posting_id == job_id)
    ).scalar_one()
    db_session.add(
        Application(
            job_posting_id=job_id,
            candidate_profile_id=candidate_profile.id,
            status=ApplicationStatus.APPLIED,
            match_id=match.id,
            score_at_apply=match.match_score,
            evidence_snapshot={},
        )
    )
    db_session.commit()

    # The candidate stops being discoverable — the recompute would otherwise
    # clear every one of their rows.
    candidate_profile.is_discoverable = False
    db_session.commit()
    result = matching_service.recompute_for_candidate(db_session, candidate_profile)

    surviving = db_session.execute(
        select(MatchResult).where(MatchResult.candidate_profile_id == candidate_profile.id)
    ).scalars().all()
    assert len(surviving) == 1
    assert surviving[0].id == match.id
    assert result.retained_for_applications == 1
    assert result.removed == 0


def test_removing_a_candidate_from_the_index_still_spares_applied_pairs(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    """The same protection on the direct-removal path, which `close_job` and
    the non-discoverable branch both use."""
    from src.domains.matching import service as matching_service
    from src.domains.pipeline.models import Application, ApplicationStatus

    recruiter_token, _ = _recruiter(db_session, "prune@acme.com")
    _candidate_token, candidate_profile = _discoverable_candidate(db_session, "prune.me@example.com")
    _embed_candidate(db_session, candidate_profile)

    job_id = _publish_job(client, db_session, recruiter_token)
    _run_job_matching(db_session, job_id)
    match = db_session.execute(
        select(MatchResult).where(MatchResult.job_posting_id == job_id)
    ).scalar_one()

    db_session.add(
        Application(
            job_posting_id=job_id,
            candidate_profile_id=candidate_profile.id,
            status=ApplicationStatus.APPLIED,
            match_id=match.id,
            score_at_apply=match.match_score,
            evidence_snapshot={},
        )
    )
    db_session.commit()

    removed = matching_service.remove_matches_for_candidate(db_session, candidate_profile.id)

    assert removed == 0
    assert (
        db_session.execute(
            select(MatchResult).where(MatchResult.candidate_profile_id == candidate_profile.id)
        ).scalar_one_or_none()
        is not None
    )


def test_a_job_past_its_deadline_matches_nobody(
    client: TestClient, db_session: Session, stub_extractor
) -> None:
    """D4: a closed application window is a hard constraint, applied at
    compute time — leaving the rows in place would keep offering students a
    job they can no longer apply to."""
    from datetime import date, timedelta

    from src.domains.matching import service as matching_service

    recruiter_token, _ = _recruiter(db_session, "expired@acme.com")
    _candidate_token, candidate_profile = _discoverable_candidate(db_session, "too.late@example.com")
    _embed_candidate(db_session, candidate_profile)

    job_id = _publish_job(client, db_session, recruiter_token)
    _run_job_matching(db_session, job_id)
    assert (
        db_session.execute(
            select(MatchResult).where(MatchResult.job_posting_id == job_id)
        ).scalar_one_or_none()
        is not None
    ), "sanity: the pair matches while the job is open"

    job = db_session.get(JobPosting, job_id)
    job.deadline = date.today() - timedelta(days=1)
    db_session.commit()

    result = matching_service.recompute_for_job(db_session, job)

    assert result.total == 0
    assert result.removed == 1
    assert (
        db_session.execute(
            select(MatchResult).where(MatchResult.job_posting_id == job_id)
        ).scalar_one_or_none()
        is None
    )


def _always_tier_b(monkeypatch) -> None:
    """Drops Tier B's absolute floor to zero for the duration of a test.

    Tier B (`domains/matching/tiers.py`) is what decides whether a new match
    interrupts a student, and it is deliberately hard to clear. That gate is
    orthogonal to the tests below, whose subject is the *delivery contract* —
    write the row, commit, then push, once per newly matched pair. Neutralising
    it here keeps those tests about the thing they are named after; the gate
    itself is covered by `test_only_tier_b_matches_interrupt_the_student`.
    """
    monkeypatch.setattr("src.domains.matching.tiers.TIER_B_MIN_SCORE", 0.0)


def test_only_tier_b_matches_interrupt_the_student(
    client: TestClient, db_session: Session, stub_extractor, monkeypatch
) -> None:
    """A Tier A pair is discoverable — it sits on the recruiter's board and in
    the student's feed — but it does not push and does not email.

    The threshold is asserted from both sides with the *same* pair, by moving
    the floor rather than by contriving two candidates with different scores:
    that keeps the only variable the one under test.
    """
    from src.domains.matching.models import MatchResult
    from src.domains.pipeline.models import Notification, NotificationType

    def _notification_count() -> int:
        return len(
            db_session.execute(
                select(Notification).where(
                    Notification.user_id == candidate_profile.user_id,
                    Notification.type == NotificationType.NEW_MATCH,
                )
            ).scalars().all()
        )

    recruiter_token, _ = _recruiter(db_session, "tiers@acme.com")
    _candidate_token, candidate_profile = _discoverable_candidate(db_session, "tiered.me@example.com")
    _embed_candidate(db_session, candidate_profile)

    # Floor above anything achievable: the pair matches, and says nothing.
    monkeypatch.setattr("src.domains.matching.tiers.TIER_B_MIN_SCORE", 101.0)
    job_id = _publish_job(client, db_session, recruiter_token)
    _run_job_matching(db_session, job_id)

    assert db_session.execute(
        select(MatchResult).where(MatchResult.job_posting_id == job_id)
    ).scalar_one_or_none() is not None, "the pair is discoverable — it is on the recruiter's board"
    assert _notification_count() == 0, "Tier A must not interrupt the student"

    # The pair is no longer *new* on the next run, so clearing the floor alone
    # cannot produce a notification — which is the correct interaction between
    # the two rules, and worth pinning: a threshold change is not news either.
    monkeypatch.setattr("src.domains.matching.tiers.TIER_B_MIN_SCORE", 0.0)
    _run_job_matching(db_session, job_id)
    assert _notification_count() == 0


def test_worker_notifies_only_newly_matched_students(
    client: TestClient, db_session: Session, stub_extractor, monkeypatch
) -> None:
    """D7: one `NEW_MATCH` notification per newly matched candidate, written
    when the worker finishes — and none for a rescore of a pair the student
    has already been told about."""
    from src.domains.pipeline.models import Notification, NotificationType

    _always_tier_b(monkeypatch)

    recruiter_token, _ = _recruiter(db_session, "notifier@acme.com")
    _candidate_token, candidate_profile = _discoverable_candidate(db_session, "notify.me@example.com")
    _embed_candidate(db_session, candidate_profile)

    job_id = _publish_job(client, db_session, recruiter_token)
    _run_job_matching(db_session, job_id)

    notifications = db_session.execute(
        select(Notification).where(
            Notification.user_id == candidate_profile.user_id,
            Notification.type == NotificationType.NEW_MATCH,
        )
    ).scalars().all()
    assert len(notifications) == 1
    payload = notifications[0].payload
    assert payload["job_title"] == VALID_CREATE["title"]
    assert payload["message"] == f"New match — {VALID_CREATE['title']}, {payload['score']}%"

    # Re-running the worker rescores the same pair. It is not new, so it must
    # not produce a second notification.
    _run_job_matching(db_session, job_id)

    assert (
        len(
            db_session.execute(
                select(Notification).where(
                    Notification.user_id == candidate_profile.user_id,
                    Notification.type == NotificationType.NEW_MATCH,
                )
            ).scalars().all()
        )
        == 1
    )


def test_new_matches_are_pushed_over_the_socket_after_the_rows_commit(
    client: TestClient, db_session: Session, stub_extractor, monkeypatch
) -> None:
    """F1's wiring: `notify_new_matches` returns the `(user_id, payload)`
    pairs it persisted, and the worker emits exactly those.

    Two things are asserted, and the second is the one that matters:

    1. The pushed payload is byte-for-byte the payload that was written to
       `notifications`, not a second rendering of the same facts — the socket
       and the inbox can never describe different matches.
    2. The push happens *after* the commit. The row is the durable record and
       the push is a latency optimisation, so pushing first would risk telling
       a student about a match that then rolled back and which they could
       never find again.
    """
    from src.domains.pipeline.models import Notification, NotificationType

    _always_tier_b(monkeypatch)

    published: list[tuple] = []
    committed_rows_at_publish: list[int] = []

    def _capture(events, *, type_):
        published.extend((user_id, payload, type_) for user_id, payload in events)
        # Read through a *separate* connection-level count so this observes
        # what is actually committed, not what is pending in the session.
        committed_rows_at_publish.append(
            db_session.execute(
                select(Notification).where(Notification.type == NotificationType.NEW_MATCH)
            ).scalars().all().__len__()
        )
        return len(events)

    monkeypatch.setattr("src.jobs.tasks.matching.realtime.publish_many", _capture)

    recruiter_token, _ = _recruiter(db_session, "socketpush@acme.com")
    _candidate_token, candidate_profile = _discoverable_candidate(db_session, "socketpush.me@example.com")
    _embed_candidate(db_session, candidate_profile)

    job_id = _publish_job(client, db_session, recruiter_token)
    _run_job_matching(db_session, job_id)

    assert len(published) == 1
    user_id, payload, type_ = published[0]
    assert user_id == candidate_profile.user_id
    assert type_ is NotificationType.NEW_MATCH

    stored = db_session.execute(
        select(Notification).where(
            Notification.user_id == candidate_profile.user_id,
            Notification.type == NotificationType.NEW_MATCH,
        )
    ).scalar_one()
    assert payload == stored.payload

    # The row existed by the time the push was attempted.
    assert committed_rows_at_publish == [1]


def test_a_dead_socket_bus_never_breaks_the_matching_run(
    client: TestClient, db_session: Session, stub_extractor, monkeypatch
) -> None:
    """`publish_to_user` swallows Redis errors by design, but the worker must
    not depend on that being the only failure mode — a live push is
    best-effort and must never be able to fail a computation whose results
    are already committed."""
    from src.domains.pipeline.models import Notification, NotificationType

    _always_tier_b(monkeypatch)
    monkeypatch.setattr(
        "src.jobs.tasks.matching.realtime.publish_many",
        lambda events, *, type_: (_ for _ in ()).throw(RuntimeError("redis is gone")),
    )

    recruiter_token, _ = _recruiter(db_session, "deadbus@acme.com")
    _candidate_token, candidate_profile = _discoverable_candidate(db_session, "deadbus.me@example.com")
    _embed_candidate(db_session, candidate_profile)
    job_id = _publish_job(client, db_session, recruiter_token)

    with pytest.raises(RuntimeError):
        _run_job_matching(db_session, job_id)

    # The point: the match rows and the notification row survived the failed
    # push, because both were committed before it was attempted.
    assert db_session.execute(
        select(MatchResult).where(MatchResult.job_posting_id == job_id)
    ).scalars().all()
    assert db_session.execute(
        select(Notification).where(
            Notification.user_id == candidate_profile.user_id,
            Notification.type == NotificationType.NEW_MATCH,
        )
    ).scalar_one() is not None
