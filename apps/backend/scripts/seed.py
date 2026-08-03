"""Idempotent demo-data seed: candidates at varied verification levels,
published jobs with confirmed requirements, a populated pipeline at every
stage, and sample messages/notes.

Idempotent by construction: the first thing this does is look for the
lead seed candidate's account. If it exists, this has already run against
this database and the script exits immediately rather than duplicating
anything. There is no partial-reseed path — delete the seed rows (or the
whole database) and rerun if you want a fresh set.

Deliberately network-free: verification status/scores and embeddings are
written directly rather than dispatched through Celery/real third-party
APIs/a real embedding provider, so this runs the same way with or without
a worker, Redis, or an OpenAI key — a seed script has no business being
flaky because a third party is down.

Run: `make seed` (from the repo root) or `uv run python -m scripts.seed`
(from `apps/backend`).
"""

from __future__ import annotations

import hashlib
import math
import re
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

import structlog
from sqlalchemy import select

logger = structlog.get_logger(__name__)

SEED_MARKER_EMAIL = "ada.lovelace@seed.groundtruth.dev"
SEED_PASSWORD = "SeedPass1!"
ACME_RECRUITER_EMAIL = "grace.hopper@seed.groundtruth.dev"
INITECH_RECRUITER_EMAIL = "peter.gibbons@seed.groundtruth.dev"
EMBEDDING_DIM = 1536

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# The published job board. Two constraints shape every row here, both
# enforced by `matching/service.py::_prefiltered_candidate_ids`:
#
#   * `experience_level` must not be "senior" — the graduation-year window
#     for SENIOR is `None`, meaning no candidate on a student platform is
#     eligible, so a senior job would match nobody and never appear in any
#     candidate's feed.
#   * a non-remote job filters candidates by a location substring. Every
#     seeded candidate is in "Bangalore, India", so any job outside
#     Bangalore is marked remote — otherwise it matches nobody and the
#     job board looks broken rather than varied.
#
# Skills stay within the seeded taxonomy (Python / SQL / JavaScript / React)
# because `CandidateSkill` rows are what the evidence half of the rank-fusion
# score reads; a job requiring a skill no candidate holds scores low on
# evidence and may fall under the 50.0 threshold.
JOB_SPECS: list[dict] = [
    {
        "company": "acme",
        "title": "Backend Engineer Intern",
        "description": (
            "Build APIs in Python using FastAPI, work with Postgres and Celery on the "
            "matching engine. You will own endpoints end to end, write migrations, and "
            "add integration tests alongside every feature."
        ),
        "job_type": "internship",
        "experience_level": "entry",
        "location": "Bangalore",
        "is_remote": False,
        "skills": [("Python", "intermediate"), ("SQL", "novice")],
    },
    {
        "company": "acme",
        "title": "Frontend Engineer Intern",
        "description": (
            "Build React interfaces for the recruiter dashboard, working closely with "
            "design. Expect TypeScript, component libraries, and a real design system."
        ),
        "job_type": "internship",
        "experience_level": "entry",
        "location": "Bangalore",
        "is_remote": False,
        "skills": [("JavaScript", "intermediate"), ("React", "intermediate")],
    },
    {
        "company": "acme",
        "title": "Full Stack Engineer Intern",
        "description": (
            "Work across a Python FastAPI backend and a React frontend. You will ship "
            "features end to end — schema, endpoint, and the interface that consumes it — "
            "on the candidate profile and job feed surfaces."
        ),
        "job_type": "internship",
        "experience_level": "entry",
        "location": "Bangalore",
        "is_remote": False,
        "skills": [("Python", "intermediate"), ("React", "intermediate")],
    },
    {
        "company": "acme",
        "title": "Platform Engineer Intern",
        "description": (
            "Keep the Python services and Postgres databases healthy. Work on Celery "
            "queues, background job reliability, retries and dead-letter handling, and "
            "the observability that makes all of it debuggable."
        ),
        "job_type": "internship",
        "experience_level": "entry",
        "location": "Remote",
        "is_remote": True,
        "skills": [("Python", "intermediate"), ("SQL", "intermediate")],
    },
    {
        "company": "acme",
        "title": "API Integration Engineer",
        "description": (
            "Own the third-party integrations behind verification: GitHub, coding "
            "platforms, and certificate issuers. Heavy Python, careful rate limiting, "
            "and SQL for the evidence trail every check writes."
        ),
        "job_type": "full_time",
        "experience_level": "entry",
        "location": "Bangalore",
        "is_remote": False,
        "skills": [("Python", "advanced"), ("SQL", "intermediate")],
    },
    {
        "company": "acme",
        "title": "React UI Engineer",
        "description": (
            "Own the candidate-facing React application. Build accessible, fast "
            "interfaces in JavaScript and TypeScript, and care about how the evidence "
            "on a profile is actually communicated to a recruiter."
        ),
        "job_type": "full_time",
        "experience_level": "entry",
        "location": "Remote",
        "is_remote": True,
        "skills": [("JavaScript", "advanced"), ("React", "advanced")],
    },
    {
        "company": "initech",
        "title": "Data Engineer Intern",
        "description": (
            "Build data pipelines in Python and SQL feeding the analytics warehouse. "
            "You will model tables, schedule batch jobs, and keep the numbers the "
            "business reads on trustworthy."
        ),
        "job_type": "internship",
        "experience_level": "entry",
        "location": "Bangalore",
        "is_remote": False,
        "skills": [("Python", "intermediate"), ("SQL", "intermediate")],
    },
    {
        "company": "initech",
        "title": "Machine Learning Intern",
        "description": (
            "Work on ranking and recommendation models in Python. Prototype in "
            "notebooks, then help move what works into a real service backed by "
            "Postgres, with offline evaluation before anything ships."
        ),
        "job_type": "internship",
        "experience_level": "entry",
        "location": "Remote",
        "is_remote": True,
        "skills": [("Python", "intermediate"), ("SQL", "novice")],
    },
    {
        "company": "initech",
        "title": "Analytics Engineer Intern",
        "description": (
            "Turn raw product events into models the whole company queries. Deep SQL, "
            "Python for the transformation layer, and a strong bias toward metrics that "
            "are defined once and reused everywhere."
        ),
        "job_type": "internship",
        "experience_level": "entry",
        "location": "Remote",
        "is_remote": True,
        "skills": [("SQL", "advanced"), ("Python", "intermediate")],
    },
    {
        "company": "initech",
        "title": "QA Automation Intern",
        "description": (
            "Write the automated tests that protect the pipeline state machine. Python "
            "for API-level integration tests, JavaScript for browser flows, and a "
            "habit of reproducing a bug before fixing it."
        ),
        "job_type": "internship",
        "experience_level": "entry",
        "location": "Bangalore",
        "is_remote": False,
        "skills": [("Python", "novice"), ("JavaScript", "intermediate")],
    },
]


def _deterministic_vector(text: str) -> list[float]:
    """A stand-in embedder with no API dependency, using the classic
    "hashing trick": each token deterministically votes on one dimension,
    so two texts that share real words (e.g. a candidate's "Python" skill
    and a job description mentioning "Python") land with genuine positive
    cosine similarity, while unrelated texts stay near-orthogonal — unlike
    independently-seeded random vectors, which are always near-orthogonal
    regardless of content and would make every match score fail the
    threshold. Deterministic per input, so reruns are still idempotent.
    """
    vector = [0.0] * EMBEDDING_DIM
    for token in _TOKEN_RE.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def main() -> None:
    # Patched before any app module that might cache a client is imported
    # from here on, same reasoning as `tests/conftest.py`.
    from src.domains.ai import llm as llm_module

    class _DeterministicEmbedder:
        def embed(self, text: str) -> list[float]:
            return _deterministic_vector(text)

    llm_module.get_embedder = lambda: _DeterministicEmbedder()  # type: ignore[assignment]

    import src.jobs.dispatch as dispatch_module

    dispatch_module.dispatch = lambda job, task, *, queue, args=None: None  # type: ignore[assignment]

    from src.db.database import SessionLocal
    from src.db import register_models  # noqa: F401 — ensures every model is mapper-configured

    with SessionLocal() as db:
        from src.domains.auth.models import User

        already_seeded = db.execute(select(User).where(User.email == SEED_MARKER_EMAIL)).scalar_one_or_none()
        if already_seeded is not None:
            print(f"Already seeded (found {SEED_MARKER_EMAIL}) — nothing to do.")
            return

        _seed(db)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _seed(db) -> None:  # noqa: ANN001 — Session, imported lazily in main()
    from src.domains.auth import service as auth_service
    from src.domains.auth.models import CandidateProfile, RecruiterProfile
    from src.domains.auth.schemas import CandidateRegisterRequest, RecruiterRegisterRequest
    from src.domains.matching import embeddings as embeddings_module
    from src.domains.matching import service as matching_service
    from src.domains.matching.models import EmbeddableEntityType
    from src.domains.pipeline import messaging as messaging_module
    from src.domains.pipeline import notes as notes_module
    from src.domains.pipeline import service as pipeline_service
    from src.domains.pipeline.models import ApplicationStatus
    from src.domains.recruiter import service as recruiter_service
    from src.domains.recruiter.schemas import JobCreateRequest, JobRequirementsConfirmRequest, RequirementSkillRequest
    from src.domains.ai.job_extraction_schema import ExtractedSkill, JobRequirementExtraction
    from src.domains.skills.models import CandidateSkill, ProficiencyLevel, Skill, SkillCategory
    from src.domains.student import schemas as student_schemas
    from src.domains.student import service as student_service
    from src.domains.student.models import (
        Certificate,
        CodingPlatform,
        CodingPlatformAccount,
        GithubAccount,
        Project,
        ProjectKind,
        VerificationStatus,
    )
    from src.domains.interview.models import Interview, InterviewStatus

    # -----------------------------------------------------------------
    # Recruiters / companies
    # -----------------------------------------------------------------

    def register_recruiter(full_name: str, company: str, email: str) -> tuple[RecruiterProfile, str]:
        user, otp, _ = auth_service.register_recruiter(
            db,
            RecruiterRegisterRequest(
                full_name=full_name, company_name=company, company_email=email,
                password=SEED_PASSWORD, confirm_password=SEED_PASSWORD, captcha_token="test", accept_terms=True,
            ),
        )
        auth_service.confirm_email_otp(db, user.email, otp)
        profile = db.execute(select(RecruiterProfile).where(RecruiterProfile.user_id == user.id)).scalar_one()
        return profile, email

    acme_recruiter, acme_email = register_recruiter("Grace Hopper", "Acme Corp", "grace.hopper@seed.groundtruth.dev")
    initech_recruiter, initech_email = register_recruiter(
        "Peter Gibbons", "Initech", "peter.gibbons@seed.groundtruth.dev"
    )
    print(f"Recruiters: {acme_email} / {SEED_PASSWORD}  (Acme Corp)")
    print(f"            {initech_email} / {SEED_PASSWORD}  (Initech)")

    # -----------------------------------------------------------------
    # Skills (shared taxonomy row per name — get-or-create)
    # -----------------------------------------------------------------

    def get_or_create_skill(name: str, category: SkillCategory) -> Skill:
        existing = db.execute(select(Skill).where(Skill.name == name)).scalar_one_or_none()
        if existing is not None:
            return existing
        skill = Skill(name=name, category=category)
        db.add(skill)
        db.flush()
        return skill

    py_skill = get_or_create_skill("Python", SkillCategory.LANGUAGE)
    js_skill = get_or_create_skill("JavaScript", SkillCategory.LANGUAGE)
    react_skill = get_or_create_skill("React", SkillCategory.FRAMEWORK)
    sql_skill = get_or_create_skill("SQL", SkillCategory.TOOL)

    # -----------------------------------------------------------------
    # Candidates at varied verification levels
    # -----------------------------------------------------------------

    def register_candidate(full_name: str, email: str) -> CandidateProfile:
        user, otp, _ = auth_service.register_candidate(
            db,
            CandidateRegisterRequest(
                full_name=full_name, email=email, phone_number="+14155552671",
                password=SEED_PASSWORD, confirm_password=SEED_PASSWORD, captcha_token="test", accept_terms=True,
            ),
        )
        auth_service.confirm_email_otp(db, user.email, otp)
        return db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id)).scalar_one()

    def fill_basic(profile: CandidateProfile, *, headline: str, college: str, grad_year: int, location: str) -> None:
        student_service.replace_basic_info(
            db, profile,
            student_schemas.BasicInfoRequest(
                headline=headline, college=college, degree="btech", branch="cse",
                graduation_year=grad_year, location=location, target_role="backend",
            ),
        )

    def fill_technical(profile: CandidateProfile, *, github_username: str, leetcode_handle: str) -> None:
        student_service.replace_technical(
            db, profile,
            student_schemas.TechnicalRequest(
                github_username=github_username,
                coding_profiles=[student_schemas.CodingPlatformItem(platform=CodingPlatform.LEETCODE, handle=leetcode_handle)],
            ),
        )

    def add_skill(profile: CandidateProfile, skill: Skill, proficiency: ProficiencyLevel, weight: float) -> None:
        existing = db.execute(
            select(CandidateSkill).where(
                CandidateSkill.candidate_profile_id == profile.id, CandidateSkill.skill_id == skill.id
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.proficiency = proficiency
            existing.evidence_weight = weight
            return
        db.add(
            CandidateSkill(
                candidate_profile_id=profile.id, skill_id=skill.id, proficiency=proficiency, evidence_weight=weight
            )
        )

    def set_github_status(
        profile: CandidateProfile, *, status: VerificationStatus, score: float | None = None
    ) -> GithubAccount:
        account = db.execute(
            select(GithubAccount).where(GithubAccount.candidate_profile_id == profile.id)
        ).scalar_one()
        account.verification_status = status
        account.verification_score = score
        account.verification_source = "github_api"
        account.verified_at = _utcnow() if status is VerificationStatus.VERIFIED else None
        return account

    def add_project(
        profile: CandidateProfile, *, title: str, repo_url: str, technologies: list[str],
        status: VerificationStatus, contribution_share: float | None = None, score: float | None = None,
    ) -> Project:
        project = Project(
            candidate_profile_id=profile.id, kind=ProjectKind.REPOSITORY, title=title, repo_url=repo_url,
            technologies=technologies, verification_status=status,
            verification_score=score, verification_source="github_api" if status != VerificationStatus.UNVERIFIED else None,
            verified_at=_utcnow() if status is VerificationStatus.VERIFIED else None,
            verification_payload=(
                {
                    "owner": repo_url.rstrip("/").split("/")[-2],
                    "repo": repo_url.rstrip("/").split("/")[-1],
                    "is_fork": False,
                    "contribution_share": contribution_share,
                    "detected_technologies": technologies,
                }
                if contribution_share is not None
                else None
            ),
        )
        db.add(project)
        db.flush()
        return project

    def add_certificate(
        profile: CandidateProfile, *, title: str, issuer: str, status: VerificationStatus
    ) -> Certificate:
        cert = Certificate(
            candidate_profile_id=profile.id, title=title, issuer=issuer, verification_status=status,
            verification_source="certificate_url_check" if status != VerificationStatus.UNVERIFIED else None,
            verified_at=_utcnow() if status is VerificationStatus.VERIFIED else None,
        )
        db.add(cert)
        db.flush()
        return cert

    def add_completed_interview(profile: CandidateProfile, project: Project, *, total_score: float) -> Interview:
        questions = [
            {
                "sequence": i,
                "prompt": f"Walk through how {project.title.lower()} handles request {i}.",
                "grounded_in": {"description": f"file_{i}.py"},
                "transcript": "It validates input, calls the service layer, and returns a typed response.",
                "time_taken_seconds": 90,
                "exceeded_time_limit": False,
                "scores": [
                    {"dimension": "technical_accuracy", "weight": 0.40, "score": total_score, "rationale": "Accurate and specific."},
                    {"dimension": "depth_of_reasoning", "weight": 0.25, "score": total_score - 5, "rationale": "Reasonable depth."},
                    {"dimension": "codebase_specificity", "weight": 0.20, "score": total_score, "rationale": "Grounded in the real repo."},
                    {"dimension": "repository_consistency", "weight": 0.15, "score": total_score, "rationale": "Consistent with stored analysis."},
                ],
                "weighted_score": total_score,
            }
            for i in range(1, 4)
        ]
        interview = Interview(
            candidate_profile_id=profile.id,
            project_id=project.id,
            status=InterviewStatus.COMPLETED,
            question_count=len(questions),
            total_score=total_score,
            started_at=_utcnow() - timedelta(minutes=20),
            completed_at=_utcnow(),
            evidence_report={
                "interview_id": str(uuid.uuid4()),
                "project_id": str(project.id),
                "total_score": total_score,
                "rubric_weights": {
                    "technical_accuracy": 0.40, "depth_of_reasoning": 0.25,
                    "codebase_specificity": 0.20, "repository_consistency": 0.15,
                },
                "questions": questions,
                "completed_at": _utcnow().isoformat(),
            },
        )
        db.add(interview)
        db.flush()
        return interview

    # Ada — fully verified: verified GitHub, two verified repos with strong
    # contribution, a completed interview, a verified certificate.
    ada = register_candidate("Ada Lovelace", SEED_MARKER_EMAIL)
    fill_basic(ada, headline="Backend engineer intern candidate — Python APIs, FastAPI, Postgres", college="IIT Bombay", grad_year=date.today().year, location="Bangalore, India")
    fill_technical(ada, github_username="ada-seed", leetcode_handle="ada_lc")
    set_github_status(ada, status=VerificationStatus.VERIFIED, score=95.0)
    ada_project = add_project(
        ada, title="Distributed Cache", repo_url="https://github.com/ada-seed/distributed-cache",
        technologies=["Python", "Redis"], status=VerificationStatus.VERIFIED, contribution_share=0.92, score=91.0,
    )
    add_project(
        ada, title="Toy Compiler", repo_url="https://github.com/ada-seed/toy-compiler",
        technologies=["Python"], status=VerificationStatus.VERIFIED, contribution_share=0.88, score=87.0,
    )
    add_certificate(ada, title="AWS Certified Solutions Architect", issuer="Amazon Web Services", status=VerificationStatus.VERIFIED)
    add_skill(ada, py_skill, ProficiencyLevel.EXPERT, 0.95)
    add_skill(ada, sql_skill, ProficiencyLevel.ADVANCED, 0.8)
    db.flush()
    add_completed_interview(ada, ada_project, total_score=88.0)

    # Grace — partially verified: verified GitHub, one repo still pending,
    # profile complete and discoverable.
    grace = register_candidate("Grace Kim", "grace.kim@seed.groundtruth.dev")
    fill_basic(grace, headline="Frontend engineer, React specialist", college="BITS Pilani", grad_year=date.today().year, location="Bangalore, India")
    fill_technical(grace, github_username="grace-seed", leetcode_handle="grace_lc")
    set_github_status(grace, status=VerificationStatus.VERIFIED, score=80.0)
    add_project(
        grace, title="Design System", repo_url="https://github.com/grace-seed/design-system",
        technologies=["React", "TypeScript"], status=VerificationStatus.PENDING,
    )
    add_skill(grace, js_skill, ProficiencyLevel.ADVANCED, 0.85)
    add_skill(grace, react_skill, ProficiencyLevel.ADVANCED, 0.85)

    # Alan — a claim that failed verification: profile complete, but the
    # one listed repo was checked and rejected (near-empty fork).
    alan = register_candidate("Alan Turing", "alan.turing@seed.groundtruth.dev")
    fill_basic(alan, headline="Backend engineer intern candidate — Python APIs and ML infrastructure", college="IIT Delhi", grad_year=date.today().year, location="Bangalore, India")
    fill_technical(alan, github_username="alan-seed", leetcode_handle="alan_lc")
    set_github_status(alan, status=VerificationStatus.VERIFIED, score=60.0)
    add_project(
        alan, title="Forked ML Repo", repo_url="https://github.com/alan-seed/forked-ml-repo",
        technologies=["Python"], status=VerificationStatus.REJECTED, contribution_share=0.02, score=8.0,
    )
    add_skill(alan, py_skill, ProficiencyLevel.INTERMEDIATE, 0.45)
    add_skill(alan, sql_skill, ProficiencyLevel.INTERMEDIATE, 0.55)

    # Marie — freshly registered: only the mandatory basic section filled,
    # not yet discoverable, nothing verified.
    marie = register_candidate("Marie Curie", "marie.curie@seed.groundtruth.dev")
    fill_basic(marie, headline="Aspiring data scientist", college="Delhi University", grad_year=date.today().year + 1, location="Delhi, India")

    # Margaret — fully verified, headed for a "hired" outcome in the pipeline below.
    margaret = register_candidate("Margaret Hamilton", "margaret.hamilton@seed.groundtruth.dev")
    fill_basic(margaret, headline="Backend engineer intern candidate — Python APIs, reliability-minded", college="NIT Trichy", grad_year=date.today().year, location="Bangalore, India")
    fill_technical(margaret, github_username="margaret-seed", leetcode_handle="margaret_lc")
    set_github_status(margaret, status=VerificationStatus.VERIFIED, score=90.0)
    margaret_project = add_project(
        margaret, title="API Gateway", repo_url="https://github.com/margaret-seed/api-gateway",
        technologies=["Python", "FastAPI"], status=VerificationStatus.VERIFIED, contribution_share=0.95, score=93.0,
    )
    add_skill(margaret, py_skill, ProficiencyLevel.EXPERT, 0.9)
    add_skill(margaret, sql_skill, ProficiencyLevel.ADVANCED, 0.7)
    db.flush()
    add_completed_interview(margaret, margaret_project, total_score=92.0)

    for profile in (ada, grace, alan, margaret):
        student_service.recompute_and_persist_strength(db, profile.id)
    db.commit()
    print(
        f"Candidates: {SEED_MARKER_EMAIL}, grace.kim@..., alan.turing@..., "
        f"marie.curie@..., margaret.hamilton@... (all @seed.groundtruth.dev, password {SEED_PASSWORD})"
    )

    # -----------------------------------------------------------------
    # Jobs — created, extracted (hand-built, no LLM), confirmed/published
    # -----------------------------------------------------------------

    jobs_by_title = _publish_jobs(db, {"acme": acme_recruiter, "initech": initech_recruiter})
    backend_job = jobs_by_title["Backend Engineer Intern"]
    frontend_job = jobs_by_title["Frontend Engineer Intern"]

    # -----------------------------------------------------------------
    # Embeddings + matching (deterministic embedder, real scoring code path)
    # -----------------------------------------------------------------

    _recompute_all_matching(db)

    # -----------------------------------------------------------------
    # Pipeline: applications at every stage, messages, a private note
    # -----------------------------------------------------------------

    def smart_apply(profile: CandidateProfile, job) -> object | None:
        match = db.execute(
            select(matching_service.MatchResult).where(
                matching_service.MatchResult.job_posting_id == job.id,
                matching_service.MatchResult.candidate_profile_id == profile.id,
            )
        ).scalar_one_or_none()
        if match is None:
            return None
        return pipeline_service.apply_to_job(db, profile, job.id, cover_note="Excited to contribute — seeded demo application.")

    ada_application = smart_apply(ada, backend_job)
    grace_application = smart_apply(grace, frontend_job)
    alan_application = smart_apply(alan, backend_job)
    margaret_application = smart_apply(margaret, backend_job)

    acme_user = db.execute(select(RecruiterProfile).where(RecruiterProfile.id == acme_recruiter.id)).scalar_one()
    from src.domains.auth.models import User as UserModel

    acme_user_row = db.get(UserModel, acme_recruiter.user_id)

    if ada_application is not None:
        pipeline_service.transition_status(db, acme_user_row, ada_application, to_status=ApplicationStatus.SHORTLISTED)
        pipeline_service.transition_status(db, acme_user_row, ada_application, to_status=ApplicationStatus.INTERVIEW_SCHEDULED)
        messaging_module.send_message(db, acme_user_row, ada_application, body="Thanks for applying — we'd love to schedule a call this week.")
        notes_module.add_note(db, acme_recruiter, ada_application.id, body="Strong repo contribution history and a completed code interview. Fast-track.")

    if grace_application is not None:
        pipeline_service.transition_status(db, acme_user_row, grace_application, to_status=ApplicationStatus.SHORTLISTED)

    if alan_application is not None:
        pipeline_service.transition_status(db, acme_user_row, alan_application, to_status=ApplicationStatus.REJECTED)
        notes_module.add_note(db, acme_recruiter, alan_application.id, body="Listed repo failed verification (near-empty fork). Passing for now.")

    if margaret_application is not None:
        pipeline_service.transition_status(db, acme_user_row, margaret_application, to_status=ApplicationStatus.SHORTLISTED)
        pipeline_service.transition_status(db, acme_user_row, margaret_application, to_status=ApplicationStatus.INTERVIEW_SCHEDULED)
        pipeline_service.transition_status(db, acme_user_row, margaret_application, to_status=ApplicationStatus.HIRED)
        messaging_module.send_message(db, acme_user_row, margaret_application, body="Congratulations — we'd like to extend an offer!")

    db.commit()
    print("Pipeline populated: applied, shortlisted, interview-scheduled, hired, and rejected applications, with sample messages and a private note.")
    print("\nSeed complete.")


if __name__ == "__main__":
    main()
    sys.exit(0)
