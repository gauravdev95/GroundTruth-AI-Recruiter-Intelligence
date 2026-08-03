"""In-platform notifications — a DB-backed inbox. Three triggers: stage
change, new message, and a new match.

The notification row is the durable record; a realtime push (see
`src/realtime/`) is a delivery optimisation layered on top of it, never a
replacement. A client that missed the socket event still finds the
notification on its next poll, which is why the row is written first and
emitted second.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domains.auth.models import CandidateProfile
from src.domains.pipeline.models import Notification, NotificationType


def notify(db: Session, *, user_id: uuid.UUID, type_: NotificationType, payload: dict) -> None:
    db.add(Notification(user_id=user_id, type=type_, payload=payload))


def notify_new_matches(
    db: Session, *, matches: list[tuple[uuid.UUID, str, float]]
) -> list[tuple[uuid.UUID, dict]]:
    """Writes one `NEW_MATCH` notification per newly matched candidate.

    `matches` is `(candidate_profile_id, job_title, score)`. Only *newly
    inserted* pairs should be passed — a rescore of a pair the student has
    already been told about is not news, and notifying on it would turn every
    re-verification into a burst of duplicates.

    Returns `(user_id, payload)` per notification so the caller can emit the
    same payload over the socket without re-deriving it. Candidate ids are
    resolved to user ids in one query rather than per row.
    """
    if not matches:
        return []

    candidate_ids = list({candidate_id for candidate_id, _, _ in matches})
    user_id_by_candidate = dict(
        db.execute(
            select(CandidateProfile.id, CandidateProfile.user_id).where(
                CandidateProfile.id.in_(candidate_ids)
            )
        ).all()
    )

    emitted: list[tuple[uuid.UUID, dict]] = []
    for candidate_id, job_title, score in matches:
        user_id = user_id_by_candidate.get(candidate_id)
        if user_id is None:
            # The profile was deleted between the match being computed and
            # this write. Nothing to notify; not an error.
            continue
        payload = {
            "job_title": job_title,
            "score": round(score),
            "message": f"New match — {job_title}, {round(score)}%",
        }
        notify(db, user_id=user_id, type_=NotificationType.NEW_MATCH, payload=payload)
        emitted.append((user_id, payload))

    return emitted
