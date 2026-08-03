"""Builds the candidate evidence record — the same builder backs two things:
`Application.evidence_snapshot` (a frozen copy taken at Smart Apply time)
and the recruiter's live candidate evidence card (`GET
/api/v1/recruiter/candidates/{id}/evidence`, always current). One function,
two callers, so neither can silently drift out of the shape the other
expects.

Everything here reads rows already written by the verification and
interview subsystems — contribution analysis (`Project.verification_payload`),
interview transcripts and scores (`Interview.evidence_report`), coding-
platform stats (`CodingPlatformAccount.verification_payload`), certificates.
Nothing is recomputed or narrated here.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domains.auth.models import CandidateProfile
from src.domains.interview.models import Interview, InterviewStatus
from src.domains.matching.models import MatchResult
from src.domains.skills.models import CandidateSkill, Skill
from src.domains.student.models import Certificate, CodingPlatformAccount, Experience, GithubAccount, Project, VerificationStatus


def build_evidence_record(db: Session, profile: CandidateProfile, *, job_posting_id: uuid.UUID | None = None) -> dict:
    projects = list(
        db.execute(
            select(Project).where(Project.candidate_profile_id == profile.id, Project.deleted_at.is_(None))
        ).scalars()
    )
    verified_project_ids = [p.id for p in projects if p.verification_status is VerificationStatus.VERIFIED]

    interviews = []
    if verified_project_ids:
        interviews = list(
            db.execute(
                select(Interview).where(
                    Interview.candidate_profile_id == profile.id,
                    Interview.project_id.in_(verified_project_ids),
                    Interview.status == InterviewStatus.COMPLETED,
                )
            ).scalars()
        )
    project_titles = {p.id: p.title for p in projects}

    coding_accounts = list(
        db.execute(
            select(CodingPlatformAccount).where(
                CodingPlatformAccount.candidate_profile_id == profile.id,
                CodingPlatformAccount.deleted_at.is_(None),
            )
        ).scalars()
    )
    certificates = list(
        db.execute(
            select(Certificate).where(
                Certificate.candidate_profile_id == profile.id, Certificate.deleted_at.is_(None)
            )
        ).scalars()
    )
    experiences = list(
        db.execute(
            select(Experience).where(
                Experience.candidate_profile_id == profile.id, Experience.deleted_at.is_(None)
            )
        ).scalars()
    )
    github_account = db.execute(
        select(GithubAccount).where(
            GithubAccount.candidate_profile_id == profile.id, GithubAccount.deleted_at.is_(None)
        )
    ).scalars().first()
    skills = db.execute(
        select(Skill.name, CandidateSkill.proficiency, CandidateSkill.evidence_weight)
        .join(CandidateSkill, CandidateSkill.skill_id == Skill.id)
        .where(CandidateSkill.candidate_profile_id == profile.id)
    ).all()

    match_summary = None
    if job_posting_id is not None:
        match = db.execute(
            select(MatchResult).where(
                MatchResult.job_posting_id == job_posting_id, MatchResult.candidate_profile_id == profile.id
            )
        ).scalar_one_or_none()
        if match is not None:
            match_summary = {
                "match_score": float(match.match_score),
                "semantic_score": float(match.semantic_score),
                "evidence_score": float(match.evidence_score),
                "matched_required_skills": match.matched_required_skills,
                "matched_desirable_skills": match.matched_desirable_skills,
            }

    return {
        "profile": {
            "headline": profile.headline,
            "college": profile.college,
            "degree": profile.degree.value if profile.degree else None,
            "branch": profile.branch.value if profile.branch else None,
            "graduation_year": profile.graduation_year,
            "location": profile.location,
            "target_role": profile.target_role.value if profile.target_role else None,
            "profile_strength": profile.profile_strength,
            "is_discoverable": profile.is_discoverable,
        },
        "github_account": (
            {
                "username": github_account.github_username,
                "profile_url": github_account.profile_url,
                "verification_status": github_account.verification_status.value,
                "verification_score": float(github_account.verification_score) if github_account.verification_score is not None else None,
            }
            if github_account is not None
            else None
        ),
        "projects": [
            {
                "title": p.title,
                "repo_url": p.repo_url,
                "kind": p.kind.value,
                "technologies": p.technologies,
                "verification_status": p.verification_status.value,
                "verification_score": float(p.verification_score) if p.verification_score is not None else None,
                # Contribution analysis, straight from the stored payload —
                # this is the "contribution analysis" the candidate card
                # constraint names.
                "verification_payload": p.verification_payload,
            }
            for p in projects
        ],
        "coding_platform_accounts": [
            {
                "platform": a.platform.value,
                "handle": a.handle,
                "verification_status": a.verification_status.value,
                "verification_score": float(a.verification_score) if a.verification_score is not None else None,
                "verification_payload": a.verification_payload,
            }
            for a in coding_accounts
        ],
        "certificates": [
            {
                "title": c.title,
                "issuer": c.issuer,
                "verification_status": c.verification_status.value,
                "verification_score": float(c.verification_score) if c.verification_score is not None else None,
            }
            for c in certificates
        ],
        "experiences": [
            {
                "company_name": e.company_name,
                "title": e.title,
                "employment_type": e.employment_type.value,
                "verification_status": e.verification_status.value,
            }
            for e in experiences
        ],
        "skills": [
            {"name": name, "proficiency": proficiency.value, "evidence_weight": float(weight)}
            for name, proficiency, weight in skills
        ],
        "interviews": [
            {
                "interview_id": str(interview.id),
                "project_title": project_titles.get(interview.project_id),
                "total_score": float(interview.total_score) if interview.total_score is not None else None,
                "completed_at": interview.completed_at.isoformat() if interview.completed_at else None,
                # Full per-question transcript + rubric scores — "interview
                # transcript and scores" per the candidate-card constraint —
                # already exactly this shape from `evaluate_interview_task`.
                "evidence_report": interview.evidence_report,
            }
            for interview in interviews
        ],
        "match": match_summary,
    }
