"""Integration tests for the verification consumers
(`src/jobs/tasks/verification.py`) — the module that was missing entirely
before this change, per `PROGRESS.md` §2.1.

Every third-party client (`domains/verification/clients/*`) is monkeypatched;
nothing here makes a real network call. The point of these tests is the
*consumer* behavior: a claim that started `PENDING` reaches a terminal
`VerificationStatus`, `verification_score`/`verification_source`/
`verification_payload` are written, `candidate_skills` gets populated from a
verified repository's detected technologies, and `profile_strength` is
recomputed — not whether GitHub's or Codeforces' API is reachable.

Tasks are invoked directly (`.run(...)`), the same pattern
`test_resume_import.py` uses, with `SessionLocal` monkeypatched to the test's
own rolled-back session so status writes are visible to assertions without a
second, uncommitted session shadowing them.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domains.auth import service as auth_service
from src.domains.auth.models import CandidateProfile
from src.domains.auth.schemas import CandidateRegisterRequest
from src.domains.auth.security import create_access_token
from src.domains.skills.models import CandidateSkill, Skill
from src.domains.student.models import (
    Certificate,
    CodingPlatformAccount,
    Experience,
    GithubAccount,
    Project,
    ProjectKind,
    VerificationStatus,
)
from src.domains.verification.clients import codeforces as codeforces_client
from src.domains.verification.clients import github as github_client
from src.domains.verification.clients import reachability
from src.domains.verification.exceptions import ClaimNotFound, VerificationServiceUnavailable
from src.platform.models import AsyncJob, AsyncJobStatus

STUDENT_BASE = "/api/v1/student/profile"


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
    monkeypatch.setattr("src.jobs.tasks.verification.SessionLocal", factory)
    monkeypatch.setattr("src.jobs.celery_app.SessionLocal", factory)


def _candidate(db_session: Session, email: str = "verify.me@example.com") -> tuple[str, CandidateProfile]:
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


def _pending_job(db_session: Session, job_type: str) -> AsyncJob:
    job = db_session.execute(
        select(AsyncJob)
        .where(AsyncJob.job_type == job_type, AsyncJob.status == AsyncJobStatus.PENDING)
        .order_by(AsyncJob.created_at.desc())
    ).scalars().first()
    assert job is not None, f"no pending {job_type} job was queued"
    return job


# --------------------------------------------------------------------------
# GitHub account
# --------------------------------------------------------------------------


def test_verify_github_account_verifies_a_real_user(client: TestClient, db_session: Session, monkeypatch):
    from src.jobs.tasks.verification import verify_github_account_task

    token, _profile = _candidate(db_session)
    resp = client.put(
        f"{STUDENT_BASE}/sections/technical",
        json={"github_username": "ada", "coding_profiles": [{"platform": "codeforces", "handle": "adah"}]},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    job = _pending_job(db_session, "verify_github_account")
    monkeypatch.setattr(
        github_client,
        "get_user",
        lambda username, **kw: {"id": 12345, "login": "ada", "public_repos": 3, "followers": 1, "created_at": "x"},
    )

    verify_github_account_task.run(str(job.id))

    account = db_session.execute(select(GithubAccount).where(GithubAccount.github_username == "ada")).scalar_one()
    assert account.verification_status is VerificationStatus.VERIFIED
    assert account.verification_score == 100.0
    assert account.verification_source == "github_api"
    assert account.github_user_id == 12345
    assert account.verified_at is not None


def test_verify_github_account_rejects_a_nonexistent_user(client: TestClient, db_session: Session, monkeypatch):
    from src.jobs.tasks.verification import verify_github_account_task

    token, _profile = _candidate(db_session, "reject.github@example.com")
    client.put(
        f"{STUDENT_BASE}/sections/technical",
        json={"github_username": "nobody", "coding_profiles": [{"platform": "codeforces", "handle": "h"}]},
        headers=_auth(token),
    )
    job = _pending_job(db_session, "verify_github_account")

    def _not_found(username, **kw):
        raise ClaimNotFound("no such user")

    monkeypatch.setattr(github_client, "get_user", _not_found)
    verify_github_account_task.run(str(job.id))

    account = db_session.execute(
        select(GithubAccount).where(GithubAccount.github_username == "nobody")
    ).scalar_one()
    assert account.verification_status is VerificationStatus.REJECTED
    assert account.verification_score == 0.0


def test_verify_github_account_leaves_claim_unverified_on_exhausted_transient_failure(
    client: TestClient, db_session: Session, monkeypatch
):
    from src.jobs.tasks.verification import verify_github_account_task

    token, _profile = _candidate(db_session, "flaky.github@example.com")
    client.put(
        f"{STUDENT_BASE}/sections/technical",
        json={"github_username": "flaky", "coding_profiles": [{"platform": "codeforces", "handle": "h"}]},
        headers=_auth(token),
    )
    job = _pending_job(db_session, "verify_github_account")

    def _unavailable(username, **kw):
        raise VerificationServiceUnavailable("github is down")

    monkeypatch.setattr(github_client, "get_user", _unavailable)

    # Simulate the last retry via Celery's own request-stack API:
    # `.request.retries == .max_retries` is what `_exhausted()` checks, so
    # this reproduces "the backoff ladder is spent" without sleeping through
    # `JOB_RETRY_BACKOFF_MAX_SECONDS` for real.
    verify_github_account_task.push_request(retries=verify_github_account_task.max_retries)
    try:
        with pytest.raises(VerificationServiceUnavailable):
            verify_github_account_task.run(str(job.id))
    finally:
        verify_github_account_task.pop_request()

    account = db_session.execute(
        select(GithubAccount).where(GithubAccount.github_username == "flaky")
    ).scalar_one()
    assert account.verification_status is VerificationStatus.UNVERIFIED
    assert account.verification_payload["exhausted_retries"] is True


# --------------------------------------------------------------------------
# Repository — the GitHub repository analysis consumer
# --------------------------------------------------------------------------


def _stub_repository_analysis(monkeypatch, *, contribution_share: float, is_fork: bool = False):
    monkeypatch.setattr(
        github_client, "get_repo", lambda owner, repo, **kw: {"fork": is_fork, "default_branch": "main", "language": "Python"}
    )
    total = 100
    mine = int(contribution_share * total)
    monkeypatch.setattr(
        github_client,
        "get_contributor_stats",
        lambda owner, repo, **kw: [
            {"author": {"login": "ada"}, "total": mine},
            {"author": {"login": "other"}, "total": total - mine},
        ],
    )
    monkeypatch.setattr(
        github_client,
        "get_repo_tree",
        lambda owner, repo, branch, **kw: ["requirements.txt", "tests/test_app.py", "app.py", "README.md"],
    )
    monkeypatch.setattr(
        github_client,
        "get_file_content",
        lambda owner, repo, path, **kw: "fastapi==0.115.0\n" if path == "requirements.txt" else None,
    )
    monkeypatch.setattr(
        github_client,
        "get_commit_activity",
        lambda owner, repo, **kw: [{"total": 3}, {"total": 0}, {"total": 2}],
    )


def test_verify_repository_verifies_a_real_contribution_and_writes_skills(
    client: TestClient, db_session: Session, monkeypatch
):
    from src.jobs.tasks.verification import verify_repository_task

    token, profile = _candidate(db_session, "repo.owner@example.com")
    client.put(
        f"{STUDENT_BASE}/sections/technical",
        json={"github_username": "ada", "coding_profiles": [{"platform": "codeforces", "handle": "h"}]},
        headers=_auth(token),
    )
    client.put(
        f"{STUDENT_BASE}/sections/projects",
        json={
            "projects": [
                {"kind": "repository", "title": "My App", "repo_url": "https://github.com/ada/myapp", "technologies": []}
            ]
        },
        headers=_auth(token),
    )
    job = _pending_job(db_session, "verify_repository")
    _stub_repository_analysis(monkeypatch, contribution_share=0.9, is_fork=False)

    verify_repository_task.run(str(job.id))

    project = db_session.execute(
        select(Project).where(Project.candidate_profile_id == profile.id)
    ).scalar_one()
    assert project.verification_status is VerificationStatus.VERIFIED
    assert project.verification_score > 40
    assert project.verification_payload["contribution_share"] == 0.9
    assert "fastapi" in project.verification_payload["detected_technologies"]

    skill = db_session.execute(select(Skill).where(Skill.name == "fastapi")).scalar_one_or_none()
    assert skill is not None
    candidate_skill = db_session.execute(
        select(CandidateSkill).where(
            CandidateSkill.candidate_profile_id == profile.id, CandidateSkill.skill_id == skill.id
        )
    ).scalar_one_or_none()
    assert candidate_skill is not None
    assert candidate_skill.evidence_weight > 0


def test_verify_repository_flags_a_low_contribution_fork(client: TestClient, db_session: Session, monkeypatch):
    from src.jobs.tasks.verification import verify_repository_task

    token, profile = _candidate(db_session, "fork.owner@example.com")
    client.put(
        f"{STUDENT_BASE}/sections/technical",
        json={"github_username": "ada", "coding_profiles": [{"platform": "codeforces", "handle": "h"}]},
        headers=_auth(token),
    )
    client.put(
        f"{STUDENT_BASE}/sections/projects",
        json={
            "projects": [
                {"kind": "repository", "title": "Forked App", "repo_url": "https://github.com/ada/forked", "technologies": []}
            ]
        },
        headers=_auth(token),
    )
    job = _pending_job(db_session, "verify_repository")
    _stub_repository_analysis(monkeypatch, contribution_share=0.05, is_fork=True)

    verify_repository_task.run(str(job.id))

    project = db_session.execute(
        select(Project).where(Project.candidate_profile_id == profile.id)
    ).scalar_one()
    assert project.verification_status is VerificationStatus.FLAGGED


# --------------------------------------------------------------------------
# Repository — the seven-stage pipeline's own bookkeeping
# --------------------------------------------------------------------------


def _stages_by_kind(db_session: Session, project_id):
    from src.domains.student.models import VerificationStage

    return {
        row.stage: row
        for row in db_session.execute(
            select(VerificationStage).where(VerificationStage.project_id == project_id)
        ).scalars()
    }


def _repo_project(client: TestClient, db_session: Session, token: str, repo_url: str) -> Project:
    client.put(
        f"{STUDENT_BASE}/sections/technical",
        json={"github_username": "ada", "coding_profiles": [{"platform": "codeforces", "handle": "h"}]},
        headers=_auth(token),
    )
    client.put(
        f"{STUDENT_BASE}/sections/projects",
        json={
            "projects": [
                {"kind": "repository", "title": "App", "repo_url": repo_url, "technologies": []}
            ]
        },
        headers=_auth(token),
    )
    return db_session.execute(select(Project).where(Project.repo_url == repo_url)).scalar_one()


def test_a_verified_repository_records_all_five_analysis_stages(
    client: TestClient, db_session: Session, monkeypatch
):
    """Every stage persists its own result, in order, and the interview stage
    is left open (PENDING) for a repository that verified."""
    from src.domains.student.models import (
        STAGE_SEQUENCE,
        VerificationStageKind,
        VerificationStageStatus,
    )
    from src.jobs.tasks.verification import verify_repository_task

    token, _profile = _candidate(db_session, "stages.ok@example.com")
    project = _repo_project(client, db_session, token, "https://github.com/ada/staged")
    job = _pending_job(db_session, "verify_repository")
    _stub_repository_analysis(monkeypatch, contribution_share=0.9, is_fork=False)

    verify_repository_task.run(str(job.id))

    rows = _stages_by_kind(db_session, project.id)
    assert len(rows) == 7
    assert [rows[kind].sequence for kind in STAGE_SEQUENCE] == [1, 2, 3, 4, 5, 6, 7]

    for kind in STAGE_SEQUENCE[:5]:
        assert rows[kind].status is VerificationStageStatus.SUCCEEDED, kind
        assert rows[kind].result is not None, kind
        assert rows[kind].completed_at is not None, kind

    # Each stage's result is its own, not a copy of the composite blob.
    assert rows[VerificationStageKind.FORK_AUTHORSHIP_CHECK].result["passed"] is True
    assert rows[VerificationStageKind.CONTRIBUTION_ANALYSIS].result["active_weeks"] == 2
    assert rows[VerificationStageKind.ARCHITECTURE_CODE_QUALITY].result["has_tests"] is True
    assert "fastapi" in rows[VerificationStageKind.TECHNOLOGY_DETECTION].result["detected_technologies"]

    # Stage 6 stays open: the interview is student-initiated, not run here.
    assert rows[VerificationStageKind.CODE_GROUNDED_INTERVIEW].status is VerificationStageStatus.PENDING
    assert rows[VerificationStageKind.EVIDENCE_REPORT].status is VerificationStageStatus.PENDING


def test_failed_authorship_check_skips_every_later_stage_and_blocks_the_interview(
    client: TestClient, db_session: Session, monkeypatch
):
    """The gate: a repository the candidate did not author is rejected at
    stage 2, nothing downstream runs, and no interview can be generated."""
    from src.domains.interview.exceptions import RepositoryNotVerified
    from src.domains.interview import service as interview_service
    from src.domains.student.models import (
        STAGE_SEQUENCE,
        VerificationStageKind,
        VerificationStageStatus,
    )
    from src.jobs.tasks.verification import verify_repository_task

    token, profile = _candidate(db_session, "stages.unauthored@example.com")
    project = _repo_project(client, db_session, token, "https://github.com/other/notmine")
    job = _pending_job(db_session, "verify_repository")
    # Effectively no commits by the candidate — below the reject threshold.
    _stub_repository_analysis(monkeypatch, contribution_share=0.0, is_fork=False)

    verify_repository_task.run(str(job.id))

    rows = _stages_by_kind(db_session, project.id)
    assert rows[VerificationStageKind.REPOSITORY_SELECTION].status is VerificationStageStatus.SUCCEEDED
    assert rows[VerificationStageKind.FORK_AUTHORSHIP_CHECK].status is VerificationStageStatus.FAILED
    assert rows[VerificationStageKind.FORK_AUTHORSHIP_CHECK].error

    # Skipped, not failed — these never ran.
    for kind in STAGE_SEQUENCE[2:]:
        assert rows[kind].status is VerificationStageStatus.SKIPPED, kind

    db_session.refresh(project)
    assert project.verification_status is VerificationStatus.REJECTED

    with pytest.raises(RepositoryNotVerified):
        interview_service.start_interview(db_session, profile, project.id)


def test_a_mid_pipeline_failure_preserves_earlier_stage_results(
    client: TestClient, db_session: Session, monkeypatch
):
    """The reason stages exist: a stage-4 outage must not discard the fork
    check and contribution analysis that already succeeded."""
    from src.domains.student.models import VerificationStageKind, VerificationStageStatus
    from src.domains.verification.exceptions import VerificationServiceUnavailable
    from src.jobs.tasks.verification import verify_repository_task

    token, _profile = _candidate(db_session, "stages.flaky@example.com")
    project = _repo_project(client, db_session, token, "https://github.com/ada/flaky")
    job = _pending_job(db_session, "verify_repository")
    _stub_repository_analysis(monkeypatch, contribution_share=0.9, is_fork=False)

    def _tree_unavailable(owner, repo, branch, **kw):
        raise VerificationServiceUnavailable("GitHub tree endpoint timed out")

    monkeypatch.setattr(github_client, "get_repo_tree", _tree_unavailable)

    with pytest.raises(VerificationServiceUnavailable):
        verify_repository_task.run(str(job.id))

    rows = _stages_by_kind(db_session, project.id)
    assert rows[VerificationStageKind.REPOSITORY_SELECTION].status is VerificationStageStatus.SUCCEEDED
    assert rows[VerificationStageKind.FORK_AUTHORSHIP_CHECK].status is VerificationStageStatus.SUCCEEDED
    assert rows[VerificationStageKind.CONTRIBUTION_ANALYSIS].status is VerificationStageStatus.SUCCEEDED
    assert rows[VerificationStageKind.CONTRIBUTION_ANALYSIS].result["contribution_share"] == 0.9

    # The stage that broke goes back to PENDING rather than FAILED: the retry
    # re-runs the pipeline from the top, and a FAILED predecessor would make
    # the "previous stage succeeded" gate refuse to reach it again.
    assert rows[VerificationStageKind.ARCHITECTURE_CODE_QUALITY].status is VerificationStageStatus.PENDING


# --------------------------------------------------------------------------
# Coding platform — Codeforces (real API shape, stubbed) and HackerRank
# (reachability heuristic only)
# --------------------------------------------------------------------------


def test_verify_coding_platform_verifies_a_real_codeforces_handle(
    client: TestClient, db_session: Session, monkeypatch
):
    from src.jobs.tasks.verification import verify_coding_platform_account_task

    token, profile = _candidate(db_session, "cf.handle@example.com")
    client.put(
        f"{STUDENT_BASE}/sections/technical",
        json={"github_username": "ada", "coding_profiles": [{"platform": "codeforces", "handle": "tourist"}]},
        headers=_auth(token),
    )
    job = _pending_job(db_session, "verify_coding_platform_account")

    monkeypatch.setattr(
        codeforces_client,
        "get_user_info",
        lambda handle: {"handle": "tourist", "rating": 3500, "maxRating": 3800, "rank": "legendary grandmaster"},
    )
    monkeypatch.setattr(codeforces_client, "count_solved_problems", lambda handle, **kw: 4000)

    verify_coding_platform_account_task.run(str(job.id))

    account = db_session.execute(
        select(CodingPlatformAccount).where(CodingPlatformAccount.candidate_profile_id == profile.id)
    ).scalar_one()
    assert account.verification_status is VerificationStatus.VERIFIED
    assert account.verification_source == "codeforces_api"
    assert account.verification_payload["solved_count"] == 4000


def test_verify_coding_platform_hackerrank_reaches_at_most_flagged(
    client: TestClient, db_session: Session, monkeypatch
):
    from src.jobs.tasks.verification import verify_coding_platform_account_task

    token, profile = _candidate(db_session, "hr.handle@example.com")
    client.put(
        f"{STUDENT_BASE}/sections/technical",
        json={"github_username": "ada", "coding_profiles": [{"platform": "hackerrank", "handle": "adadev"}]},
        headers=_auth(token),
    )
    job = _pending_job(db_session, "verify_coding_platform_account")
    monkeypatch.setattr(reachability, "check_reachable", lambda url, **kw: (True, "adadev"))

    verify_coding_platform_account_task.run(str(job.id))

    account = db_session.execute(
        select(CodingPlatformAccount).where(CodingPlatformAccount.candidate_profile_id == profile.id)
    ).scalar_one()
    assert account.verification_status is VerificationStatus.FLAGGED
    assert account.verification_payload["confidence"] == "low"


# --------------------------------------------------------------------------
# Certificate
# --------------------------------------------------------------------------


def test_verify_certificate_verified_when_reachable_and_issuer_matches(
    client: TestClient, db_session: Session, monkeypatch
):
    from src.jobs.tasks.verification import verify_certificate_task

    token, profile = _candidate(db_session, "cert.holder@example.com")
    client.put(
        f"{STUDENT_BASE}/sections/certificates",
        json={
            "certificates": [
                {
                    "title": "Intro to ML",
                    "issuer": "Coursera",
                    "credential_url": "https://coursera.org/verify/abc",
                }
            ]
        },
        headers=_auth(token),
    )
    job = _pending_job(db_session, "verify_certificate")
    monkeypatch.setattr(reachability, "check_reachable", lambda url, **kw: (True, ""))

    verify_certificate_task.run(str(job.id))

    cert = db_session.execute(
        select(Certificate).where(Certificate.candidate_profile_id == profile.id)
    ).scalar_one()
    assert cert.verification_status is VerificationStatus.VERIFIED
    assert cert.verified_at is not None


# --------------------------------------------------------------------------
# Experience — consolidated internal signals, never VERIFIED
# --------------------------------------------------------------------------


def test_verify_experience_flags_when_technologies_overlap_a_verified_project(
    client: TestClient, db_session: Session, monkeypatch
):
    from src.jobs.tasks.verification import verify_experience_task

    token, profile = _candidate(db_session, "exp.holder@example.com")

    # A pre-existing verified project carrying "Django" as evidence.
    verified_project = Project(
        candidate_profile_id=profile.id,
        kind=ProjectKind.REPOSITORY,
        title="Verified App",
        repo_url="https://github.com/ada/verified",
        technologies=["Django"],
        verification_status=VerificationStatus.VERIFIED,
    )
    db_session.add(verified_project)
    db_session.commit()

    resp = client.put(
        f"{STUDENT_BASE}/sections/experience",
        json={
            "experiences": [
                {
                    "company_name": "Some Startup",
                    "title": "Backend Intern",
                    "employment_type": "internship",
                    "start_date": "2025-06-01",
                    "end_date": "2025-08-01",
                    "technologies": ["Django"],
                }
            ]
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    job = _pending_job(db_session, "verify_experience")
    verify_experience_task.run(str(job.id))

    experience = db_session.execute(
        select(Experience).where(Experience.candidate_profile_id == profile.id)
    ).scalar_one()
    assert experience.verification_status is VerificationStatus.FLAGGED
    assert "Django" in experience.verification_payload["overlapping_technologies"]


def test_verify_experience_never_writes_verified(client: TestClient, db_session: Session):
    from src.jobs.tasks.verification import verify_experience_task

    token, profile = _candidate(db_session, "exp.unverified@example.com")
    client.put(
        f"{STUDENT_BASE}/sections/experience",
        json={
            "experiences": [
                {
                    "company_name": "Totally Unknown Co",
                    "title": "Intern",
                    "employment_type": "internship",
                    "start_date": "2025-06-01",
                    "technologies": ["Cobol"],
                }
            ]
        },
        headers=_auth(token),
    )
    job = _pending_job(db_session, "verify_experience")
    verify_experience_task.run(str(job.id))

    experience = db_session.execute(
        select(Experience).where(Experience.candidate_profile_id == profile.id)
    ).scalar_one()
    assert experience.verification_status is not VerificationStatus.VERIFIED
