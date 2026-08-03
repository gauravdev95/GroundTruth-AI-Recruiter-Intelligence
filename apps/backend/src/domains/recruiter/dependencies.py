"""FastAPI dependencies scoping every request to the caller's own recruiter
profile and jobs — the recruiter-domain mirror of
`domains/student/dependencies.py`.
"""

from __future__ import annotations

import uuid

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.authorization import verify_ownership
from src.core.exceptions import NotFound
from src.db.database import get_db
from src.domains.auth.dependencies import require_role
from src.domains.auth.models import RecruiterProfile, User, UserRole
from src.domains.recruiter.models import JobPosting

require_recruiter = require_role(UserRole.RECRUITER)


def get_own_recruiter_profile(
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
) -> RecruiterProfile:
    profile = db.execute(
        select(RecruiterProfile).where(RecruiterProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise NotFound("Recruiter profile not found")
    return profile


def get_own_job(
    job_id: uuid.UUID,
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
) -> JobPosting:
    """Resolves a job by id and verifies the caller created it — 403, not
    404, for someone else's job (constraint: "recruiters access only their
    own jobs; students get 403" — `require_recruiter` already turns a
    student's request into a 403 before this runs; this covers the
    other-recruiter's-job case with the same status)."""
    job = db.get(JobPosting, job_id)
    if job is None:
        raise NotFound("Job not found")
    verify_ownership(resource_owner_id=job.created_by_user_id, current_user=user)
    return job
