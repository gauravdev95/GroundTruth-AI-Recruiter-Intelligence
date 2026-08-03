"""The two read paths over `match_results` — same rows, same `match_score`
ordering, two different owners' view of them. Neither endpoint computes
anything; both are `SELECT ... ORDER BY match_score DESC` (see
`domains/matching/service.py`'s module docstring).

Neither applies a `LIMIT`. They used to re-apply the write-side top-K here as
a display cap, which meant rows that had genuinely been persisted were
invisible with nothing to indicate they existed. The cap belongs at the write
(`scoring.TOP_K`, bounding how many rows a recompute may create); a read
returns what is there.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.domains.auth.models import CandidateProfile
from src.domains.company.models import Company
from src.domains.matching.models import MatchResult
from src.domains.matching.schemas import (
    JobFeedResponse,
    MatchedCandidatePreview,
    MatchedCandidateResponse,
    MatchedCandidatesResponse,
    MatchedJobPreview,
    MatchedJobResponse,
    SkillMatchReasonResponse,
)
from src.domains.recruiter.dependencies import get_own_job
from src.domains.recruiter.models import JobPosting
from src.domains.student.dependencies import get_own_profile

recruiter_matches_router = APIRouter(prefix="/api/v1/recruiter/jobs", tags=["recruiter-matches"])
student_feed_router = APIRouter(prefix="/api/v1/student/matches", tags=["student-matches"])


def _reasons(raw: list[dict]) -> list[SkillMatchReasonResponse]:
    return [SkillMatchReasonResponse(**item) for item in raw]


@recruiter_matches_router.get("/{job_id}/matches", response_model=MatchedCandidatesResponse)
def get_job_matches(job: JobPosting = Depends(get_own_job), db: Session = Depends(get_db)) -> MatchedCandidatesResponse:
    rows = db.execute(
        select(MatchResult, CandidateProfile)
        .join(CandidateProfile, CandidateProfile.id == MatchResult.candidate_profile_id)
        .where(MatchResult.job_posting_id == job.id)
        .order_by(MatchResult.match_score.desc())
    ).all()

    candidates = [
        MatchedCandidateResponse(
            match_score=float(match.match_score),
            semantic_score=float(match.semantic_score),
            evidence_score=float(match.evidence_score),
            matched_required_skills=_reasons(match.matched_required_skills),
            matched_desirable_skills=_reasons(match.matched_desirable_skills),
            computed_at=match.computed_at,
            updated_at=match.updated_at,
            candidate=MatchedCandidatePreview(
                candidate_profile_id=profile.id,
                headline=profile.headline,
                college=profile.college,
                degree=profile.degree.value if profile.degree else None,
                branch=profile.branch.value if profile.branch else None,
                graduation_year=profile.graduation_year,
                location=profile.location,
                target_role=profile.target_role.value if profile.target_role else None,
                profile_strength=profile.profile_strength,
            ),
        )
        for match, profile in rows
    ]
    return MatchedCandidatesResponse(job_id=job.id, job_title=job.title, candidates=candidates)


@student_feed_router.get("", response_model=JobFeedResponse)
def get_job_feed(
    profile: CandidateProfile = Depends(get_own_profile), db: Session = Depends(get_db)
) -> JobFeedResponse:
    rows = db.execute(
        select(MatchResult, JobPosting, Company)
        .join(JobPosting, JobPosting.id == MatchResult.job_posting_id)
        .join(Company, Company.id == JobPosting.company_id)
        .where(MatchResult.candidate_profile_id == profile.id)
        .order_by(MatchResult.match_score.desc())
    ).all()

    jobs = [
        MatchedJobResponse(
            match_score=float(match.match_score),
            semantic_score=float(match.semantic_score),
            evidence_score=float(match.evidence_score),
            matched_required_skills=_reasons(match.matched_required_skills),
            matched_desirable_skills=_reasons(match.matched_desirable_skills),
            computed_at=match.computed_at,
            updated_at=match.updated_at,
            job=MatchedJobPreview(
                job_id=job.id,
                title=job.title,
                company_name=company.name,
                job_type=job.job_type.value,
                experience_level=job.experience_level.value,
                location=job.location,
                is_remote=job.is_remote,
                deadline=job.deadline,
            ),
        )
        for match, job, company in rows
    ]
    return JobFeedResponse(jobs=jobs)
