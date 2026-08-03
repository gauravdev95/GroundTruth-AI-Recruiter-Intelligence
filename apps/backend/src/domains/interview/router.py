"""AI interview API routes.

Thin by design, matching every other router in this codebase: parse request
-> call `service` -> return a schema. Every route resolves the profile from
the authenticated candidate via `get_own_profile`, so a recruiter is
rejected with 403 before any handler body runs and no route accepts a
profile id from the client.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.core.exceptions import NotFound
from src.db.database import get_db
from src.domains.auth.models import CandidateProfile
from src.domains.auth.rate_limit import limiter
from src.domains.interview import service
from src.domains.interview.schemas import (
    EvidenceReportResponse,
    InterviewStateResponse,
    InterviewSummaryResponse,
    SubmitAnswerRequest,
)
from src.domains.student.dependencies import get_own_profile

router = APIRouter(prefix="/api/v1/student/interview", tags=["student-interview"])


@router.post("/projects/{project_id}/start", response_model=InterviewSummaryResponse)
@limiter.limit("10/hour")
def start_interview(
    request: Request,
    project_id: uuid.UUID,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> InterviewSummaryResponse:
    interview = service.start_interview(db, profile, project_id)
    return InterviewSummaryResponse.model_validate(interview)


@router.get("/projects/{project_id}/latest", response_model=InterviewSummaryResponse)
def latest_for_project(
    project_id: uuid.UUID,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> InterviewSummaryResponse:
    interview = service.get_latest_for_project(db, profile, project_id)
    if interview is None:
        raise NotFound("No interview exists for this project yet")
    return InterviewSummaryResponse.model_validate(interview)


@router.get("/{interview_id}", response_model=InterviewStateResponse)
def get_state(
    interview_id: uuid.UUID,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> InterviewStateResponse:
    """Resumability lives here: this always returns the next unanswered
    question (marking it presented on first fetch), so reloading the page
    after a disconnect picks up exactly where the candidate left off."""
    return service.get_state(db, profile, interview_id)


@router.post("/{interview_id}/questions/{question_id}/answer", response_model=InterviewStateResponse)
@limiter.limit("30/hour")
def submit_answer(
    request: Request,
    interview_id: uuid.UUID,
    question_id: uuid.UUID,
    payload: SubmitAnswerRequest,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> InterviewStateResponse:
    return service.submit_answer(
        db,
        profile,
        interview_id,
        question_id,
        transcript=payload.transcript,
        time_taken_seconds=payload.time_taken_seconds,
    )


@router.get("/{interview_id}/report", response_model=EvidenceReportResponse)
def get_report(
    interview_id: uuid.UUID,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> EvidenceReportResponse:
    return service.get_report(db, profile, interview_id)
