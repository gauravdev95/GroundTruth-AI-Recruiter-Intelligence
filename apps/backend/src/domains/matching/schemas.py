"""Response schemas for the two read paths over `match_results` — the
recruiter's ranked candidate list and the student's job feed. Both are
plain reads with no computation; see `domains/matching/service.py`.

**`computed_at` vs `updated_at`, and what each is called in the UI.**

The two columns answer different questions and both are sent, because a
client that only had one would be forced to imply the other:

* `computed_at` — when this pair *first* matched. Never moves.
  Rendered as **"Matched {when}"**.
* `updated_at` — when its score was last recomputed.
  Rendered as **"Score updated {when}"**, and only when it actually differs
  from `computed_at`; on a pair that has never been rescored the two are the
  same instant (`service.py::_reconcile` uses one timestamp for both on
  insert), and printing it twice under two labels would invent a second
  event.

The labels deliberately avoid "computed" and "recomputed". Those are the
names of the *mechanism*; what a student or recruiter is being told is when
they matched and when the number last moved. Reusing the column names in the
interface would make the reader learn our scheduler to read a date.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class SkillMatchReasonResponse(BaseModel):
    skill_name: str
    candidate_has_skill: bool
    candidate_proficiency: str | None
    evidence_weight: float | None
    evidence_sources: list[dict]


# --- Recruiter side: matched candidates for one job -------------------------


class MatchedCandidatePreview(BaseModel):
    """Enough for a one-click preview card — not the full profile-builder
    payload, which stays behind the ordinary (candidate-owned) profile
    endpoints."""

    candidate_profile_id: uuid.UUID
    headline: str | None
    college: str | None
    degree: str | None
    branch: str | None
    graduation_year: int | None
    location: str | None
    target_role: str | None
    profile_strength: int


class MatchedCandidateResponse(BaseModel):
    match_score: float
    semantic_score: float
    evidence_score: float
    matched_required_skills: list[SkillMatchReasonResponse]
    matched_desirable_skills: list[SkillMatchReasonResponse]
    computed_at: datetime
    updated_at: datetime
    candidate: MatchedCandidatePreview


class MatchedCandidatesResponse(BaseModel):
    job_id: uuid.UUID
    job_title: str
    candidates: list[MatchedCandidateResponse]


# --- Student side: job feed --------------------------------------------------


class MatchedJobPreview(BaseModel):
    job_id: uuid.UUID
    title: str
    company_name: str
    job_type: str
    experience_level: str
    location: str | None
    is_remote: bool
    deadline: date | None


class MatchedJobResponse(BaseModel):
    match_score: float
    semantic_score: float
    evidence_score: float
    matched_required_skills: list[SkillMatchReasonResponse]
    matched_desirable_skills: list[SkillMatchReasonResponse]
    computed_at: datetime
    updated_at: datetime
    job: MatchedJobPreview


class JobFeedResponse(BaseModel):
    jobs: list[MatchedJobResponse]
