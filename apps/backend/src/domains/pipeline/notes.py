"""Private recruiter team notes.

"Enforce exclusion at the query layer, never by UI filtering" — the query in
`list_notes`/`add_note` joins `applications -> job_postings` and filters
`JobPosting.company_id == recruiter's company_id` *inside the SQL*, not by
fetching rows and discarding ones that don't match in Python. No route in
`pipeline/router.py` exposes this module to a candidate token at all — the
company filter is what stops a recruiter at a *different* company from
reading another company's notes, which the ordinary `get_own_job` ownership
check (scoped to a single creator) would not, since notes are meant to be
shared across a hiring team, not locked to whichever recruiter happened to
post the job.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.exceptions import Forbidden, NotFound
from src.domains.auth.models import RecruiterProfile
from src.domains.pipeline.models import Application, RecruiterNote
from src.domains.recruiter.models import JobPosting


def _company_scoped_application(db: Session, recruiter: RecruiterProfile, application_id: uuid.UUID) -> Application:
    row = db.execute(
        select(Application, JobPosting)
        .join(JobPosting, JobPosting.id == Application.job_posting_id)
        .where(Application.id == application_id, JobPosting.company_id == recruiter.company_id)
    ).first()
    if row is None:
        # A real application that belongs to a *different* company must
        # 403, not 404 — same "don't leak whether it exists" reasoning
        # `core/authorization.verify_ownership` documents — but only if it
        # exists at all; otherwise a genuine 404.
        exists = db.get(Application, application_id)
        raise Forbidden() if exists is not None else NotFound("Application not found")
    application, _job = row
    return application


def list_notes(db: Session, recruiter: RecruiterProfile, application_id: uuid.UUID) -> list[RecruiterNote]:
    application = _company_scoped_application(db, recruiter, application_id)
    return list(
        db.execute(
            select(RecruiterNote)
            .where(RecruiterNote.application_id == application.id)
            .order_by(RecruiterNote.created_at.desc())
        ).scalars()
    )


def add_note(db: Session, recruiter: RecruiterProfile, application_id: uuid.UUID, *, body: str) -> RecruiterNote:
    application = _company_scoped_application(db, recruiter, application_id)
    note = RecruiterNote(application_id=application.id, author_user_id=recruiter.user_id, body=body)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note
