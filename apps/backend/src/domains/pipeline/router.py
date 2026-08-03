"""Marketplace-loop API routes: Smart Apply, the Kanban pipeline, the
recruiter evidence card, messaging, notes, notifications, and analytics.

Three routers, one per audience: `student_router` (candidate-only, via
`get_own_profile`), `recruiter_router` (recruiter-only, via
`get_own_recruiter_profile`/`get_own_job`), and `notifications_router`
(either role — a notification's `user_id` already scopes it, so this only
needs `get_current_user`, not a role check).
"""

from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from src.core.audit import write_audit_log
from src.core.exceptions import Forbidden, NotFound
from src.db.database import get_db
from src.domains.auth.dependencies import get_current_user
from src.domains.auth.models import CandidateProfile, RecruiterProfile, User
from src.domains.matching.models import MatchResult
from src.domains.pipeline import analytics, messaging, notes as notes_service, service
from src.domains.pipeline.evidence import build_evidence_record
from src.domains.pipeline.models import Application, Notification
from src.domains.pipeline.schemas import (
    AddNoteRequest,
    ApplicationDetailResponse,
    ApplicationListItemResponse,
    ApplicationResponse,
    ApplyRequest,
    ConversationResponse,
    EvidenceRecordResponse,
    MessageResponse,
    NoteResponse,
    NotificationListResponse,
    NotificationResponse,
    PipelineResponse,
    RecruiterApplicationDetailResponse,
    ScoreDriftResponse,
    SendMessageRequest,
    TransitionRequest,
)
from src.domains.recruiter.dependencies import get_own_job, get_own_recruiter_profile
from src.domains.recruiter.models import JobPosting
from src.domains.student.dependencies import get_own_profile

student_router = APIRouter(prefix="/api/v1/student", tags=["student-pipeline"])
recruiter_router = APIRouter(prefix="/api/v1/recruiter", tags=["recruiter-pipeline"])
notifications_router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


# --------------------------------------------------------------------------
# Student: Smart Apply, own applications, messaging on them
# --------------------------------------------------------------------------


@student_router.post("/jobs/{job_id}/apply", response_model=ApplicationResponse, status_code=201)
def apply_to_job(
    job_id: uuid.UUID,
    payload: ApplyRequest,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> ApplicationResponse:
    application = service.apply_to_job(db, profile, job_id, cover_note=payload.cover_note)
    return ApplicationResponse.model_validate(application)


@student_router.get("/applications", response_model=list[ApplicationListItemResponse])
def list_my_applications(
    profile: CandidateProfile = Depends(get_own_profile), db: Session = Depends(get_db)
) -> list[ApplicationListItemResponse]:
    return [
        ApplicationListItemResponse(
            application=ApplicationResponse.model_validate(application), job_title=job_title, company_name=company_name
        )
        for application, job_title, company_name in service.list_candidate_applications_with_job(db, profile)
    ]


@student_router.get("/applications/{application_id}", response_model=ApplicationDetailResponse)
def get_my_application(
    application_id: uuid.UUID,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> ApplicationDetailResponse:
    application, job_title, company_name = service.get_application_for_candidate_with_job(
        db, profile, application_id
    )
    return ApplicationDetailResponse(
        application=ApplicationResponse.model_validate(application),
        evidence_snapshot=application.evidence_snapshot,
        job_title=job_title,
        company_name=company_name,
    )


@student_router.get("/applications/{application_id}/messages", response_model=ConversationResponse)
def get_my_conversation(
    application_id: uuid.UUID,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> ConversationResponse:
    application = service.get_application_for_candidate(db, profile, application_id)
    return ConversationResponse(
        application_id=application.id,
        messages=[MessageResponse.model_validate(m) for m in messaging.list_messages(db, application)],
    )


@student_router.post("/applications/{application_id}/messages", response_model=MessageResponse, status_code=201)
def send_my_message(
    application_id: uuid.UUID,
    payload: SendMessageRequest,
    profile: CandidateProfile = Depends(get_own_profile),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    application = service.get_application_for_candidate(db, profile, application_id)
    message = messaging.send_message(db, user, application, body=payload.body)
    return MessageResponse.model_validate(message)


@student_router.get("/analytics/summary")
def get_student_analytics(
    profile: CandidateProfile = Depends(get_own_profile), db: Session = Depends(get_db)
) -> dict:
    return analytics.student_summary(db, profile)


# --------------------------------------------------------------------------
# Recruiter: Kanban pipeline, transitions, evidence card, messaging, notes
# --------------------------------------------------------------------------


@recruiter_router.get("/jobs/{job_id}/pipeline", response_model=PipelineResponse)
def get_pipeline(job: JobPosting = Depends(get_own_job), db: Session = Depends(get_db)) -> PipelineResponse:
    return PipelineResponse(**service.get_pipeline(db, job))


@recruiter_router.get("/applications/{application_id}", response_model=RecruiterApplicationDetailResponse)
def get_application_detail(
    application_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> RecruiterApplicationDetailResponse:
    context = service.get_application_for_recruiter_with_context(db, user, application_id)
    return RecruiterApplicationDetailResponse(
        application=ApplicationResponse.model_validate(context.application),
        job_title=context.job_title,
        company_name=context.company_name,
        candidate_profile_id=context.candidate_profile_id,
        candidate_headline=context.candidate_headline,
        drift=ScoreDriftResponse(**asdict(context.drift)),
        can_roll_back=context.rollback_target is not None,
        rollback_target=context.rollback_target,
    )


@recruiter_router.post("/applications/{application_id}/transition", response_model=ApplicationResponse)
def transition_application(
    application_id: uuid.UUID,
    payload: TransitionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationResponse:
    application = service.get_application_for_recruiter(db, user, application_id)
    updated = service.transition_status(db, user, application, to_status=payload.to_status)
    return ApplicationResponse.model_validate(updated)


@recruiter_router.post("/applications/{application_id}/rollback", response_model=ApplicationResponse)
def rollback_application(
    application_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationResponse:
    """Undoes the last forward stage transition.

    Its own endpoint rather than a `to_status` a client picks, because for a
    `REJECTED` application the target is not a client-knowable value — it is
    read back off `audit_log` (`service.resolve_rollback_target`). A body
    naming a target would either be ignored or invite a client to name one
    the audit trail contradicts. An illegal rollback (`APPLIED`, `HIRED`)
    is a 409 from the same `Conflict` path an illegal forward transition
    raises, so the board surfaces both the same way.
    """
    application = service.get_application_for_recruiter(db, user, application_id)
    return ApplicationResponse.model_validate(service.rollback_status(db, user, application))


def _verify_recruiter_can_view_candidate(db: Session, user: User, candidate_profile_id: uuid.UUID) -> None:
    """Query-layer authorization: a recruiter may view a candidate's
    evidence only if that candidate has a `MatchResult` *or* an
    `Application` against one of this recruiter's own jobs — an `EXISTS`
    subquery, not a fetch-then-filter."""
    has_relationship = db.execute(
        select(
            exists(
                select(1)
                .select_from(JobPosting)
                .where(
                    JobPosting.created_by_user_id == user.id,
                    or_(
                        exists(
                            select(1).where(
                                MatchResult.job_posting_id == JobPosting.id,
                                MatchResult.candidate_profile_id == candidate_profile_id,
                            )
                        ),
                        exists(
                            select(1).where(
                                Application.job_posting_id == JobPosting.id,
                                Application.candidate_profile_id == candidate_profile_id,
                            )
                        ),
                    ),
                )
            )
        )
    ).scalar_one()
    if not has_relationship:
        raise Forbidden()


@recruiter_router.get("/candidates/{candidate_profile_id}/evidence", response_model=EvidenceRecordResponse)
def get_candidate_evidence(
    candidate_profile_id: uuid.UUID,
    user: User = Depends(get_current_user),
    _recruiter: RecruiterProfile = Depends(get_own_recruiter_profile),
    db: Session = Depends(get_db),
) -> EvidenceRecordResponse:
    _verify_recruiter_can_view_candidate(db, user, candidate_profile_id)

    profile = db.get(CandidateProfile, candidate_profile_id)
    if profile is None:
        raise NotFound("Candidate not found")

    write_audit_log(
        db,
        actor_user_id=user.id,
        action="candidate_profile.viewed",
        entity_type="candidate_profile",
        entity_id=profile.id,
        before=None,
        after=None,
    )
    db.commit()

    return EvidenceRecordResponse(record=build_evidence_record(db, profile))


@recruiter_router.get("/applications/{application_id}/messages", response_model=ConversationResponse)
def get_application_conversation(
    application_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ConversationResponse:
    application = service.get_application_for_recruiter(db, user, application_id)
    return ConversationResponse(
        application_id=application.id,
        messages=[MessageResponse.model_validate(m) for m in messaging.list_messages(db, application)],
    )


@recruiter_router.post(
    "/applications/{application_id}/messages", response_model=MessageResponse, status_code=201
)
def send_application_message(
    application_id: uuid.UUID,
    payload: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    application = service.get_application_for_recruiter(db, user, application_id)
    message = messaging.send_message(db, user, application, body=payload.body)
    return MessageResponse.model_validate(message)


@recruiter_router.get("/applications/{application_id}/notes", response_model=list[NoteResponse])
def list_application_notes(
    application_id: uuid.UUID,
    recruiter: RecruiterProfile = Depends(get_own_recruiter_profile),
    db: Session = Depends(get_db),
) -> list[NoteResponse]:
    return [NoteResponse.model_validate(n) for n in notes_service.list_notes(db, recruiter, application_id)]


@recruiter_router.post("/applications/{application_id}/notes", response_model=NoteResponse, status_code=201)
def add_application_note(
    application_id: uuid.UUID,
    payload: AddNoteRequest,
    recruiter: RecruiterProfile = Depends(get_own_recruiter_profile),
    db: Session = Depends(get_db),
) -> NoteResponse:
    return NoteResponse.model_validate(notes_service.add_note(db, recruiter, application_id, body=payload.body))


@recruiter_router.get("/analytics/funnel")
def get_recruiter_funnel(
    recruiter: RecruiterProfile = Depends(get_own_recruiter_profile), db: Session = Depends(get_db)
) -> dict:
    return analytics.recruiter_funnel(db, recruiter)


# --------------------------------------------------------------------------
# Notifications (either role)
# --------------------------------------------------------------------------


@notifications_router.get("", response_model=NotificationListResponse)
def list_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> NotificationListResponse:
    rows = list(
        db.execute(
            select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(50)
        ).scalars()
    )
    unread = sum(1 for r in rows if r.read_at is None)
    return NotificationListResponse(
        notifications=[NotificationResponse.model_validate(r) for r in rows], unread_count=unread
    )


@notifications_router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> NotificationResponse:
    from datetime import datetime, timezone

    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise NotFound("Notification not found")
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return NotificationResponse.model_validate(notification)
