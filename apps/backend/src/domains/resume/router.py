"""Resume import API.

Every endpoint is candidate-only and scoped to the caller's own profile via
`get_own_profile` — the same dependency the section endpoints use, so a
recruiter gets 403 and no route accepts a profile id from the client.

The upload endpoint returns **202 Accepted** with a job id. It never waits on
parsing or the LLM; that work runs in the `extraction` queue and the client
polls `/api/v1/jobs/{id}`.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.domains.auth.models import CandidateProfile
from src.domains.auth.rate_limit import limiter
from src.domains.resume import confirm as confirm_module
from src.domains.resume import service
from src.domains.resume.schemas import (
    ConfirmDraftRequest,
    ConfirmDraftResponse,
    DraftSuggestionsResponse,
    ResumeDraftDetailResponse,
    ResumeDraftResponse,
    ResumeUploadAcceptedResponse,
    ResumeUploadListResponse,
    ResumeUploadResponse,
)
from src.domains.student.dependencies import get_own_profile
from src.domains.student.router import _completeness_response

router = APIRouter(prefix="/api/v1/student/resume", tags=["student-resume"])


def _suggestions_response(payload: dict) -> DraftSuggestionsResponse:
    suggestions = confirm_module.suggest_sections(payload)
    return DraftSuggestionsResponse(
        basic=suggestions.basic,
        technical=suggestions.technical,
        projects=suggestions.projects,
        certificates=suggestions.certificates,
        experience=suggestions.experience,
        unmapped=suggestions.unmapped,
    )


@router.post(
    "/uploads",
    response_model=ResumeUploadAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/hour")
def upload_resume(
    request: Request,
    file: UploadFile = File(...),
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> ResumeUploadAcceptedResponse:
    """Store a resume and queue extraction. Returns before any parsing happens."""
    # `file.size` is populated by Starlette from the multipart body it already
    # buffered, so this is a real size rather than a client claim.
    size_bytes = file.size or 0

    upload, job = service.create_upload(
        db,
        profile,
        fileobj=file.file,
        filename=file.filename or "resume",
        size_bytes=size_bytes,
    )
    return ResumeUploadAcceptedResponse(
        upload=ResumeUploadResponse.model_validate(upload),
        async_job_id=job.id,
    )


@router.get("/uploads", response_model=ResumeUploadListResponse)
def list_uploads(
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> ResumeUploadListResponse:
    return ResumeUploadListResponse(
        uploads=[ResumeUploadResponse.model_validate(u) for u in service.list_uploads(db, profile)]
    )


@router.get("/uploads/{upload_id}", response_model=ResumeUploadResponse)
def read_upload(
    upload_id: uuid.UUID,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> ResumeUploadResponse:
    return ResumeUploadResponse.model_validate(service.get_upload(db, profile, upload_id))


@router.delete("/uploads/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_upload(
    upload_id: uuid.UUID,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> None:
    """Remove the stored file. Drafts already produced from it are retained."""
    service.delete_upload(db, service.get_upload(db, profile, upload_id))


@router.get("/uploads/{upload_id}/draft", response_model=ResumeDraftDetailResponse)
def read_draft_for_upload(
    upload_id: uuid.UUID,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> ResumeDraftDetailResponse:
    service.get_upload(db, profile, upload_id)  # 404s if not the caller's upload
    draft = service.latest_draft_for_upload(db, profile, upload_id)
    if draft is None:
        from src.core.exceptions import NotFound

        raise NotFound("No extraction draft exists for this upload yet")

    return ResumeDraftDetailResponse(
        draft=ResumeDraftResponse.model_validate(draft),
        suggestions=_suggestions_response(draft.payload),
    )


@router.get("/drafts/{draft_id}", response_model=ResumeDraftDetailResponse)
def read_draft(
    draft_id: uuid.UUID,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> ResumeDraftDetailResponse:
    draft = service.get_draft(db, profile, draft_id)
    return ResumeDraftDetailResponse(
        draft=ResumeDraftResponse.model_validate(draft),
        suggestions=_suggestions_response(draft.payload),
    )


@router.post("/drafts/{draft_id}/confirm", response_model=ConfirmDraftResponse)
def confirm_draft(
    draft_id: uuid.UUID,
    payload: ConfirmDraftRequest,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> ConfirmDraftResponse:
    """Write the confirmed sections through the ordinary section services.

    This is the only path by which extracted data reaches a live profile table,
    and it goes through the same schemas and services a manual section PUT does.
    """
    draft = service.get_draft(db, profile, draft_id)
    completeness = service.confirm_draft(db, profile, draft, payload)
    db.refresh(draft)
    return ConfirmDraftResponse(
        draft=ResumeDraftResponse.model_validate(draft),
        completeness=_completeness_response(completeness),
    )


@router.post("/drafts/{draft_id}/discard", response_model=ResumeDraftResponse)
def discard_draft(
    draft_id: uuid.UUID,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> ResumeDraftResponse:
    draft = service.get_draft(db, profile, draft_id)
    return ResumeDraftResponse.model_validate(service.discard_draft(db, draft))
