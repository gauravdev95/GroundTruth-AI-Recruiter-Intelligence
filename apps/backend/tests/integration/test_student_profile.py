"""Integration tests for the student profile-builder API.

Accounts are set up by calling `domains.auth.service` directly, then every
assertion goes through the real HTTP endpoints so auth, validation, and the
error envelope are exercised for real.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domains.auth import service as auth_service
from src.domains.auth.models import CandidateProfile
from src.domains.auth.schemas import CandidateRegisterRequest, RecruiterRegisterRequest
from src.domains.auth.security import create_access_token
from src.domains.student.models import Certificate, CodingPlatformAccount, GithubAccount, Project
from src.platform.models import AsyncJob, AsyncJobStatus

BASE = "/api/v1/student/profile"


@pytest.fixture(autouse=True)
def stub_broker(monkeypatch):
    """Don't publish to a real broker.

    Section saves now dispatch queued verification jobs after commit
    (`evidence.dispatch_all`); these tests assert on `async_jobs` row state,
    not on Celery's own publish path, so stubbing it keeps them runnable
    without Redis. Same fixture as `test_resume_import.py::stub_broker`.
    """
    monkeypatch.setattr("src.jobs.dispatch.dispatch", lambda job, task, *, queue, args=None: None)

VALID_BASIC = {
    "full_name": "Ada Lovelace",
    "headline": "Final-year CS student building compilers",
    "college": "IIT Bombay",
    "degree": "btech",
    "branch": "cse",
    "graduation_year": 2026,
    "location": "Mumbai, India",
    "target_roles": ["backend"],
}

#: `claimed_technologies`, never `technologies` — the plain name belongs to
#: the list the verification worker detects from dependency manifests, and
#: the request model rejects it outright.
VALID_PROJECTS = {
    "projects": [
        {
            "kind": "described",
            "title": "Toy compiler",
            "description": "A small compiler for a Lisp dialect, written in Rust.",
            "claimed_technologies": ["Rust"],
            "is_primary": True,
        }
    ]
}

VALID_TECHNICAL = {
    "github_username": "ada",
    "coding_profiles": [{"platform": "leetcode", "handle": "ada_lovelace"}],
}


def _candidate_token(client: TestClient, db_session: Session, email: str = "student.profile@example.com") -> str:
    """Register a verified candidate and mint its access token directly.

    Deliberately not going through `POST /auth/login`: that endpoint enforces
    reCAPTCHA and per-IP rate limits, neither of which is under test here.
    Minting the token with the same helper the login endpoint uses keeps these
    tests about the profile API and independent of CAPTCHA configuration.
    """
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


def _recruiter_token(client: TestClient, db_session: Session, email: str = "recruiter.profile@acme.com") -> str:
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
    return create_access_token(user_id=user.id, role=user.role.value)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _profile(db_session: Session, email: str) -> CandidateProfile:
    return db_session.execute(
        select(CandidateProfile).join(CandidateProfile.user).where(CandidateProfile.user.has(email=email))
    ).scalar_one()


# --------------------------------------------------------------------------
# Authentication and authorization
# --------------------------------------------------------------------------


SECTION_PATHS = [
    f"{BASE}/sections/basic",
    f"{BASE}/sections/technical",
    f"{BASE}/sections/projects",
    f"{BASE}/sections/certificates",
    f"{BASE}/sections/experience",
]


def test_every_endpoint_requires_authentication(client: TestClient) -> None:
    for path in [*SECTION_PATHS, f"{BASE}/completeness"]:
        assert client.get(path).status_code == 401, path
    for path in SECTION_PATHS:
        assert client.put(path, json={}).status_code == 401, path


def test_recruiter_gets_403_on_every_endpoint(client: TestClient, db_session: Session) -> None:
    headers = _auth(_recruiter_token(client, db_session))

    for path in [*SECTION_PATHS, f"{BASE}/completeness"]:
        resp = client.get(path, headers=headers)
        assert resp.status_code == 403, path
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    for path in SECTION_PATHS:
        assert client.put(path, json={}, headers=headers).status_code == 403, path


def test_candidate_only_ever_reads_its_own_profile(client: TestClient, db_session: Session) -> None:
    """There is no profile id in any route, so a candidate cannot address
    another candidate's data at all — each token resolves to its own row."""
    first = _auth(_candidate_token(client, db_session, "first.student@example.com"))
    second = _auth(_candidate_token(client, db_session, "second.student@example.com"))

    client.put(f"{BASE}/sections/basic", json=VALID_BASIC, headers=first)

    resp = client.get(f"{BASE}/sections/basic", headers=second)
    assert resp.status_code == 200
    assert resp.json()["data"]["college"] is None


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def test_unknown_fields_are_rejected(client: TestClient, db_session: Session) -> None:
    headers = _auth(_candidate_token(client, db_session))

    resp = client.put(
        f"{BASE}/sections/basic",
        json={**VALID_BASIC, "surprise_field": "nope"},
        headers=headers,
    )

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_FAILED"


def test_client_cannot_supply_profile_strength_or_discoverability(
    client: TestClient, db_session: Session
) -> None:
    """Both are server-derived; they are not declared on any request model, so
    `extra="forbid"` rejects them outright rather than ignoring them."""
    headers = _auth(_candidate_token(client, db_session))

    for smuggled in ({"profile_strength": 100}, {"is_discoverable": True}):
        resp = client.put(f"{BASE}/sections/basic", json={**VALID_BASIC, **smuggled}, headers=headers)
        assert resp.status_code == 422, smuggled


def test_basic_section_rejects_invalid_enum_and_year(client: TestClient, db_session: Session) -> None:
    headers = _auth(_candidate_token(client, db_session))

    bad_degree = client.put(
        f"{BASE}/sections/basic", json={**VALID_BASIC, "degree": "wizardry"}, headers=headers
    )
    assert bad_degree.status_code == 422

    bad_year = client.put(
        f"{BASE}/sections/basic", json={**VALID_BASIC, "graduation_year": 1200}, headers=headers
    )
    assert bad_year.status_code == 422


def test_technical_accepts_no_coding_profiles(client: TestClient, db_session: Session) -> None:
    """It used to require at least one, back when GitHub and the handles were
    a single mandatory `technical` section. They are separate sections now and
    only GitHub is required, so demanding a handle here would reinstate the
    gate the split removed."""
    headers = _auth(_candidate_token(client, db_session))

    resp = client.put(
        f"{BASE}/sections/technical",
        json={"github_username": "ada", "coding_profiles": []},
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["coding_profiles"] == []
    # GitHub alone completes the mandatory half of what used to be one
    # section; a project is what is still owed.
    blocking = resp.json()["completeness"]["blocking"]
    assert "your GitHub account" not in blocking
    assert "at least one project" in blocking


def test_github_profile_url_is_normalized_to_a_username(client: TestClient, db_session: Session) -> None:
    headers = _auth(_candidate_token(client, db_session))

    resp = client.put(
        f"{BASE}/sections/technical",
        json={**VALID_TECHNICAL, "github_username": "https://github.com/ada"},
        headers=headers,
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["github_account"]["github_username"] == "ada"
    assert resp.json()["data"]["github_account"]["profile_url"] == "https://github.com/ada"


def test_non_github_url_is_rejected(client: TestClient, db_session: Session) -> None:
    headers = _auth(_candidate_token(client, db_session))

    resp = client.put(
        f"{BASE}/sections/technical",
        json={**VALID_TECHNICAL, "github_username": "https://gitlab.com/ada"},
        headers=headers,
    )

    assert resp.status_code == 422


def test_projects_are_capped_at_three(client: TestClient, db_session: Session) -> None:
    headers = _auth(_candidate_token(client, db_session))
    payload = {
        "projects": [
            {"kind": "repository", "title": f"Repo {i}", "repo_url": f"https://github.com/ada/r{i}"}
            for i in range(4)
        ]
    }

    assert client.put(f"{BASE}/sections/projects", json=payload, headers=headers).status_code == 422


def test_project_kind_shape_is_enforced(client: TestClient, db_session: Session) -> None:
    headers = _auth(_candidate_token(client, db_session))

    missing_url = client.put(
        f"{BASE}/sections/projects",
        json={"projects": [{"kind": "repository", "title": "No URL"}]},
        headers=headers,
    )
    assert missing_url.status_code == 422

    described_with_url = client.put(
        f"{BASE}/sections/projects",
        json={
            "projects": [
                {"kind": "described", "title": "Essay", "description": "x", "repo_url": "https://a.co/b"}
            ]
        },
        headers=headers,
    )
    assert described_with_url.status_code == 422

    described_without_description = client.put(
        f"{BASE}/sections/projects",
        json={"projects": [{"kind": "described", "title": "Essay"}]},
        headers=headers,
    )
    assert described_without_description.status_code == 422


def test_items_that_would_collide_on_the_natural_key_are_rejected(
    client: TestClient, db_session: Session
) -> None:
    """Reconciliation keys a repo by URL and a described project by title, so
    two items sharing a key would silently merge into one row."""
    headers = _auth(_candidate_token(client, db_session))

    duplicate_repo = client.put(
        f"{BASE}/sections/projects",
        json={
            "projects": [
                {"kind": "repository", "title": "A", "repo_url": "https://github.com/ada/x"},
                {"kind": "repository", "title": "B", "repo_url": "https://github.com/ada/x"},
            ]
        },
        headers=headers,
    )
    assert duplicate_repo.status_code == 422

    duplicate_described = client.put(
        f"{BASE}/sections/projects",
        json={
            "projects": [
                {"kind": "described", "title": "Thesis", "description": "one"},
                {"kind": "described", "title": "thesis", "description": "two"},
            ]
        },
        headers=headers,
    )
    assert duplicate_described.status_code == 422

    duplicate_certificate = client.put(
        f"{BASE}/sections/certificates",
        json={
            "certificates": [
                {"title": "AWS SAA", "issuer": "Amazon"},
                {"title": "aws saa", "issuer": "amazon"},
            ]
        },
        headers=headers,
    )
    assert duplicate_certificate.status_code == 422


def test_non_http_urls_are_rejected(client: TestClient, db_session: Session) -> None:
    headers = _auth(_candidate_token(client, db_session))

    resp = client.put(
        f"{BASE}/sections/certificates",
        json={
            "certificates": [
                {"title": "AWS SAA", "issuer": "Amazon", "credential_url": "javascript:alert(1)"}
            ]
        },
        headers=headers,
    )

    assert resp.status_code == 422


# --------------------------------------------------------------------------
# Per-section independence and strength recomputation
# --------------------------------------------------------------------------


def test_sections_save_independently_across_sittings(client: TestClient, db_session: Session) -> None:
    headers = _auth(_candidate_token(client, db_session))

    first = client.put(f"{BASE}/sections/basic", json=VALID_BASIC, headers=headers)
    assert first.status_code == 200
    assert first.json()["completeness"]["profile_strength"] == 35
    assert first.json()["completeness"]["is_discoverable"] is False

    second = client.put(f"{BASE}/sections/technical", json=VALID_TECHNICAL, headers=headers)
    assert second.status_code == 200
    # 35 basic + 15 GitHub + 5 for one coding profile.
    assert second.json()["completeness"]["profile_strength"] == 55
    # Not met yet: projects became mandatory, because every downstream
    # artefact starts from a linked repository.
    assert second.json()["completeness"]["meets_section_requirements"] is False

    third = client.put(f"{BASE}/sections/projects", json=VALID_PROJECTS, headers=headers)
    assert third.status_code == 200, third.text
    # + 10 for the first project, which is worth double the others.
    assert third.json()["completeness"]["profile_strength"] == 65
    # Every mandatory section is complete now. Discoverability additionally
    # waits on the embedding worker, which is stubbed in these tests.
    assert third.json()["completeness"]["meets_section_requirements"] is True
    assert third.json()["completeness"]["is_discoverable"] is False

    # Section 1 survived the section 2 save untouched.
    basic = client.get(f"{BASE}/sections/basic", headers=headers)
    assert basic.json()["data"]["college"] == "IIT Bombay"


def test_strength_is_persisted_not_just_reported(client: TestClient, db_session: Session) -> None:
    email = "persisted.student@example.com"
    headers = _auth(_candidate_token(client, db_session, email))

    client.put(f"{BASE}/sections/basic", json=VALID_BASIC, headers=headers)
    client.put(f"{BASE}/sections/technical", json=VALID_TECHNICAL, headers=headers)
    client.put(f"{BASE}/sections/projects", json=VALID_PROJECTS, headers=headers)

    profile = _profile(db_session, email)
    db_session.refresh(profile)
    # 35 basic + 15 GitHub + 10 first project + 5 one coding profile.
    assert profile.profile_strength == 65
    # Every mandatory section is done, so the student has met every requirement
    # they can act on — but `is_discoverable` additionally needs the profile
    # vector, and the embedding worker is stubbed out here (`stub_broker`). It
    # stays False until that job runs; see
    # `test_embed_and_match_makes_the_profile_discoverable`.
    resp = client.get(f"{BASE}/completeness", headers=headers)
    assert resp.json()["meets_section_requirements"] is True
    assert resp.json()["is_discoverable"] is False
    assert profile.is_discoverable is False


def test_discoverability_turns_off_when_a_mandatory_section_is_emptied(
    client: TestClient, db_session: Session
) -> None:
    email = "toggling.student@example.com"
    headers = _auth(_candidate_token(client, db_session, email))

    client.put(f"{BASE}/sections/basic", json=VALID_BASIC, headers=headers)
    client.put(f"{BASE}/sections/technical", json=VALID_TECHNICAL, headers=headers)
    client.put(f"{BASE}/sections/projects", json=VALID_PROJECTS, headers=headers)
    assert client.get(f"{BASE}/completeness", headers=headers).json()["meets_section_requirements"] is True

    # Replacing section 2 with a different platform keeps it complete...
    client.put(
        f"{BASE}/sections/technical",
        json={"github_username": "ada", "coding_profiles": [{"platform": "codeforces", "handle": "ada"}]},
        headers=headers,
    )
    profile = _profile(db_session, email)
    db_session.refresh(profile)
    assert client.get(f"{BASE}/completeness", headers=headers).json()["meets_section_requirements"] is True

    active = db_session.execute(
        select(CodingPlatformAccount).where(
            CodingPlatformAccount.candidate_profile_id == profile.id,
            CodingPlatformAccount.deleted_at.is_(None),
        )
    ).scalars().all()
    assert [account.platform.value for account in active] == ["codeforces"]


def test_optional_sections_add_strength_without_affecting_discoverability(
    client: TestClient, db_session: Session
) -> None:
    headers = _auth(_candidate_token(client, db_session))

    resp = client.put(
        f"{BASE}/sections/experience",
        json={
            "experiences": [
                {
                    "company_name": "Acme",
                    "title": "Backend Intern",
                    "employment_type": "internship",
                    "start_date": "2025-06-01",
                    "end_date": "2025-08-31",
                    "technologies": ["Python", "python", "  FastAPI  "],
                }
            ]
        },
        headers=headers,
    )

    assert resp.status_code == 200
    assert resp.json()["completeness"]["profile_strength"] == 5
    assert resp.json()["completeness"]["is_discoverable"] is False
    # Technologies are trimmed and de-duplicated case-insensitively.
    assert resp.json()["data"]["experiences"][0]["technologies"] == ["Python", "FastAPI"]


# --------------------------------------------------------------------------
# Evidence queuing
# --------------------------------------------------------------------------


def _jobs(db_session: Session, job_type: str) -> list[AsyncJob]:
    return list(
        db_session.execute(select(AsyncJob).where(AsyncJob.job_type == job_type)).scalars()
    )


def test_github_and_coding_claims_are_queued_as_pending(client: TestClient, db_session: Session) -> None:
    email = "queued.student@example.com"
    headers = _auth(_candidate_token(client, db_session, email))

    client.put(f"{BASE}/sections/technical", json=VALID_TECHNICAL, headers=headers)

    profile = _profile(db_session, email)
    github = db_session.execute(
        select(GithubAccount).where(GithubAccount.candidate_profile_id == profile.id)
    ).scalar_one()
    assert github.verification_status.value == "pending"
    assert github.verified_at is None

    github_jobs = _jobs(db_session, "verify_github_account")
    assert len(github_jobs) == 1
    assert github_jobs[0].status is AsyncJobStatus.PENDING
    assert github_jobs[0].payload["source_id"] == str(github.id)
    assert github_jobs[0].payload["source_type"] == "github_account"

    assert len(_jobs(db_session, "verify_coding_platform_account")) == 1


def test_repo_and_certificate_urls_are_queued(client: TestClient, db_session: Session) -> None:
    email = "urls.student@example.com"
    headers = _auth(_candidate_token(client, db_session, email))

    client.put(
        f"{BASE}/sections/projects",
        json={
            "projects": [
                {
                    "kind": "repository",
                    "title": "Compiler",
                    "repo_url": "https://github.com/ada/compiler",
                    "claimed_technologies": ["Rust"],
                },
                {"kind": "described", "title": "Thesis", "description": "A described project"},
            ]
        },
        headers=headers,
    )
    client.put(
        f"{BASE}/sections/certificates",
        json={
            "certificates": [
                {
                    "title": "AWS SAA",
                    "issuer": "Amazon",
                    "credential_url": "https://credly.com/badges/abc",
                },
                {"title": "Dean's List", "issuer": "IIT Bombay"},
            ]
        },
        headers=headers,
    )

    profile = _profile(db_session, email)
    projects = db_session.execute(
        select(Project).where(Project.candidate_profile_id == profile.id).order_by(Project.position)
    ).scalars().all()
    # Only the repository-kind project is queued; a described project has no
    # URL to fetch, so it stays unverified rather than pending forever.
    assert projects[0].verification_status.value == "pending"
    assert projects[1].verification_status.value == "unverified"
    assert len(_jobs(db_session, "verify_repository")) == 1

    certificates = db_session.execute(
        select(Certificate)
        .where(Certificate.candidate_profile_id == profile.id)
        .order_by(Certificate.position)
    ).scalars().all()
    assert certificates[0].verification_status.value == "pending"
    assert certificates[1].verification_status.value == "unverified"
    assert len(_jobs(db_session, "verify_certificate")) == 1


def test_resaving_an_unchanged_section_does_not_duplicate_jobs(
    client: TestClient, db_session: Session
) -> None:
    headers = _auth(_candidate_token(client, db_session))

    client.put(f"{BASE}/sections/technical", json=VALID_TECHNICAL, headers=headers)
    client.put(f"{BASE}/sections/technical", json=VALID_TECHNICAL, headers=headers)
    client.put(f"{BASE}/sections/technical", json=VALID_TECHNICAL, headers=headers)

    assert len(_jobs(db_session, "verify_github_account")) == 1
    assert len(_jobs(db_session, "verify_coding_platform_account")) == 1


def test_resaving_preserves_a_verified_status(client: TestClient, db_session: Session) -> None:
    """A student editing an unrelated field must not silently un-verify work a
    Phase II worker already completed."""
    email = "verified.student@example.com"
    headers = _auth(_candidate_token(client, db_session, email))

    client.put(f"{BASE}/sections/projects", json={
        "projects": [
            {"kind": "repository", "title": "Compiler", "repo_url": "https://github.com/ada/compiler"}
        ]
    }, headers=headers)

    profile = _profile(db_session, email)
    project = db_session.execute(
        select(Project).where(Project.candidate_profile_id == profile.id)
    ).scalar_one()

    # Simulate the Phase II worker finishing.
    project.verification_status = "verified"
    db_session.commit()

    # Student renames the project; the repo URL (the thing verified) is unchanged.
    renamed = client.put(f"{BASE}/sections/projects", json={
        "projects": [
            {
                "kind": "repository",
                "title": "Compiler v2",
                "repo_url": "https://github.com/ada/compiler",
                "claimed_technologies": ["Rust"],
            }
        ]
    }, headers=headers)
    assert renamed.status_code == 200, renamed.text

    db_session.refresh(project)
    assert project.title == "Compiler v2"
    assert project.verification_status.value == "verified"


def test_removing_a_project_soft_deletes_it(client: TestClient, db_session: Session) -> None:
    email = "removing.student@example.com"
    headers = _auth(_candidate_token(client, db_session, email))

    client.put(f"{BASE}/sections/projects", json={
        "projects": [
            {"kind": "repository", "title": "One", "repo_url": "https://github.com/ada/one"},
            {"kind": "repository", "title": "Two", "repo_url": "https://github.com/ada/two"},
        ]
    }, headers=headers)

    client.put(f"{BASE}/sections/projects", json={
        "projects": [{"kind": "repository", "title": "One", "repo_url": "https://github.com/ada/one"}]
    }, headers=headers)

    resp = client.get(f"{BASE}/sections/projects", headers=headers)
    assert [p["title"] for p in resp.json()["data"]["projects"]] == ["One"]

    profile = _profile(db_session, email)
    all_rows = db_session.execute(
        select(Project).where(Project.candidate_profile_id == profile.id)
    ).scalars().all()
    # The removed row is retained, soft-deleted, not destroyed.
    assert len(all_rows) == 2
    assert sum(1 for row in all_rows if row.deleted_at is not None) == 1


def test_completeness_endpoint_reports_blocking_requirements(
    client: TestClient, db_session: Session
) -> None:
    headers = _auth(_candidate_token(client, db_session))

    resp = client.get(f"{BASE}/completeness", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["profile_strength"] == 0
    assert body["is_discoverable"] is False
    # Six, not five: `github` and `coding` are scored separately now.
    assert len(body["sections"]) == 6
    assert "your GitHub account" in body["blocking"]
    assert "at least one project" in body["blocking"]


def test_onboarding_choice_starts_null_and_is_recorded_once(
    client: TestClient, db_session: Session
) -> None:
    """The fork is answered once and the answer is durable server state — the
    client gates on `onboarding_choice`, not on `profile_strength == 0`,
    because picking "build manually" writes no section data."""
    headers = _auth(_candidate_token(client, db_session))

    assert client.get(f"{BASE}/completeness", headers=headers).json()["onboarding_choice"] is None

    resp = client.post(f"{BASE}/onboarding", json={"choice": "manual_entry"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["onboarding_choice"] == "manual_entry"
    # Answering writes no profile data, so nothing about completeness moves.
    assert resp.json()["profile_strength"] == 0

    # Re-answering is a no-op, not a conflict and not a rewrite: the fork lives
    # at a URL the student can navigate back to.
    second = client.post(f"{BASE}/onboarding", json={"choice": "resume_upload"}, headers=headers)
    assert second.status_code == 200
    assert second.json()["onboarding_choice"] == "manual_entry"

    assert client.get(f"{BASE}/completeness", headers=headers).json()["onboarding_choice"] == "manual_entry"


def test_onboarding_rejects_an_unknown_choice(client: TestClient, db_session: Session) -> None:
    headers = _auth(_candidate_token(client, db_session))

    resp = client.post(f"{BASE}/onboarding", json={"choice": "telepathy"}, headers=headers)

    assert resp.status_code == 422
