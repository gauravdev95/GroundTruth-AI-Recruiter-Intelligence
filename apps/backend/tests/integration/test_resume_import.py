"""Integration tests for the resume import flow.

Object storage and the LLM are stubbed — the point is the flow around them:
authorization, the 202-with-job-id contract, that extraction lands in a DRAFT
row and nowhere else, and that confirming writes through the ordinary section
services (recomputing strength and queueing verification jobs).

The worker task is invoked directly rather than through a broker: Celery's own
dispatch is not under test here, and running it in-process keeps the assertions
about database state honest.
"""

from __future__ import annotations

import io
import uuid

import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domains.ai.exceptions import LLMProviderError, LLMRefused
from src.domains.ai.extraction_schema import ResumeExtraction
from src.domains.auth import service as auth_service
from src.domains.auth.models import CandidateProfile
from src.domains.auth.schemas import CandidateRegisterRequest, RecruiterRegisterRequest
from src.domains.auth.security import create_access_token
from src.domains.resume.models import (
    ResumeDraftStatus,
    ResumeExtractionDraft,
    ResumeUpload,
    ResumeUploadStatus,
)
from src.domains.student.models import CodingPlatformAccount, GithubAccount
from src.platform.models import AsyncJob, AsyncJobStatus

BASE = "/api/v1/student/resume"

RESUME_TEXT = (
    "Ada Lovelace — Final-year Computer Science student at IIT Bombay, graduating 2026. "
    "Backend engineering intern at Acme Corp. github.com/ada, leetcode.com/u/ada_lc. "
    "Built a toy compiler in Rust and a distributed cache in Go."
)

EXTRACTION = ResumeExtraction.model_validate(
    {
        "contact": {
            # Required, because `full_name` is a required field of profile
            # section 1 and `confirm.py::suggest_sections` only forwards it
            # when the extraction supplies one. A fixture without it produces
            # a `basic` block the student cannot confirm — the review screen
            # rejects its own suggestions — which is a fixture bug, not a
            # product one: the real extractor does read a name off the
            # document header (`extraction/entries.py`).
            "full_name": "Ada Lovelace",
            "headline": "Final-year CS student building compilers",
            "location": "Mumbai, India",
            "github_username": "ada",
            "leetcode_handle": "ada_lc",
        },
        "education": [
            {
                "institution": "IIT Bombay",
                "degree": "B.Tech",
                "field_of_study": "Computer Science",
                "graduation_year": 2026,
            }
        ],
        "skills": ["Python", "Rust"],
        "projects": [
            {
                "title": "Toy compiler",
                "repo_url": "https://github.com/ada/compiler",
                "technologies": ["Rust"],
            }
        ],
        "experience": [
            {
                "company_name": "Acme Corp",
                "title": "Backend Engineering Intern",
                "employment_type": "internship",
                "start_date": "2025-06-01",
                "end_date": "2025-08-31",
                "technologies": ["Python"],
            }
        ],
        "certificates": [
            {
                "title": "AWS Solutions Architect",
                "issuer": "Amazon",
                "credential_url": "https://credly.com/badges/abc",
            }
        ],
    }
)


def _docx_bytes(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _candidate_token(db_session: Session, email: str = "resume.student@example.com") -> str:
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


def _recruiter_token(db_session: Session, email: str = "resume.recruiter@acme.com") -> str:
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
        select(CandidateProfile).where(CandidateProfile.user.has(email=email))
    ).scalar_one()


@pytest.fixture(autouse=True)
def stub_broker(monkeypatch):
    """Don't publish to a real broker.

    These tests drive the task body directly, so Celery's dispatch is not under
    test. Stubbing it keeps them runnable without Redis and keeps assertions
    about `async_jobs` state deterministic.
    """
    monkeypatch.setattr("src.jobs.dispatch.dispatch", lambda job, task, *, queue, args=None: None)


class _SessionProxy:
    """Context manager that yields the test session without closing it.

    The worker deliberately opens its own `SessionLocal()` sessions so status
    writes survive a rollback in the business-logic session — correct in
    production, but invisible to `conftest`'s single rolled-back transaction.
    Pointing the worker at the test session bridges that without weakening the
    production code.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def __enter__(self) -> Session:
        return self._session

    def __exit__(self, *_: object) -> bool:
        return False


@pytest.fixture(autouse=True)
def worker_sessions(monkeypatch, db_session: Session):
    factory = lambda: _SessionProxy(db_session)  # noqa: E731
    monkeypatch.setattr("src.jobs.tasks.resume.SessionLocal", factory)
    monkeypatch.setattr("src.jobs.celery_app.SessionLocal", factory)


@pytest.fixture()
def stub_storage(monkeypatch):
    """In-memory object store keyed by the same object keys the service builds."""
    store: dict[str, bytes] = {}

    def _upload(fileobj, *, key, content_type):
        store[key] = fileobj.read()

    monkeypatch.setattr("src.domains.storage.client.upload_fileobj", _upload)
    monkeypatch.setattr("src.domains.storage.client.download_bytes", lambda key: store[key])
    monkeypatch.setattr("src.domains.storage.client.delete_object", lambda key: store.pop(key, None))
    return store


@pytest.fixture()
def stub_extractor(monkeypatch):
    """Replace the LLM with a deterministic stub. Raise `.error` to test failures."""

    class _Stub:
        def __init__(self) -> None:
            self.error: Exception | None = None
            self.calls = 0

        def extract_resume(self, text: str) -> ResumeExtraction:
            self.calls += 1
            if self.error is not None:
                raise self.error
            return EXTRACTION

    stub = _Stub()
    monkeypatch.setattr("src.jobs.tasks.resume.get_resume_extractor", lambda: stub)
    return stub


def _upload_resume(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post(
        f"{BASE}/uploads",
        files={
            "file": (
                "resume.docx",
                _docx_bytes(RESUME_TEXT),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=headers,
    )
    assert response.status_code == 202, response.text
    return response.json()


def _run_extraction(async_job_id: str) -> None:
    """Invoke the task body in-process, bypassing the broker."""
    from src.jobs.tasks.resume import extract_resume_task

    extract_resume_task.run(async_job_id)


# --------------------------------------------------------------------------
# Authorization
# --------------------------------------------------------------------------


def test_upload_requires_authentication(client: TestClient) -> None:
    assert client.post(f"{BASE}/uploads").status_code == 401
    assert client.get(f"{BASE}/uploads").status_code == 401


def test_recruiter_is_forbidden(client: TestClient, db_session: Session) -> None:
    headers = _auth(_recruiter_token(db_session))

    resp = client.get(f"{BASE}/uploads", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_candidate_cannot_read_another_students_draft(
    client: TestClient, db_session: Session, stub_storage, stub_extractor
) -> None:
    first = _auth(_candidate_token(db_session, "owner.resume@example.com"))
    second = _auth(_candidate_token(db_session, "other.resume@example.com"))

    accepted = _upload_resume(client, first)
    _run_extraction(accepted["async_job_id"])

    draft_id = client.get(
        f"{BASE}/uploads/{accepted['upload']['id']}/draft", headers=first
    ).json()["draft"]["id"]

    # Scoped by profile in the query — another student's draft is simply absent.
    assert client.get(f"{BASE}/drafts/{draft_id}", headers=second).status_code == 404


def test_job_status_is_scoped_to_its_owner(
    client: TestClient, db_session: Session, stub_storage, stub_extractor
) -> None:
    first = _auth(_candidate_token(db_session, "jobowner@example.com"))
    second = _auth(_candidate_token(db_session, "jobsnooper@example.com"))

    accepted = _upload_resume(client, first)
    job_id = accepted["async_job_id"]

    assert client.get(f"/api/v1/jobs/{job_id}", headers=first).status_code == 200
    assert client.get(f"/api/v1/jobs/{job_id}", headers=second).status_code == 403


# --------------------------------------------------------------------------
# Upload contract
# --------------------------------------------------------------------------


def test_upload_returns_202_without_doing_the_work(
    client: TestClient, db_session: Session, stub_storage, stub_extractor
) -> None:
    """No user request may block on parsing or an LLM call."""
    headers = _auth(_candidate_token(db_session))

    accepted = _upload_resume(client, headers)

    assert accepted["upload"]["status"] == "uploaded"
    assert accepted["async_job_id"]
    # The request returned before the extractor was ever consulted.
    assert stub_extractor.calls == 0

    job = client.get(f"/api/v1/jobs/{accepted['async_job_id']}", headers=headers).json()
    assert job["status"] == "pending"
    assert job["job_type"] == "extract_resume"


def test_unsupported_file_type_is_rejected(
    client: TestClient, db_session: Session, stub_storage
) -> None:
    headers = _auth(_candidate_token(db_session))

    resp = client.post(
        f"{BASE}/uploads",
        files={"file": ("notes.txt", b"just some text", "text/plain")},
        headers=headers,
    )

    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_oversized_upload_is_rejected(
    client: TestClient, db_session: Session, stub_storage, monkeypatch
) -> None:
    # Patched where it is *used*: `service` imported the function by name, so
    # rebinding it on `config` would leave the service's reference untouched.
    monkeypatch.setattr(
        "src.domains.resume.service.get_storage_settings",
        lambda: type("S", (), {"resume_max_bytes": 10, "s3_resume_bucket": "b"})(),
    )
    headers = _auth(_candidate_token(db_session))

    resp = client.post(
        f"{BASE}/uploads",
        files={
            "file": (
                "resume.docx",
                _docx_bytes(RESUME_TEXT),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=headers,
    )

    assert resp.status_code == 413


# --------------------------------------------------------------------------
# Extraction lands in a DRAFT, never in a live table
# --------------------------------------------------------------------------


def test_extraction_writes_a_draft_and_touches_no_profile_table(
    client: TestClient, db_session: Session, stub_storage, stub_extractor
) -> None:
    email = "draftonly@example.com"
    headers = _auth(_candidate_token(db_session, email))

    accepted = _upload_resume(client, headers)
    _run_extraction(accepted["async_job_id"])

    profile = _profile(db_session, email)
    db_session.expire_all()

    draft = db_session.execute(
        select(ResumeExtractionDraft).where(
            ResumeExtractionDraft.candidate_profile_id == profile.id
        )
    ).scalar_one()
    assert draft.status is ResumeDraftStatus.PENDING_REVIEW
    assert draft.payload["contact"]["github_username"] == "ada"

    # The extraction named a college, a GitHub account and a certificate — none
    # of it reached a live table.
    assert profile.college is None
    assert profile.profile_strength == 0
    assert profile.is_discoverable is False
    assert (
        db_session.execute(
            select(GithubAccount).where(GithubAccount.candidate_profile_id == profile.id)
        ).first()
        is None
    )


def test_job_and_upload_reach_terminal_success_state(
    client: TestClient, db_session: Session, stub_storage, stub_extractor
) -> None:
    headers = _auth(_candidate_token(db_session))

    accepted = _upload_resume(client, headers)
    _run_extraction(accepted["async_job_id"])
    db_session.expire_all()

    upload = db_session.get(ResumeUpload, uuid.UUID(accepted["upload"]["id"]))
    assert upload.status is ResumeUploadStatus.EXTRACTED
    assert upload.error is None


def test_draft_endpoint_returns_server_mapped_suggestions(
    client: TestClient, db_session: Session, stub_storage, stub_extractor
) -> None:
    headers = _auth(_candidate_token(db_session))

    accepted = _upload_resume(client, headers)
    _run_extraction(accepted["async_job_id"])

    body = client.get(f"{BASE}/uploads/{accepted['upload']['id']}/draft", headers=headers).json()

    assert body["suggestions"]["basic"]["degree"] == "btech"
    assert body["suggestions"]["basic"]["branch"] == "cse"
    assert body["suggestions"]["technical"]["github_username"] == "ada"
    assert body["suggestions"]["projects"][0]["kind"] == "repository"
    # Honest about what a resume cannot supply.
    assert any("Target role" in note for note in body["suggestions"]["unmapped"])


# --------------------------------------------------------------------------
# Failure handling
# --------------------------------------------------------------------------


def test_scanned_document_fails_permanently_without_calling_the_llm(
    client: TestClient, db_session: Session, stub_storage, stub_extractor, monkeypatch
) -> None:
    """A file with no text layer is deterministic — never retried, never billed."""
    from src.jobs.celery_app import NonRetryableJobError

    headers = _auth(_candidate_token(db_session))
    accepted = _upload_resume(client, headers)

    monkeypatch.setattr(
        "src.jobs.tasks.resume.extract_text",
        lambda data, content_type: (_ for _ in ()).throw(
            __import__(
                "src.domains.resume.parsing", fromlist=["NoTextContent"]
            ).NoTextContent("No readable text was found.")
        ),
    )

    with pytest.raises(NonRetryableJobError):
        _run_extraction(accepted["async_job_id"])

    assert stub_extractor.calls == 0
    db_session.expire_all()
    upload = db_session.get(ResumeUpload, uuid.UUID(accepted["upload"]["id"]))
    assert upload.status is ResumeUploadStatus.FAILED
    assert "No readable text" in upload.error


def test_llm_refusal_is_not_retried(
    client: TestClient, db_session: Session, stub_storage, stub_extractor
) -> None:
    from src.jobs.celery_app import NonRetryableJobError

    headers = _auth(_candidate_token(db_session))
    accepted = _upload_resume(client, headers)
    stub_extractor.error = LLMRefused("declined")

    with pytest.raises(NonRetryableJobError):
        _run_extraction(accepted["async_job_id"])

    db_session.expire_all()
    upload = db_session.get(ResumeUpload, uuid.UUID(accepted["upload"]["id"]))
    assert upload.status is ResumeUploadStatus.FAILED


def test_transient_llm_error_propagates_for_retry(
    client: TestClient, db_session: Session, stub_storage, stub_extractor
) -> None:
    """A provider outage must reach Celery's backoff ladder, not fail the job."""
    from src.jobs.celery_app import NonRetryableJobError

    headers = _auth(_candidate_token(db_session))
    accepted = _upload_resume(client, headers)
    stub_extractor.error = LLMProviderError("upstream 503")

    with pytest.raises(LLMProviderError):
        _run_extraction(accepted["async_job_id"])

    db_session.expire_all()
    upload = db_session.get(ResumeUpload, uuid.UUID(accepted["upload"]["id"]))
    # Left PROCESSING so the UI keeps showing work in flight during backoff.
    assert upload.status is ResumeUploadStatus.PROCESSING


# --------------------------------------------------------------------------
# Confirm: the only path into live profile tables
# --------------------------------------------------------------------------


def test_confirm_writes_through_the_section_services(
    client: TestClient, db_session: Session, stub_storage, stub_extractor
) -> None:
    """Strength recomputes and evidence queues — proof the section services ran."""
    email = "confirming@example.com"
    headers = _auth(_candidate_token(db_session, email))

    accepted = _upload_resume(client, headers)
    _run_extraction(accepted["async_job_id"])
    detail = client.get(f"{BASE}/uploads/{accepted['upload']['id']}/draft", headers=headers).json()
    draft_id = detail["draft"]["id"]

    resp = client.post(
        f"{BASE}/drafts/{draft_id}/confirm",
        json={
            "basic": {
                **detail["suggestions"]["basic"],
                "target_roles": ["backend"],  # the student supplies what the resume can't
            },
            "technical": detail["suggestions"]["technical"],
        },
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["draft"]["status"] == "confirmed"
    # Recomputed by the shared completeness code (`student/completeness.py`):
    #   basic  35 — all seven fields, `target_roles` supplied above
    #   github 15 — the account exists; verification is tracked separately and
    #                deliberately does not move `profile_strength`
    #   coding  5 — one platform handle (leetcode) out of two counted
    #        = 55
    # The old expectation of 65 predates `technical` (30) being split into the
    # mandatory `github` (15) and `projects` (20) sections — this confirm
    # supplies no projects, so those 20 points were never earned.
    assert body["completeness"]["profile_strength"] == 55
    # Still `False`, and correctly so: there are now *three* mandatory sections
    # — basic, github and projects — and this confirm supplies no projects. The
    # old expectation of `True` dates from when `technical` was one mandatory
    # section covering both. A resume confirm alone does not make a student
    # eligible; the projects section is the one that gives the evidence
    # pipeline something to verify.
    assert body["completeness"]["meets_section_requirements"] is False
    assert body["completeness"]["is_discoverable"] is False

    profile = _profile(db_session, email)
    db_session.expire_all()
    assert profile.college == "IIT Bombay"

    # Confirming a GitHub username queued its verification job, exactly as a
    # manual section PUT would have.
    github = db_session.execute(
        select(GithubAccount).where(GithubAccount.candidate_profile_id == profile.id)
    ).scalar_one()
    assert github.verification_status.value == "pending"
    assert (
        db_session.execute(
            select(AsyncJob).where(AsyncJob.job_type == "verify_github_account")
        ).first()
        is not None
    )
    assert (
        db_session.execute(
            select(CodingPlatformAccount).where(
                CodingPlatformAccount.candidate_profile_id == profile.id
            )
        ).scalar_one().handle
        == "ada_lc"
    )


def test_confirm_rejects_payloads_the_section_schemas_reject(
    client: TestClient, db_session: Session, stub_storage, stub_extractor
) -> None:
    """Confirmed data is subject to the same validation as a hand-typed PUT."""
    headers = _auth(_candidate_token(db_session))
    accepted = _upload_resume(client, headers)
    _run_extraction(accepted["async_job_id"])
    detail = client.get(f"{BASE}/uploads/{accepted['upload']['id']}/draft", headers=headers).json()
    draft_id = detail["draft"]["id"]

    # `extra="forbid"` on the shared section schema blocks the smuggle.
    smuggled = client.post(
        f"{BASE}/drafts/{draft_id}/confirm",
        json={
            "basic": {
                **detail["suggestions"]["basic"],
                "target_roles": ["backend"],
                "profile_strength": 100,
            }
        },
        headers=headers,
    )
    assert smuggled.status_code == 422

    incomplete = client.post(
        f"{BASE}/drafts/{draft_id}/confirm",
        json={"basic": {"headline": "Only a headline"}},
        headers=headers,
    )
    assert incomplete.status_code == 422


def test_confirm_requires_at_least_one_section(
    client: TestClient, db_session: Session, stub_storage, stub_extractor
) -> None:
    headers = _auth(_candidate_token(db_session))
    accepted = _upload_resume(client, headers)
    _run_extraction(accepted["async_job_id"])
    draft_id = client.get(
        f"{BASE}/uploads/{accepted['upload']['id']}/draft", headers=headers
    ).json()["draft"]["id"]

    assert client.post(f"{BASE}/drafts/{draft_id}/confirm", json={}, headers=headers).status_code == 422


def test_draft_cannot_be_confirmed_twice(
    client: TestClient, db_session: Session, stub_storage, stub_extractor
) -> None:
    headers = _auth(_candidate_token(db_session, "twice@example.com"))
    accepted = _upload_resume(client, headers)
    _run_extraction(accepted["async_job_id"])
    detail = client.get(f"{BASE}/uploads/{accepted['upload']['id']}/draft", headers=headers).json()
    draft_id = detail["draft"]["id"]
    payload = {"technical": detail["suggestions"]["technical"]}

    assert client.post(f"{BASE}/drafts/{draft_id}/confirm", json=payload, headers=headers).status_code == 200
    second = client.post(f"{BASE}/drafts/{draft_id}/confirm", json=payload, headers=headers)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "CONFLICT"


def test_discarded_draft_cannot_be_confirmed(
    client: TestClient, db_session: Session, stub_storage, stub_extractor
) -> None:
    headers = _auth(_candidate_token(db_session, "discarding@example.com"))
    accepted = _upload_resume(client, headers)
    _run_extraction(accepted["async_job_id"])
    detail = client.get(f"{BASE}/uploads/{accepted['upload']['id']}/draft", headers=headers).json()
    draft_id = detail["draft"]["id"]

    assert client.post(f"{BASE}/drafts/{draft_id}/discard", headers=headers).status_code == 200
    resp = client.post(
        f"{BASE}/drafts/{draft_id}/confirm",
        json={"technical": detail["suggestions"]["technical"]},
        headers=headers,
    )
    assert resp.status_code == 409


def test_partial_confirm_leaves_other_sections_untouched(
    client: TestClient, db_session: Session, stub_storage, stub_extractor
) -> None:
    """Confirming is additive review, not a profile reset."""
    email = "partial@example.com"
    headers = _auth(_candidate_token(db_session, email))
    accepted = _upload_resume(client, headers)
    _run_extraction(accepted["async_job_id"])
    detail = client.get(f"{BASE}/uploads/{accepted['upload']['id']}/draft", headers=headers).json()

    resp = client.post(
        f"{BASE}/drafts/{detail['draft']['id']}/confirm",
        json={"technical": detail["suggestions"]["technical"]},
        headers=headers,
    )

    assert resp.status_code == 200
    profile = _profile(db_session, email)
    db_session.expire_all()
    # Only the technical section was confirmed, so basic is still empty — the
    # point of the test: confirming one section leaves the others alone.
    assert profile.college is None
    # github 15 (the account) + coding 5 (one leetcode handle) = 20.
    # Was 30 when `technical` was a single 30-point section; it is now split
    # into github (15) and projects (20), and this confirm carries no projects.
    assert resp.json()["completeness"]["profile_strength"] == 20
    assert resp.json()["completeness"]["is_discoverable"] is False
