"""GitHub OAuth connect flow + repository picker.

Separate from `router.py` (the section GET/PUT endpoints) for the same
reason `resume/router.py` is separate: a distinct sub-flow with its own
external dependency, not another profile section.

`/connect` and `/callback` are unauthenticated-shaped on the wire (GitHub's
redirect carries no bearer token) but are not open endpoints: `/connect`
requires the caller's own access token to mint a `state` naming *their*
`candidate_profile_id`, and `/callback` trusts nothing except what that
signed `state` says — see `github_oauth.py` module docstring.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.config import get_security_settings
from src.core.crypto import decrypt_secret
from src.core.exceptions import Conflict
from src.db.database import get_db
from src.domains.auth.models import CandidateProfile
from src.domains.auth.rate_limit import limiter
from src.domains.student import github_oauth
from src.domains.student import service as student_service
from src.domains.student.dependencies import get_own_profile
from src.domains.student.models import GithubAccount
from src.domains.student.router import _completeness_response
from src.domains.student.schemas import MAX_PROJECTS, ProjectResponse, ProjectsResponse, SectionEnvelope
from src.domains.verification.clients import github as github_client
from src.domains.verification.exceptions import VerificationServiceUnavailable

router = APIRouter(prefix="/api/v1/student/github", tags=["student-github"])


class ConnectUrlResponse(BaseModel):
    authorize_url: str


class GithubRepoResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: str
    name: str
    description: str | None = None
    language: str | None = None
    fork: bool = False
    private: bool = False
    stargazers_count: int = 0
    updated_at: str | None = None


class GithubRepoListResponse(BaseModel):
    repos: list[GithubRepoResponse]


class SelectReposRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo_full_names: list[str] = Field(min_length=1, max_length=MAX_PROJECTS)


@router.get("/connect", response_model=ConnectUrlResponse)
def connect(profile: CandidateProfile = Depends(get_own_profile)) -> ConnectUrlResponse:
    """Returns the GitHub authorize URL for the frontend to redirect to —
    a JSON response rather than a 302, since this is called via `fetch`/axios
    from an already-loaded page, not a browser-initiated navigation."""
    return ConnectUrlResponse(authorize_url=github_oauth.build_connect_url(profile.id))


@router.get("/callback")
def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """GitHub redirects the browser here directly — this endpoint always
    ends in a redirect back to the frontend, never a JSON error response,
    the same shape `auth/router.py::google_callback` uses."""
    settings = get_security_settings()
    target = f"{settings.frontend_base_url}/candidate/profile"

    if error or not code or not state:
        return RedirectResponse(f"{target}?github=error")

    try:
        github_oauth.handle_callback(db, code=code, state=state)
    except (github_oauth.GitHubOAuthError, github_oauth.GitHubOAuthNotConfigured, VerificationServiceUnavailable):
        return RedirectResponse(f"{target}?github=error")

    return RedirectResponse(f"{target}?github=connected")


@router.get("/repos", response_model=GithubRepoListResponse)
def list_repos(
    profile: CandidateProfile = Depends(get_own_profile), db: Session = Depends(get_db)
) -> GithubRepoListResponse:
    """The connected account's repositories, for the picker UI. 409s (via the
    typed error below) if GitHub isn't connected yet — the frontend shows
    the connect button in that case rather than an empty list."""
    account = db.execute(
        select(GithubAccount).where(
            GithubAccount.candidate_profile_id == profile.id,
            GithubAccount.deleted_at.is_(None),
            GithubAccount.access_token_encrypted.is_not(None),
        )
    ).scalar_one_or_none()
    if account is None or account.access_token_encrypted is None:
        raise Conflict("Connect a GitHub account before listing repositories")

    token = decrypt_secret(account.access_token_encrypted)
    if token is None:
        raise Conflict("GitHub connection is no longer valid; please reconnect")

    repos = github_client.list_user_repos(token)
    return GithubRepoListResponse(repos=[GithubRepoResponse.model_validate(r) for r in repos])


@router.post("/repos/select", response_model=SectionEnvelope[ProjectsResponse])
@limiter.limit("10/hour")
def select_repos(
    request: Request,
    payload: SelectReposRequest,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> SectionEnvelope[ProjectsResponse]:
    """Writes the chosen repositories through the ordinary projects section
    service — see `student/service.py::set_projects_from_github` for why."""
    completeness = student_service.set_projects_from_github(
        db, profile, selected_full_names=payload.repo_full_names
    )
    projects = student_service.load_snapshot(db, profile).projects
    return SectionEnvelope(
        data=ProjectsResponse(projects=[ProjectResponse.model_validate(p) for p in projects]),
        completeness=_completeness_response(completeness),
    )
