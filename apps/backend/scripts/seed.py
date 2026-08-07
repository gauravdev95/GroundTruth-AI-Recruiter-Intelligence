"""Idempotent demo-data seed, in two independent cohorts.

**Cohort 1 — verification states** (this module). Candidates at varied
verification levels, published jobs with confirmed requirements, a populated
pipeline at every stage, and sample messages/notes. Exercises the *states*:
a rejected claim, a pending repo, a half-finished profile.

**Cohort 2 — the scripted demo** (`seed_demo.py`). One recruiter, ten
students, one open role, sized so the end-to-end hiring flow has a real
spread of candidates to run against.

Idempotent by construction, and the two cohorts are guarded **separately**:
each looks for its own marker account and skips only itself. A database that
already has cohort 1 still gets cohort 2 on the next run, which is what makes
adding a cohort to an existing dev database possible at all. There is no
partial-reseed path *within* a cohort — delete its rows (or the whole
database) and rerun if you want a fresh set.

Deliberately network-free: verification status/scores and embeddings are
written directly rather than dispatched through Celery/real third-party
APIs/a real embedding model, so this runs the same way with or without a
worker, Redis, or a downloaded model cache — a seed script has no business
being flaky because a third party is down, and no business spending 440 MB
of hub download on vectors it only needs to be self-consistent.

Run: `make seed` (from the repo root) or `uv run python -m scripts.seed`
(from `apps/backend`).
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

import structlog
from sqlalchemy import select

# A zero-import leaf module, so this is safe above the deliberate
# patch-before-import dance in `main()` — it caches no client and pulls in no
# provider SDK.
from src.domains.ai.embedding_constants import EMBEDDING_DIMENSIONS

logger = structlog.get_logger(__name__)

SEED_MARKER_EMAIL = "ada.lovelace@seed.groundtruth.dev"
SEED_PASSWORD = "SeedPass1!"
ACME_RECRUITER_EMAIL = "grace.hopper@seed.groundtruth.dev"
INITECH_RECRUITER_EMAIL = "peter.gibbons@seed.groundtruth.dev"
# Tracks the real embedding width rather than restating it: the seeded
# vectors go into the same `vector(N)` column real ones do, so a model
# change that moves N must move these too or every seed insert fails.
EMBEDDING_DIM = EMBEDDING_DIMENSIONS

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

    # The embedder is the one production component this seed can legitimately
    # swap, and the default changed on 2026-08-06 from the deterministic
    # stand-in to the real local model. Why:
    #
    # The stand-in is a hashing trick over tokens, so its "similarity" is
    # proportional token overlap. Between a 90-word candidate profile and a
    # 180-word job description that lands around 0.35-0.40 even when the two
    # describe the same job — and the semantic term carries 0.40 of the score.
    # The consequence was a seeded demo where the strongest possible candidate
    # scored 65 and eight of ten students fell under MATCH_THRESHOLD, which
    # reads as a broken matcher rather than as a stand-in embedder.
    #
    # `local_embedder.py` needs no API key and no network *after* its weights
    # are cached, so the cost of the new default is a one-time ~440 MB hub
    # fetch on a cold cache. `SEED_FAKE_EMBEDDINGS=1` restores the old
    # behaviour for CI and offline boxes, where a fast, dependency-free seed
    # matters more than a realistic spread.
    #
    # Note what is *not* swapped: `matching/scoring.py` runs untouched either
    # way. The seed may choose how text becomes a vector; it may not choose
    # how a vector becomes a score.
    if os.environ.get("SEED_FAKE_EMBEDDINGS") == "1":
        llm_module.get_embedder = lambda: _DeterministicEmbedder()  # type: ignore[assignment]
        print("Embedding with the deterministic stand-in (SEED_FAKE_EMBEDDINGS=1).")
    else:
        print("Embedding with the local sentence-transformers model (set SEED_FAKE_EMBEDDINGS=1 to skip).")

    import src.jobs.dispatch as dispatch_module

    dispatch_module.dispatch = lambda job, task, *, queue, args=None: None  # type: ignore[assignment]

    from src.db.database import SessionLocal
    from src.db import register_models  # noqa: F401 — ensures every model is mapper-configured

    # Imported here, not at module scope: both modules touch app code at
    # import time, and importing them above would bind the *real* embedder
    # before the patch above replaces it — turning a network-free seed into a
    # 440 MB model download.
    from scripts import seed_demo

    # Which cohorts to seed. Both by default; `SEED_COHORT=demo` or
    # `SEED_COHORT=states` for one.
    #
    # This exists because the cohorts share a candidate pool and therefore
    # show up in each other's results. Cohort 1's Ada Lovelace scores 50.5
    # against the demo job — a genuine match by every rule the matcher
    # applies, and a confusing ninth card on a board the demo script says has
    # eight. `SEED_COHORT=demo` is the switch for a clean scripted run;
    # leaving it unset is the honest default, because on a real platform
    # other people's candidates *do* match your job.
    cohort = os.environ.get("SEED_COHORT", "all").lower()
    if cohort not in {"all", "demo", "states"}:
        print(f"Unknown SEED_COHORT={cohort!r} — expected all, demo, or states.")
        sys.exit(1)

    with SessionLocal() as db:
        from src.domains.auth.models import User

        if cohort in {"all", "states"}:
            already_seeded = db.execute(
                select(User).where(User.email == SEED_MARKER_EMAIL)
            ).scalar_one_or_none()
            if already_seeded is not None:
                print(f"Cohort 1 already seeded (found {SEED_MARKER_EMAIL}) — skipping.")
            else:
                _seed(db)

        # Guarded independently — see the module docstring. A database holding
        # only cohort 1 still gets cohort 2 here.
        if cohort in {"all", "demo"}:
            if seed_demo.already_seeded(db):
                print(f"Cohort 2 already seeded (found {seed_demo.DEMO_MARKER_EMAIL}) — skipping.")
            else:
                print("\n--- Demo cohort ---")
                seed_demo.seed_demo(db)

    print("\nSeed complete.")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _seed(db) -> None:  # noqa: ANN001 — Session, imported lazily in main()
    from src.domains.auth import service as auth_service
    from src.domains.auth.models import CandidateProfile, RecruiterProfile
    from src.domains.auth.schemas import CandidateRegisterRequest, RecruiterRegisterRequest
    from src.domains.matching import embeddings as embeddings_module
    from src.domains.matching import service as matching_service
    from src.domains.matching.scoring import get_match_threshold
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
    from src.config.config import get_interview_settings
    from src.domains.interview.models import (
        Interview,
        InterviewDimensionScore,
        InterviewGrounding,
        InterviewQuestion,
        InterviewStage,
        InterviewStatus,
        InterviewTurn,
        TurnRole,
        get_current_rubric_version,
        get_rubric_weights,
    )

    # -----------------------------------------------------------------
    # Recruiters / companies
    # -----------------------------------------------------------------

    def register_recruiter(full_name: str, company: str, email: str) -> tuple[RecruiterProfile, str]:
        user = auth_service.register_recruiter(
            db,
            RecruiterRegisterRequest(
                full_name=full_name, company_name=company, company_email=email,
                password=SEED_PASSWORD, confirm_password=SEED_PASSWORD, captcha_token="test", accept_terms=True,
            ),
        )
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
        user = auth_service.register_candidate(
            db,
            # Signup is email + password only; the name arrives with the
            # first section save below, exactly as it does for a real student.
            CandidateRegisterRequest(email=email, password=SEED_PASSWORD, captcha_token="test"),
        )
        return db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id)).scalar_one()

    def fill_basic(
        profile: CandidateProfile, *, full_name: str, headline: str, college: str,
        grad_year: int, location: str,
    ) -> None:
        student_service.replace_basic_info(
            db, profile,
            student_schemas.BasicInfoRequest(
                full_name=full_name, phone_number="+14155552671",
                headline=headline, college=college, degree="btech", branch="cse",
                graduation_year=grad_year, location=location, target_roles=["backend"],
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
        # Seeded under the *current* rubric, read from config rather than
        # hardcoded — hardcoding a weight table here is how the seed silently
        # drifts from the scorer, producing demo reports whose dimensions the
        # UI has no label for.
        rubric = get_rubric_weights()
        exchanges = [
            (
                f"Walk through how {project.title.lower()} handles request {i}.",
                "It validates input, calls the service layer, and returns a typed response.",
            )
            for i in range(1, 4)
        ]
        started = _utcnow() - timedelta(minutes=20)
        interview = Interview(
            candidate_profile_id=profile.id,
            project_id=project.id,
            grounding=InterviewGrounding.REPOSITORY,
            rubric_version=get_current_rubric_version(),
            status=InterviewStatus.COMPLETED,
            stage=InterviewStage.DONE,
            question_count=len(exchanges),
            current_question_index=len(exchanges) - 1,
            time_limit_seconds=get_interview_settings().interview_time_limit_seconds,
            total_score=total_score,
            started_at=started,
            completed_at=_utcnow(),
            evidence_report={
                "verified_claims": [f"Built and can explain {project.title}."],
                "contradicted_claims": [],
                "unsupported_claims": [],
                "strengths": ["Explained the request path end to end without prompting."],
                "concerns": ["Lighter on failure modes than on the happy path."],
                "summary": f"Knows {project.title} well and explains it clearly.",
            },
        )
        db.add(interview)
        db.flush()

        sequence = 0
        for index, (prompt, answer) in enumerate(exchanges):
            db.add(
                InterviewQuestion(
                    interview_id=interview.id,
                    sequence=index + 1,
                    prompt=prompt,
                    grounded_in={"description": f"file_{index + 1}.py"},
                    expected_signals=["names the component", "explains why, not just what"],
                )
            )
            for role, text in ((TurnRole.INTERVIEWER, prompt), (TurnRole.CANDIDATE, answer)):
                sequence += 1
                db.add(
                    InterviewTurn(
                        interview_id=interview.id,
                        sequence=sequence,
                        role=role,
                        text=text,
                        action="ASK_QUESTION" if role is TurnRole.INTERVIEWER else None,
                        question_index=index,
                        spoken_at=started + timedelta(seconds=sequence * 45),
                    )
                )

        for dimension, weight in rubric.items():
            db.add(
                InterviewDimensionScore(
                    interview_id=interview.id,
                    dimension=dimension,
                    weight=weight,
                    score=total_score,
                    evidence=f"Judged across the whole conversation about {project.title}.",
                    confidence=90.0,
                )
            )

        db.flush()
        return interview

    # Ada — fully verified: verified GitHub, two verified repos with strong
    # contribution, a completed interview, a verified certificate.
    ada = register_candidate("Ada Lovelace", SEED_MARKER_EMAIL)
    fill_basic(ada, full_name="Ada Lovelace", headline="Backend engineer intern candidate — Python APIs, FastAPI, Postgres", college="IIT Bombay", grad_year=date.today().year, location="Bangalore, India")
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
    fill_basic(grace, full_name="Grace Kim", headline="Frontend engineer, React specialist", college="BITS Pilani", grad_year=date.today().year, location="Bangalore, India")
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
    fill_basic(alan, full_name="Alan Turing", headline="Backend engineer intern candidate — Python APIs and ML infrastructure", college="IIT Delhi", grad_year=date.today().year, location="Bangalore, India")
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
    fill_basic(marie, full_name="Marie Curie", headline="Aspiring data scientist", college="Delhi University", grad_year=date.today().year + 1, location="Delhi, India")

    # Margaret — fully verified, headed for a "hired" outcome in the pipeline below.
    margaret = register_candidate("Margaret Hamilton", "margaret.hamilton@seed.groundtruth.dev")
    fill_basic(margaret, full_name="Margaret Hamilton", headline="Backend engineer intern candidate — Python APIs, reliability-minded", college="NIT Trichy", grad_year=date.today().year, location="Bangalore, India")
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
        """Apply through the real Smart Apply path, which requires a live match.

        Warns loudly when there is no match rather than returning None in
        silence. `apply_to_job` needs a `MatchResult`, so a scoring or
        threshold change that drops a seeded pair below the cut used to empty
        the demo's Kanban board with no diagnostic at all — the board simply
        rendered empty and the cause was three modules away.

        Still returns None rather than raising: a partially-populated demo is
        more useful than a seed script that refuses to finish, and the warning
        names exactly which pair to look at.
        """
        match = db.execute(
            select(matching_service.MatchResult).where(
                matching_service.MatchResult.job_posting_id == job.id,
                matching_service.MatchResult.candidate_profile_id == profile.id,
            )
        ).scalar_one_or_none()
        if match is None:
            print(
                f"  !! no match for {profile.headline or profile.id} x {job.title} — "
                f"below MATCH_THRESHOLD ({get_match_threshold()}), so no application was created. "
                "The demo pipeline will be missing this candidate."
            )
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


def _publish_jobs(db, recruiters_by_key: dict) -> dict:  # noqa: ANN001 — Session
    """Every row of `JOB_SPECS`, walked through the real publish state
    machine, keyed by title for the pipeline section below.

    Titles are unique across `JOB_SPECS` and are what the caller reaches for
    ("Backend Engineer Intern"), so they key the result rather than ids.
    """
    from scripts import seed_helpers as helpers

    jobs_by_title = {}
    for spec in JOB_SPECS:
        job = helpers.publish_job(db, recruiters_by_key[spec["company"]], spec)
        jobs_by_title[job.title] = job
    print(f"Jobs: {len(jobs_by_title)} published across Acme Corp and Initech.")
    return jobs_by_title


def _recompute_all_matching(db) -> None:  # noqa: ANN001 — Session
    from scripts import seed_helpers as helpers

    helpers.recompute_all_matching(db)


if __name__ == "__main__":
    main()
    sys.exit(0)
