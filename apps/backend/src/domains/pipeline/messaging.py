"""In-platform messaging, restricted to pairs with an existing pipeline
relationship — enforced structurally: a `Conversation` only ever exists
attached to an `Application` (`models.py`'s FK), and every function here
takes an already-ownership-checked `Application` from the caller
(`pipeline/router.py` resolves it via `service.get_application_for_recruiter`
/ `get_application_for_candidate` first), never a bare conversation id a
client could guess.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.config import get_security_settings
from src.core.mail.service import send_new_message_email
from src.domains.auth.models import CandidateProfile, User
from src.domains.pipeline import notifications
from src.domains.pipeline.models import Application, Conversation, Message, NotificationType
from src.domains.recruiter.models import JobPosting

logger = structlog.get_logger(__name__)


def get_or_create_conversation(db: Session, application: Application) -> Conversation:
    conversation = db.execute(
        select(Conversation).where(Conversation.application_id == application.id)
    ).scalar_one_or_none()
    if conversation is not None:
        return conversation
    conversation = Conversation(application_id=application.id)
    db.add(conversation)
    db.flush()
    return conversation


def list_messages(db: Session, application: Application) -> list[Message]:
    conversation = db.execute(
        select(Conversation).where(Conversation.application_id == application.id)
    ).scalar_one_or_none()
    if conversation is None:
        return []
    return list(
        db.execute(
            select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at)
        ).scalars()
    )


def send_message(db: Session, sender: User, application: Application, *, body: str) -> Message:
    conversation = get_or_create_conversation(db, application)
    message = Message(conversation_id=conversation.id, sender_user_id=sender.id, body=body)
    db.add(message)
    db.flush()

    recipient_user_id = _other_party(db, sender, application)
    if recipient_user_id is not None:
        notifications.notify(
            db,
            user_id=recipient_user_id,
            type_=NotificationType.NEW_MESSAGE,
            payload={"application_id": str(application.id), "conversation_id": str(conversation.id)},
        )

    db.commit()
    db.refresh(message)

    if recipient_user_id is not None:
        _notify_new_message_by_email(db, recipient_user_id=recipient_user_id, application=application)

    return message


def _notify_new_message_by_email(db: Session, *, recipient_user_id: uuid.UUID, application: Application) -> None:
    """Best-effort, same as stage-change email: never block the send."""
    recipient = db.get(User, recipient_user_id)
    if recipient is None:
        return
    job = db.get(JobPosting, application.job_posting_id)
    application_url = f"{get_security_settings().frontend_base_url}/applications/{application.id}"
    try:
        send_new_message_email(
            to_email=recipient.email,
            full_name=recipient.display_name,
            job_title=job.title if job is not None else "your application",
            application_url=application_url,
        )
    except Exception:
        logger.warning("new_message_email_failed", user_id=str(recipient_user_id), application_id=str(application.id))


def _other_party(db: Session, sender: User, application: Application) -> uuid.UUID | None:
    candidate = db.get(CandidateProfile, application.candidate_profile_id)
    job = db.get(JobPosting, application.job_posting_id)
    candidate_user_id = candidate.user_id if candidate is not None else None
    recruiter_user_id = job.created_by_user_id if job is not None else None

    if sender.id == candidate_user_id:
        return recruiter_user_id
    return candidate_user_id
