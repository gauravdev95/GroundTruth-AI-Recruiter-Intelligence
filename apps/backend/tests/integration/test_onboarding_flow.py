"""End-to-end integration test for the eight-stage student onboarding flow.

One test walks a brand-new account from the entry fork to a submitted profile,
asserting the state the client would render at every stage. The others pin the
gates that walk is not allowed to skip.

**Every step goes through the real HTTP endpoints.** Nothing here calls a
service function directly, so auth, request validation, the error envelope and
the completeness recomputation are all exercised as the browser exercises
them. The only things stubbed are the two external systems this flow is not a
test of: Celery's publish path and GitHub's API.

The stage numbering below matches `student/setup_state.py::SETUP_STEPS` and the
frontend's `setup/lib/stages.ts`. Those three lists are the same flow written
three times, and the assertions on step keys and ordering here are what keep
them from drifting apart.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.config import GitHubOAuthSettings
from src.domains.auth import service as auth_service
from src.domains.auth.models import CandidateProfile
from src.domains.auth.schemas import CandidateRegisterRequest
from src.domains.auth.security import create_access_token
from src.domains.student.models import Project, VerificationStatus
from src.domains.verification.clients import github as github_client

PROFILE_BASE = "/api/v1/student/profile"
GITHUB_BASE = "/api/v1/student/github"
SETUP_STATE = f"{PROFILE_BASE}/setup-state"

#: The stage order the client renders. Written out rather than derived from
#: `SETUP_STEPS` on purpose: deriving it would make this test agree with the
#: server by construction, and the whole point is to catch a reordering that
#: the frontend's own list has not followed.
EXPECTED_STAGES = [
    "choose",
    "basic",
    "github",
    "projects",
    "coding",
    "certificates",
    "experience",
    "review",
]

VALID_BASIC = {
    "full_name": "Ada Lovelace",
    "headline": "Final-year CS student building compilers",
    "college": "IIT Bombay",
    "degree": "btech",
    "branch": "cse",
    "graduation_year": 2026,
    "location": "Mumbai, India",
    "target_roles": ["backend", "ml_engineer"],
}

_TEST_GITHUB_OAUTH_SETTINGS = GitHubOAuthSettings(
    github_client_id="test-client-id", github_client_secret="test-secret"
)

_REPOS = [
    {
        "full_name": "ada/payments-api",
        "name": "payments-api",
        "description": "Settlement engine",
        "language": "Python",
        "fork": False,
        "private": False,
        "stargazers_count": 12,
        "updated_at": "2026-07-01T00:00:00Z",
    },
    {
        "full_name": "ada/compiler",
        "name": "compiler",
        "description": None,
        "language": "Rust",
        "fork": False,
        "private": False,
        "stargazers_count": 3,
        "updated_at": "2026-06-01T00:00:00Z",
    },
]


@pytest.fixture(autouse=True)
def stub_broker(monkeypatch):
    """Section saves dispatch verification jobs after commit. This test asserts
    on database state and HTTP responses, not on Celery's publish path."""
    monkeypatch.setattr("src.jobs.dispatch.dispatch", lambda job, task, *, queue, args=None: None)


@pytest.fixture(autouse=True)
def configured_github_oauth(monkeypatch):
    """Patched at each *call site*, not at `src.config.config`: both modules do
    `from ... import get_github_oauth_settings`, which binds a local name at
    import time that patching the origin would not affect."""
    monkeypatch.setattr(
        "src.domains.student.github_oauth.get_github_oauth_settings",
        lambda: _TEST_GITHUB_OAUTH_SETTINGS,
    )
    monkeypatch.setattr(
        "src.domains.verification.clients.github.get_github_oauth_settings",
        lambda: _TEST_GITHUB_OAUTH_SETTINGS,
    )


@pytest.fixture()
def github_api(monkeypatch):
    """The GitHub side of stages 2 and 3, stubbed at the client boundary."""
    monkeypatch.setattr(
        github_client, "exchange_code_for_token", lambda code: ("gho_faketoken", "read:user,public_repo")
    )
    monkeypatch.setattr(
        github_client,
        "get_user_authenticated",
        lambda tok: {
            "id": 999,
            "login": "ada",
            "html_url": "https://github.com/ada",
            "public_repos": 5,
            "followers": 2,
        },
    )
    monkeypatch.setattr(github_client, "list_user_repos", lambda tok: _REPOS)


def _register(db_session: Session, email: str) -> tuple[str, CandidateProfile]:
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


def _connect_github(client: TestClient, token: str) -> None:
    """Stages 2's OAuth round trip, as the browser performs it."""
    connect = client.get(f"{GITHUB_BASE}/connect", headers=_auth(token))
    assert connect.status_code == 200, connect.text
    state = parse_qs(urlparse(connect.json()["authorize_url"]).query)["state"][0]

    callback = client.get(
        f"{GITHUB_BASE}/callback", params={"code": "abc", "state": state}, follow_redirects=False
    )
    assert callback.status_code in (302, 307)
    assert "github=connected" in callback.headers["location"]


def _state(client: TestClient, token: str) -> dict:
    resp = client.get(SETUP_STATE, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _step(state: dict, key: str) -> dict:
    return next(step for step in state["steps"] if step["key"] == key)


# --------------------------------------------------------------------------
# The full walk
# --------------------------------------------------------------------------


def test_a_student_can_walk_the_whole_flow_and_submit(
    client: TestClient, db_session: Session, github_api
) -> None:
    """Stage 0 to a submitted profile, in one pass.

    Each block below is one stage of the flow, and asserts the two things the
    client actually depends on at that point: that the write succeeded, and
    that `setup-state` now reports what the progress bar and the Continue
    button read.
    """
    token, profile = _register(db_session, "flow.student@example.com")

    # --- Stage 0: the entry fork ------------------------------------------
    initial = _state(client, token)
    assert [step["key"] for step in initial["steps"]] == EXPECTED_STAGES
    assert initial["is_submitted"] is False
    assert initial["can_submit"] is False
    # A fresh profile owes all three mandatory stages.
    assert set(initial["blocking"]) == {"a headline", "your college", "your degree", "your branch",
                                        "your graduation year", "your location", "a target role",
                                        "your GitHub account", "at least one project"}

    choose = client.post(
        f"{PROFILE_BASE}/onboarding", json={"choice": "manual_entry"}, headers=_auth(token)
    )
    assert choose.status_code == 200, choose.text
    assert _step(_state(client, token), "choose")["status"] == "saved"

    # --- Stage 1: basic info ----------------------------------------------
    basic = client.put(f"{PROFILE_BASE}/sections/basic", json=VALID_BASIC, headers=_auth(token))
    assert basic.status_code == 200, basic.text
    saved_basic = basic.json()["data"]
    assert saved_basic["target_roles"] == ["backend", "ml_engineer"]
    # The scalar mirror is derived, never sent — and is always the first of the
    # array. See `CandidateProfile.target_role`.
    assert saved_basic["target_role"] == "backend"
    assert saved_basic["has_profile_photo"] is False

    after_basic = _state(client, token)
    assert _step(after_basic, "basic")["status"] == "saved"
    # The pill moves to the next incomplete mandatory stage, not to the next
    # empty one — GitHub is what is owed.
    assert _step(after_basic, "github")["is_current"] is True
    assert after_basic["can_submit"] is False

    # --- Stage 2: GitHub ---------------------------------------------------
    _connect_github(client, token)

    after_github = _state(client, token)
    github_step = _step(after_github, "github")
    # OAuth is stronger than the API check, so the account lands verified —
    # and the stage reports `verified`, not merely `saved`.
    assert github_step["status"] == "verified"
    assert after_github["blocking"] == ["at least one project"]
    assert after_github["can_submit"] is False

    # --- Stage 3: link projects (starts the background pipeline) -----------
    repos = client.get(f"{GITHUB_BASE}/repos", headers=_auth(token))
    assert repos.status_code == 200, repos.text
    assert [repo["full_name"] for repo in repos.json()["repos"]] == [
        "ada/payments-api",
        "ada/compiler",
    ]

    select_resp = client.post(
        f"{GITHUB_BASE}/repos/select",
        json={"repo_full_names": ["ada/payments-api"]},
        headers=_auth(token),
    )
    assert select_resp.status_code == 200, select_resp.text
    assert len(select_resp.json()["data"]["projects"]) == 1

    after_projects = _state(client, token)
    assert _step(after_projects, "projects")["status"] != "empty"
    assert after_projects["blocking"] == []
    # Every mandatory stage is done, so Submit would now succeed — three stages
    # before the student reaches it.
    assert after_projects["can_submit"] is True
    # ...and the pill has moved on to the first optional stage rather than
    # jumping to review.
    assert _step(after_projects, "coding")["is_current"] is True

    # The contribution note is a separate write, so editing it cannot re-queue
    # an analysis that is already running.
    project = db_session.execute(
        select(Project).where(Project.candidate_profile_id == profile.id)
    ).scalar_one()
    note = client.put(
        f"{PROFILE_BASE}/sections/projects",
        json={
            "projects": [
                {
                    "kind": "repository",
                    "title": project.title,
                    "description": "Built the settlement engine",
                    "repo_url": project.repo_url,
                    "is_primary": True,
                    "claimed_technologies": [],
                }
            ]
        },
        headers=_auth(token),
    )
    assert note.status_code == 200, note.text
    assert note.json()["data"]["projects"][0]["description"] == "Built the settlement engine"

    # --- Stage 4: coding profile (optional, and skipped) -------------------
    # An empty list is what "Skip for now" sends, and it is a valid body.
    coding = client.put(
        f"{PROFILE_BASE}/sections/coding", json={"coding_profiles": []}, headers=_auth(token)
    )
    assert coding.status_code == 200, coding.text
    assert coding.json()["data"]["coding_profiles"] == []
    # Skipping it takes nothing away: the GitHub account beside it is untouched
    # and the profile can still be submitted.
    assert coding.json()["data"]["github_account"]["github_username"] == "ada"
    assert _state(client, token)["can_submit"] is True

    # --- Stage 5: certificates (optional, filled) --------------------------
    certificates = client.put(
        f"{PROFILE_BASE}/sections/certificates",
        json={
            "certificates": [
                {
                    "title": "AWS Solutions Architect",
                    "issuer": "Amazon",
                    "issued_at": "2026-03-01",
                    "credential_url": "https://aws.amazon.com/verify/abc",
                }
            ]
        },
        headers=_auth(token),
    )
    assert certificates.status_code == 200, certificates.text

    # --- Stage 6: experience (optional, skipped) ---------------------------
    experience = client.put(
        f"{PROFILE_BASE}/sections/experience", json={"experiences": []}, headers=_auth(token)
    )
    assert experience.status_code == 200, experience.text

    # --- Stage 7: review & submit ------------------------------------------
    before_submit = _state(client, token)
    assert before_submit["can_submit"] is True
    assert before_submit["is_submitted"] is False
    # `can_submit` deliberately does not include consent: the box is ticked on
    # this very screen, so folding it in would leave the flag false on the only
    # screen that can turn it true.

    submit = client.post(f"{PROFILE_BASE}/submit", json={"consent": True}, headers=_auth(token))
    assert submit.status_code == 200, submit.text
    body = submit.json()
    assert body["is_submitted"] is True
    assert body["submitted_at"] is not None
    assert body["completeness"]["is_onboarding_submitted"] is True

    final = _state(client, token)
    assert final["is_submitted"] is True
    assert _step(final, "review")["status"] == "saved"
    # The flow ends on review with exactly one current step — the pill never
    # vanishes.
    assert sum(step["is_current"] for step in final["steps"]) == 1

    db_session.refresh(profile)
    assert profile.onboarding_submitted_at is not None
    # Consent is recorded in the same transaction as the submission.
    assert profile.onboarding_consent_at is not None
    assert profile.target_roles == ["backend", "ml_engineer"]


# --------------------------------------------------------------------------
# The gates that walk is not allowed to skip
# --------------------------------------------------------------------------


def test_submitting_without_a_project_is_refused(
    client: TestClient, db_session: Session, github_api
) -> None:
    """Projects became mandatory because every downstream artefact starts from
    a linked repository — a profile with none is one the pipeline cannot act
    on, so it must not be able to reach the dashboard."""
    token, _profile = _register(db_session, "no.project@example.com")
    client.put(f"{PROFILE_BASE}/sections/basic", json=VALID_BASIC, headers=_auth(token))
    _connect_github(client, token)

    state = _state(client, token)
    assert state["can_submit"] is False
    assert state["blocking"] == ["at least one project"]

    resp = client.post(f"{PROFILE_BASE}/submit", json={"consent": True}, headers=_auth(token))
    assert resp.status_code == 409, resp.text
    assert "at least one project" in resp.text


def test_submitting_without_consent_is_refused(
    client: TestClient, db_session: Session, github_api
) -> None:
    """DPDP. A submission is what starts the repository analysis, so it cannot
    proceed on a consent record that does not exist."""
    token, profile = _register(db_session, "no.consent@example.com")
    client.put(f"{PROFILE_BASE}/sections/basic", json=VALID_BASIC, headers=_auth(token))
    _connect_github(client, token)
    client.post(
        f"{GITHUB_BASE}/repos/select",
        json={"repo_full_names": ["ada/payments-api"]},
        headers=_auth(token),
    )

    # Everything else is done — this is a consent failure, not an incomplete
    # profile.
    assert _state(client, token)["can_submit"] is True

    refused = client.post(f"{PROFILE_BASE}/submit", json={"consent": False}, headers=_auth(token))
    # 422, not 409: a `false` consent is a malformed submission rather than a
    # profile that is not ready.
    assert refused.status_code == 422, refused.text

    missing = client.post(f"{PROFILE_BASE}/submit", json={}, headers=_auth(token))
    assert missing.status_code == 422, missing.text

    db_session.refresh(profile)
    assert profile.onboarding_submitted_at is None
    assert profile.onboarding_consent_at is None


def test_a_coding_profile_is_never_required(
    client: TestClient, db_session: Session, github_api
) -> None:
    """The regression test for the section split, at the HTTP layer.

    A competitive-programming handle used to be mandatory, back when GitHub and
    coding profiles were one `technical` section. It is a supporting signal
    this platform refuses to treat as a verified skill, so gating the entire
    product on one was gating it on a number it does not believe.
    """
    token, _profile = _register(db_session, "no.handle@example.com")
    client.put(f"{PROFILE_BASE}/sections/basic", json=VALID_BASIC, headers=_auth(token))
    _connect_github(client, token)
    client.post(
        f"{GITHUB_BASE}/repos/select",
        json={"repo_full_names": ["ada/payments-api"]},
        headers=_auth(token),
    )

    state = _state(client, token)
    assert state["can_submit"] is True
    assert _step(state, "coding")["is_mandatory"] is False

    resp = client.post(f"{PROFILE_BASE}/submit", json={"consent": True}, headers=_auth(token))
    assert resp.status_code == 200, resp.text


def test_submitting_twice_is_idempotent(
    client: TestClient, db_session: Session, github_api
) -> None:
    """The review stage is a URL a student can reach twice, and a double-click
    must not be an error."""
    token, profile = _register(db_session, "twice@example.com")
    client.put(f"{PROFILE_BASE}/sections/basic", json=VALID_BASIC, headers=_auth(token))
    _connect_github(client, token)
    client.post(
        f"{GITHUB_BASE}/repos/select",
        json={"repo_full_names": ["ada/payments-api"]},
        headers=_auth(token),
    )

    first = client.post(f"{PROFILE_BASE}/submit", json={"consent": True}, headers=_auth(token))
    assert first.status_code == 200, first.text
    second = client.post(f"{PROFILE_BASE}/submit", json={"consent": True}, headers=_auth(token))
    assert second.status_code == 200, second.text

    # Same timestamp both times — the second call re-reported the first, it did
    # not re-submit.
    assert first.json()["submitted_at"] == second.json()["submitted_at"]
    # And it queued nothing a second time.
    assert second.json()["queued_verifications"] == 0

    db_session.refresh(profile)
    assert profile.onboarding_consent_at is not None


def test_target_roles_are_capped_and_deduplicated(client: TestClient, db_session: Session) -> None:
    """One to three, and order carries meaning — the first becomes the primary
    role the matcher indexes, so a repeat is rejected rather than collapsed."""
    token, _profile = _register(db_session, "roles@example.com")

    too_many = client.put(
        f"{PROFILE_BASE}/sections/basic",
        json={**VALID_BASIC, "target_roles": ["backend", "frontend", "devops", "qa"]},
        headers=_auth(token),
    )
    assert too_many.status_code == 422, too_many.text

    none_at_all = client.put(
        f"{PROFILE_BASE}/sections/basic",
        json={**VALID_BASIC, "target_roles": []},
        headers=_auth(token),
    )
    assert none_at_all.status_code == 422, none_at_all.text

    duplicated = client.put(
        f"{PROFILE_BASE}/sections/basic",
        json={**VALID_BASIC, "target_roles": ["backend", "backend"]},
        headers=_auth(token),
    )
    assert duplicated.status_code == 422, duplicated.text

    # The derived scalar cannot be supplied — `extra="forbid"` on the request.
    smuggled = client.put(
        f"{PROFILE_BASE}/sections/basic",
        json={**VALID_BASIC, "target_role": "devops"},
        headers=_auth(token),
    )
    assert smuggled.status_code == 422, smuggled.text


def test_the_coding_endpoint_cannot_disturb_the_github_account(
    client: TestClient, db_session: Session, github_api
) -> None:
    """Stage 4 saves the optional section beside the mandatory one. It must not
    be able to retire the GitHub row the previous stage connected."""
    token, profile = _register(db_session, "coding.isolation@example.com")
    _connect_github(client, token)

    resp = client.put(
        f"{PROFILE_BASE}/sections/coding",
        json={"coding_profiles": [{"platform": "leetcode", "handle": "ada_lovelace"}]},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    account = resp.json()["data"]["github_account"]
    assert account["github_username"] == "ada"
    # Still OAuth-verified: the coding save did not touch it.
    assert account["verification_status"] == VerificationStatus.VERIFIED.value

    # And clearing the handles again leaves it alone.
    cleared = client.put(
        f"{PROFILE_BASE}/sections/coding", json={"coding_profiles": []}, headers=_auth(token)
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["github_account"]["github_username"] == "ada"
