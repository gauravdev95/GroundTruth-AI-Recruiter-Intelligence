"""Integration tests for the GitHub OAuth connect flow
(`domains/student/github_oauth.py`, `domains/student/github_router.py`).

`github_client.exchange_code_for_token`/`get_user_authenticated`/`list_user_repos`
are monkeypatched — this is not a test of GitHub's OAuth server, it's a test
of the state machine: `/connect` requires the caller's own token, `/callback`
resolves the candidate from a signed `state` (not from any session cookie,
since GitHub's redirect carries none), an OAuth-verified account is written
straight to `VERIFIED`, and repo selection reuses the ordinary projects
section service.
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
from src.domains.student.models import GithubAccount, Project, VerificationStatus
from src.domains.verification.clients import github as github_client

GITHUB_BASE = "/api/v1/student/github"

_TEST_GITHUB_OAUTH_SETTINGS = GitHubOAuthSettings(
    github_client_id="test-client-id", github_client_secret="test-secret"
)


@pytest.fixture(autouse=True)
def configured_github_oauth(monkeypatch):
    """`get_github_oauth_settings().is_configured` gates every endpoint here.

    Patched at each *call site*, not at `src.config.config` — both
    `github_oauth.py` and `clients/github.py` did `from ... import
    get_github_oauth_settings`, which binds a local name at import time that
    patching the origin module's attribute afterward would not affect.
    """
    monkeypatch.setattr(
        "src.domains.student.github_oauth.get_github_oauth_settings",
        lambda: _TEST_GITHUB_OAUTH_SETTINGS,
    )
    monkeypatch.setattr(
        "src.domains.verification.clients.github.get_github_oauth_settings",
        lambda: _TEST_GITHUB_OAUTH_SETTINGS,
    )


@pytest.fixture(autouse=True)
def stub_broker(monkeypatch):
    monkeypatch.setattr("src.jobs.dispatch.dispatch", lambda job, task, *, queue, args=None: None)


def _candidate(db_session: Session, email: str = "gh.oauth@example.com") -> tuple[str, CandidateProfile]:
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


def _extract_state(authorize_url: str) -> str:
    return parse_qs(urlparse(authorize_url).query)["state"][0]


def test_connect_requires_authentication(client: TestClient) -> None:
    assert client.get(f"{GITHUB_BASE}/connect").status_code == 401


def test_connect_returns_an_authorize_url_carrying_a_signed_state(
    client: TestClient, db_session: Session
) -> None:
    token, _profile = _candidate(db_session)
    resp = client.get(f"{GITHUB_BASE}/connect", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    authorize_url = resp.json()["authorize_url"]
    assert authorize_url.startswith("https://github.com/login/oauth/authorize")
    assert _extract_state(authorize_url)  # non-empty


def test_callback_with_missing_code_redirects_with_error(client: TestClient) -> None:
    resp = client.get(f"{GITHUB_BASE}/callback", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "github=error" in resp.headers["location"]


def test_callback_connects_the_account_as_verified(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    token, profile = _candidate(db_session, "callback.success@example.com")
    connect_resp = client.get(f"{GITHUB_BASE}/connect", headers=_auth(token))
    state = _extract_state(connect_resp.json()["authorize_url"])

    monkeypatch.setattr(
        github_client, "exchange_code_for_token", lambda code: ("gho_faketoken", "read:user,public_repo")
    )
    monkeypatch.setattr(
        github_client,
        "get_user_authenticated",
        lambda tok: {"id": 999, "login": "ada", "html_url": "https://github.com/ada", "public_repos": 5, "followers": 2},
    )

    resp = client.get(f"{GITHUB_BASE}/callback", params={"code": "abc", "state": state}, follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "github=connected" in resp.headers["location"]

    account = db_session.execute(
        select(GithubAccount).where(GithubAccount.candidate_profile_id == profile.id)
    ).scalar_one()
    assert account.verification_status is VerificationStatus.VERIFIED
    assert account.verification_source == "github_oauth"
    assert account.github_username == "ada"
    assert account.github_user_id == 999
    assert account.access_token_encrypted is not None
    assert account.access_token_encrypted != "gho_faketoken"  # actually encrypted, not stored raw


def test_callback_with_invalid_state_redirects_with_error(client: TestClient) -> None:
    resp = client.get(
        f"{GITHUB_BASE}/callback", params={"code": "abc", "state": "not-a-real-token"}, follow_redirects=False
    )
    assert resp.status_code in (302, 307)
    assert "github=error" in resp.headers["location"]


def test_repos_requires_a_connected_account(client: TestClient, db_session: Session) -> None:
    token, _profile = _candidate(db_session, "not.connected@example.com")
    resp = client.get(f"{GITHUB_BASE}/repos", headers=_auth(token))
    assert resp.status_code == 409


def test_select_repos_writes_projects_and_queues_verification(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    token, profile = _candidate(db_session, "picker@example.com")
    connect_resp = client.get(f"{GITHUB_BASE}/connect", headers=_auth(token))
    state = _extract_state(connect_resp.json()["authorize_url"])
    monkeypatch.setattr(
        github_client, "exchange_code_for_token", lambda code: ("gho_faketoken", "read:user,public_repo")
    )
    monkeypatch.setattr(
        github_client,
        "get_user_authenticated",
        lambda tok: {"id": 1, "login": "ada", "html_url": "https://github.com/ada"},
    )
    client.get(f"{GITHUB_BASE}/callback", params={"code": "abc", "state": state}, follow_redirects=False)

    resp = client.post(
        f"{GITHUB_BASE}/repos/select",
        json={"repo_full_names": ["ada/compiler", "ada/analytical-engine"]},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    titles = {p["title"] for p in resp.json()["data"]["projects"]}
    assert titles == {"compiler", "analytical-engine"}

    projects = db_session.execute(select(Project).where(Project.candidate_profile_id == profile.id)).scalars().all()
    assert len(projects) == 2
    # Queued for verification (like any repo URL, manually typed or picked)
    # — `evidence.queue_project_repository` sets PENDING, not UNVERIFIED;
    # the actual check never runs here since `stub_broker` never dispatches it.
    assert all(p.verification_status is VerificationStatus.PENDING for p in projects)


def test_select_repos_rejects_more_than_the_project_cap(client: TestClient, db_session: Session) -> None:
    token, _profile = _candidate(db_session, "toomany@example.com")
    resp = client.post(
        f"{GITHUB_BASE}/repos/select",
        json={"repo_full_names": ["a/one", "a/two", "a/three", "a/four"]},
        headers=_auth(token),
    )
    assert resp.status_code == 422
