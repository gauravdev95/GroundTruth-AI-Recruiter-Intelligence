"""Integration tests for the profile setup entry screen.

Covers the one endpoint the screen renders from (`GET .../setup-state`) and the
upload validation that guards the resume path. Everything asserted here is a
derivation from persisted rows — the point of these tests is that the screen has
no state of its own to get wrong.

Accounts are created through `domains.auth.service` (the OTP is never exposed
over HTTP) and every assertion then goes through the real endpoints, so auth,
validation and the error envelope are exercised for real.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domains.auth import service as auth_service
from src.domains.auth.models import CandidateProfile
from src.domains.auth.schemas import CandidateRegisterRequest, RecruiterRegisterRequest
from src.domains.auth.security import create_access_token
from src.domains.resume.models import ResumeUpload, ResumeUploadStatus

PROFILE_BASE = "/api/v1/student/profile"
RESUME_BASE = "/api/v1/student/resume"
SETUP_STATE = f"{PROFILE_BASE}/setup-state"

VALID_BASIC = {
    "headline": "Final-year CS student building compilers",
    "college": "IIT Bombay",
    "degree": "btech",
    "branch": "cse",
    "graduation_year": 2026,
    "location": "Mumbai, India",
    "target_role": "backend",
}

VALID_TECHNICAL = {
    "github_username": "ada",
    "coding_profiles": [{"platform": "leetcode", "handle": "ada_lovelace"}],
}

EXPECTED_STEP_KEYS = ["basic", "technical", "projects", "certificates", "experience"]
EXPECTED_STEP_TITLES = [
    "Basic Information",
    "Technical Profiles",
    "Projects",
    "Certificates & Achievements",
    "Experience",
]


@pytest.fixture(autouse=True)
def stub_broker(monkeypatch):
    """Section saves dispatch verification jobs after commit; these tests assert
    on database state rather than on Celery's publish path."""
    monkeypatch.setattr("src.jobs.dispatch.dispatch", lambda job, task, *, queue, args=None: None)


@pytest.fixture()
def stub_storage(monkeypatch):
    store: dict[str, bytes] = {}

    def _upload(fileobj, *, key, content_type):
        store[key] = fileobj.read()

    monkeypatch.setattr("src.domains.storage.client.upload_fileobj", _upload)
    monkeypatch.setattr("src.domains.storage.client.download_bytes", lambda key: store[key])
    monkeypatch.setattr("src.domains.storage.client.delete_object", lambda key: store.pop(key, None))
    return store


def _candidate_token(db_session: Session, email: str = "setup.student@example.com") -> str:
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
    return create_access_token(user_id=user.id, role=user.role.value)


def _recruiter_token(db_session: Session, email: str = "setup.recruiter@acme.com") -> str:
    user, otp, _ = auth_service.register_recruiter(
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
    auth_service.confirm_email_otp(db_session, user.email, otp)
    return create_access_token(user_id=user.id, role=user.role.value)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _profile(db_session: Session, email: str) -> CandidateProfile:
    return db_session.execute(
        select(CandidateProfile).where(CandidateProfile.user.has(email=email))
    ).scalar_one()


def _docx_bytes(text: str = "Ada Lovelace, backend engineer.") -> bytes:
    document = Document()
    document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _pdf_bytes() -> bytes:
    """A byte string that opens with the PDF magic number.

    Deliberately not a valid PDF: `create_upload` only sniffs the header, and
    parsing happens in the worker. Using a real PDF here would test pypdf.
    """
    return b"%PDF-1.7\n% minimal header for content sniffing\n" + b"0" * 512


# --------------------------------------------------------------------------
# Authorization
# --------------------------------------------------------------------------


def test_setup_state_requires_authentication(client: TestClient) -> None:
    assert client.get(SETUP_STATE).status_code == 401


def test_recruiter_gets_403_from_setup_state(client: TestClient, db_session: Session) -> None:
    """`get_own_profile` rejects a recruiter before the handler body runs, so
    there is no route by which one reads a student's setup state."""
    token = _recruiter_token(db_session)
    assert client.get(SETUP_STATE, headers=_auth(token)).status_code == 403


def test_recruiter_gets_403_across_every_student_route(
    client: TestClient, db_session: Session
) -> None:
    token = _recruiter_token(db_session, "setup.recruiter2@acme.com")
    for path in (
        SETUP_STATE,
        f"{PROFILE_BASE}/completeness",
        f"{PROFILE_BASE}/sections/basic",
        f"{PROFILE_BASE}/sections/technical",
        f"{RESUME_BASE}/uploads",
    ):
        assert client.get(path, headers=_auth(token)).status_code == 403, path


# --------------------------------------------------------------------------
# Step and percentage derivation
# --------------------------------------------------------------------------


def test_empty_profile_derives_zero_percent_and_first_step(
    client: TestClient, db_session: Session
) -> None:
    token = _candidate_token(db_session, "setup.empty@example.com")
    body = client.get(SETUP_STATE, headers=_auth(token)).json()

    assert body["completion_percentage"] == 0
    assert body["current_step_index"] == 0
    assert body["meets_section_requirements"] is False
    assert body["is_discoverable"] is False

    assert [step["key"] for step in body["steps"]] == EXPECTED_STEP_KEYS
    assert [step["title"] for step in body["steps"]] == EXPECTED_STEP_TITLES
    assert [step["status"] for step in body["steps"]] == ["empty"] * 5
    assert [step["is_current"] for step in body["steps"]] == [True, False, False, False, False]
    assert body["resume"]["has_upload"] is False


def test_partial_basic_keeps_current_step_on_the_incomplete_mandatory_section(
    client: TestClient, db_session: Session
) -> None:
    """A half-filled section 1 is what blocks discoverability, so the pill stays
    there rather than advancing to the first *empty* step."""
    token = _candidate_token(db_session, "setup.partial@example.com")
    profile = _profile(db_session, "setup.partial@example.com")

    # Written directly: the section PUT is all-or-nothing by design, and the
    # state under test is a genuinely partial row.
    profile.headline = "Backend engineer"
    profile.college = "IIT Bombay"
    db_session.commit()

    body = client.get(SETUP_STATE, headers=_auth(token)).json()

    assert body["completion_percentage"] == 10  # 2 of 7 basic fields x 5 points
    assert body["current_step_index"] == 0
    assert body["steps"][0]["status"] == "saved"
    assert body["steps"][0]["filled_count"] == 2
    assert body["steps"][0]["required_count"] == 7
    assert body["steps"][1]["status"] == "empty"
    assert body["meets_section_requirements"] is False


def test_basic_complete_moves_current_step_to_technical(
    client: TestClient, db_session: Session
) -> None:
    token = _candidate_token(db_session, "setup.basic@example.com")
    response = client.put(
        f"{PROFILE_BASE}/sections/basic", json=VALID_BASIC, headers=_auth(token)
    )
    assert response.status_code == 200, response.text

    body = client.get(SETUP_STATE, headers=_auth(token)).json()

    assert body["completion_percentage"] == 35
    assert body["current_step_index"] == 1
    assert body["steps"][0]["status"] == "saved"
    assert body["steps"][1]["is_current"] is True
    assert body["meets_section_requirements"] is False


def test_mandatory_complete_profile_meets_requirements(
    client: TestClient, db_session: Session
) -> None:
    """Sections 1 and 2 done: 65%, requirements met, and the pill has moved past
    both mandatory steps to the first untouched optional one."""
    token = _candidate_token(db_session, "setup.mandatory@example.com")
    client.put(f"{PROFILE_BASE}/sections/basic", json=VALID_BASIC, headers=_auth(token))
    response = client.put(
        f"{PROFILE_BASE}/sections/technical", json=VALID_TECHNICAL, headers=_auth(token)
    )
    assert response.status_code == 200, response.text

    body = client.get(SETUP_STATE, headers=_auth(token)).json()

    assert body["completion_percentage"] == 65  # 35 basic + 30 technical
    assert body["meets_section_requirements"] is True
    # Filled, not verified: the accounts were just queued for verification, so
    # the step must read as pending rather than as a proven claim.
    assert body["steps"][1]["status"] == "pending_verification"
    assert body["current_step_index"] == 2
    # Still not discoverable — that additionally needs a profile embedding.
    assert body["is_discoverable"] is False


def test_percentage_is_recomputed_server_side_after_each_save(
    client: TestClient, db_session: Session
) -> None:
    token = _candidate_token(db_session, "setup.recompute@example.com")

    assert client.get(SETUP_STATE, headers=_auth(token)).json()["completion_percentage"] == 0
    client.put(f"{PROFILE_BASE}/sections/basic", json=VALID_BASIC, headers=_auth(token))
    assert client.get(SETUP_STATE, headers=_auth(token)).json()["completion_percentage"] == 35

    saved = client.put(
        f"{PROFILE_BASE}/sections/projects",
        json={
            "projects": [
                {
                    "kind": "described",
                    "title": "Toy compiler",
                    "description": "A small compiler for a Lisp dialect, written in Rust.",
                    "technologies": ["Rust"],
                }
            ]
        },
        headers=_auth(token),
    )
    assert saved.status_code == 200, saved.text
    assert client.get(SETUP_STATE, headers=_auth(token)).json()["completion_percentage"] == 40


def test_client_cannot_supply_a_percentage(client: TestClient, db_session: Session) -> None:
    """`extra="forbid"` on every request model turns an attempt to smuggle a
    derived value into a 422 rather than a silently ignored field."""
    token = _candidate_token(db_session, "setup.smuggle@example.com")
    response = client.put(
        f"{PROFILE_BASE}/sections/basic",
        json={**VALID_BASIC, "profile_strength": 100, "is_discoverable": True},
        headers=_auth(token),
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------
# Resume state inside setup-state
# --------------------------------------------------------------------------


def test_setup_state_reports_an_upload_in_flight_as_parsing(
    client: TestClient, db_session: Session, stub_storage
) -> None:
    """`ResumeUploadStatus.PROCESSING` surfaces as `parsing` — the wire name the
    screen's state machine is written in."""
    token = _candidate_token(db_session, "setup.inflight@example.com")
    accepted = client.post(
        f"{RESUME_BASE}/uploads",
        files={"file": ("resume.docx", _docx_bytes(), "application/octet-stream")},
        headers=_auth(token),
    )
    assert accepted.status_code == 202, accepted.text

    body = client.get(SETUP_STATE, headers=_auth(token)).json()
    assert body["resume"]["has_upload"] is True
    assert body["resume"]["status"] == "uploaded"
    assert body["resume"]["async_job_id"] == accepted.json()["async_job_id"]
    assert body["resume"]["draft_id"] is None

    upload = db_session.get(ResumeUpload, accepted.json()["upload"]["id"])
    upload.status = ResumeUploadStatus.PROCESSING
    db_session.commit()

    assert client.get(SETUP_STATE, headers=_auth(token)).json()["resume"]["status"] == "parsing"


def test_setup_state_reports_a_failed_parse_with_its_reason(
    client: TestClient, db_session: Session, stub_storage
) -> None:
    token = _candidate_token(db_session, "setup.failed@example.com")
    accepted = client.post(
        f"{RESUME_BASE}/uploads",
        files={"file": ("resume.pdf", _pdf_bytes(), "application/pdf")},
        headers=_auth(token),
    ).json()

    upload = db_session.get(ResumeUpload, accepted["upload"]["id"])
    upload.status = ResumeUploadStatus.FAILED
    upload.error = "No readable text was found."
    db_session.commit()

    resume = client.get(SETUP_STATE, headers=_auth(token)).json()["resume"]
    assert resume["status"] == "failed"
    assert resume["error"] == "No readable text was found."


# --------------------------------------------------------------------------
# Upload validation — size and content-sniffed type
# --------------------------------------------------------------------------


def test_upload_rejects_an_oversized_file(
    client: TestClient, db_session: Session, stub_storage, monkeypatch
) -> None:
    """413, and nothing is stored — the size check runs before the object write."""
    from src.config.config import get_storage_settings

    settings = get_storage_settings()
    monkeypatch.setattr(settings, "resume_max_bytes", 1024, raising=False)

    token = _candidate_token(db_session, "setup.toobig@example.com")
    response = client.post(
        f"{RESUME_BASE}/uploads",
        files={"file": ("resume.pdf", _pdf_bytes() + b"0" * 4096, "application/pdf")},
        headers=_auth(token),
    )

    assert response.status_code == 413, response.text
    assert stub_storage == {}


def test_upload_rejects_an_empty_file(
    client: TestClient, db_session: Session, stub_storage
) -> None:
    token = _candidate_token(db_session, "setup.empty-file@example.com")
    response = client.post(
        f"{RESUME_BASE}/uploads",
        files={"file": ("resume.pdf", b"", "application/pdf")},
        headers=_auth(token),
    )
    assert response.status_code == 415
    assert stub_storage == {}


def test_upload_rejects_a_legacy_doc_with_a_specific_remedy(
    client: TestClient, db_session: Session, stub_storage
) -> None:
    """OLE2 is detected by its header, so the student is told to re-save rather
    than waiting 30 seconds for a worker failure."""
    token = _candidate_token(db_session, "setup.legacydoc@example.com")
    ole2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 1024

    response = client.post(
        f"{RESUME_BASE}/uploads",
        files={"file": ("resume.doc", ole2, "application/msword")},
        headers=_auth(token),
    )

    assert response.status_code == 415, response.text
    assert "Legacy .doc" in response.text
    assert stub_storage == {}


def test_upload_rejects_a_wrong_type_renamed_to_pdf(
    client: TestClient, db_session: Session, stub_storage
) -> None:
    """The extension says PDF and the browser says PDF; the bytes say plain
    text. The bytes win — this is the whole point of sniffing."""
    token = _candidate_token(db_session, "setup.renamed@example.com")
    response = client.post(
        f"{RESUME_BASE}/uploads",
        files={"file": ("resume.pdf", b"just some plain text, honestly" * 40, "application/pdf")},
        headers=_auth(token),
    )

    assert response.status_code == 415, response.text
    assert stub_storage == {}


def test_upload_rejects_a_non_word_zip(
    client: TestClient, db_session: Session, stub_storage
) -> None:
    """A zip is not a DOCX unless it holds `word/document.xml` — every OOXML
    format shares the same magic number."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/workbook.xml", "<workbook/>")

    token = _candidate_token(db_session, "setup.zip@example.com")
    response = client.post(
        f"{RESUME_BASE}/uploads",
        files={"file": ("resume.docx", buffer.getvalue(), "application/octet-stream")},
        headers=_auth(token),
    )

    assert response.status_code == 415, response.text
    assert stub_storage == {}


def test_upload_accepts_a_real_docx_regardless_of_declared_type(
    client: TestClient, db_session: Session, stub_storage
) -> None:
    """The declared content type is ignored entirely; the bytes decide."""
    token = _candidate_token(db_session, "setup.gooddocx@example.com")
    response = client.post(
        f"{RESUME_BASE}/uploads",
        files={"file": ("cv", _docx_bytes(), "text/plain")},
        headers=_auth(token),
    )

    assert response.status_code == 202, response.text
    assert (
        response.json()["upload"]["content_type"]
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(stub_storage) == 1
