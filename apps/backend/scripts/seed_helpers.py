"""Shared building blocks for the seed cohorts.

Extracted from `seed.py`, which grew a second cohort (`seed_demo.py`) and
would otherwise hold two divergent copies of "make a candidate with a
verified repo and a completed interview".

**Import ordering matters.** Every function here touches app modules at
module scope, so this module must not be imported until `seed.py::main()`
has patched `llm.get_embedder` and `jobs.dispatch.dispatch`. `main()`
imports it lazily for exactly that reason; importing it at the top of
`seed.py` would pull the real embedder into the process and turn a
network-free seed into a 440 MB model download.

Everything here writes through the **real service layer** wherever one
exists (`auth_service.register_candidate`, `student_service.replace_*`,
`recruiter_service.confirm_requirements`) rather than inserting rows
directly. That is what keeps the seed honest: a validator or state-machine
rule the product enforces is a rule the seed data also obeys, so a demo
profile is reachable by a real student doing real things. Verification
*outcomes* are the deliberate exception — those are written directly,
because the alternative is calling GitHub and Codeforces from a seed script.
"""

from __future__ import annotations

import hashlib
import math
import re
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domains.ai.embedding_constants import EMBEDDING_DIMENSIONS
from src.domains.ai.job_extraction_schema import ExtractedSkill, JobRequirementExtraction
from src.domains.auth import service as auth_service
from src.domains.auth.models import CandidateProfile, RecruiterProfile
from src.domains.auth.schemas import CandidateRegisterRequest, RecruiterRegisterRequest
from src.domains.interview.models import (
    Interview,
    InterviewGrounding,
    InterviewStatus,
    get_current_rubric_version,
    get_rubric_weights,
)
from src.domains.matching import embeddings as embeddings_module
from src.domains.matching import service as matching_service
from src.domains.recruiter import service as recruiter_service
from src.domains.recruiter.models import JobPosting, JobStatus
from src.domains.recruiter.schemas import (
    JobCreateRequest,
    JobRequirementsConfirmRequest,
    RequirementSkillRequest,
)
from src.domains.skills.models import CandidateSkill, ProficiencyLevel, Skill, SkillCategory
from src.domains.student import schemas as student_schemas
from src.domains.student import service as student_service
from src.domains.student.models import (
    Certificate,
    CodingPlatform,
    CodingPlatformAccount,
    Experience,
    GithubAccount,
    Project,
    ProjectKind,
    VerificationStatus,
)

#: Tracks the real embedding width rather than restating it: seeded vectors go
#: into the same `vector(N)` column real ones do.
EMBEDDING_DIM = EMBEDDING_DIMENSIONS

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def deterministic_vector(text: str) -> list[float]:
    """A stand-in embedder with no API dependency, using the classic "hashing
    trick": each token deterministically votes on one dimension, so two texts
    sharing real words (a candidate's "Rust" skill and a job description
    mentioning "Rust") land with genuine positive cosine similarity, while
    unrelated texts stay near-orthogonal — unlike independently-seeded random
    vectors, which are near-orthogonal regardless of content and would make
    every match score fail the threshold.
    """
    vector = [0.0] * EMBEDDING_DIM
    for token in _TOKEN_RE.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------


def register_recruiter(
    db: Session, *, full_name: str, company: str, email: str, password: str
) -> RecruiterProfile:
    user = auth_service.register_recruiter(
        db,
        RecruiterRegisterRequest(
            full_name=full_name,
            company_name=company,
            company_email=email,
            password=password,
            confirm_password=password,
            captcha_token="test",
            accept_terms=True,
        ),
    )
    return db.execute(select(RecruiterProfile).where(RecruiterProfile.user_id == user.id)).scalar_one()


def register_candidate(db: Session, *, email: str, password: str) -> CandidateProfile:
    """Signup is email + password only; the name arrives with the first
    section save, exactly as it does for a real student."""
    user = auth_service.register_candidate(
        db, CandidateRegisterRequest(email=email, password=password, captcha_token="test")
    )
    return db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id)).scalar_one()


# --------------------------------------------------------------------------
# Profile sections
# --------------------------------------------------------------------------


def fill_basic(
    db: Session,
    profile: CandidateProfile,
    *,
    full_name: str,
    headline: str,
    college: str,
    grad_year: int,
    location: str,
    degree: str = "btech",
    branch: str = "cse",
    target_roles: list[str] | None = None,
    about: str | None = None,
) -> None:
    student_service.replace_basic_info(
        db,
        profile,
        student_schemas.BasicInfoRequest(
            full_name=full_name,
            phone_number="+14155552671",
            headline=headline,
            college=college,
            degree=degree,
            branch=branch,
            graduation_year=grad_year,
            location=location,
            target_roles=target_roles or ["backend"],
            about=about,
        ),
    )


def fill_technical(
    db: Session,
    profile: CandidateProfile,
    *,
    github_username: str,
    coding_profiles: list[tuple[CodingPlatform, str]] | None = None,
) -> None:
    """`coding_profiles` may be empty — two of the demo students genuinely
    have no competitive-programming presence, and the section allows it."""
    student_service.replace_technical(
        db,
        profile,
        student_schemas.TechnicalRequest(
            github_username=github_username,
            coding_profiles=[
                student_schemas.CodingPlatformItem(platform=platform, handle=handle)
                for platform, handle in (coding_profiles or [])
            ],
        ),
    )


# --------------------------------------------------------------------------
# Skills and verification outcomes
# --------------------------------------------------------------------------


def get_or_create_skill(db: Session, name: str, category: SkillCategory) -> Skill:
    existing = db.execute(select(Skill).where(Skill.name == name)).scalar_one_or_none()
    if existing is not None:
        return existing
    skill = Skill(name=name, category=category)
    db.add(skill)
    db.flush()
    return skill


def add_skill(
    db: Session, profile: CandidateProfile, skill: Skill, proficiency: ProficiencyLevel, weight: float
) -> None:
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
            candidate_profile_id=profile.id,
            skill_id=skill.id,
            proficiency=proficiency,
            evidence_weight=weight,
        )
    )


def set_github_status(
    db: Session, profile: CandidateProfile, *, status: VerificationStatus, score: float | None = None
) -> GithubAccount:
    account = db.execute(
        select(GithubAccount).where(GithubAccount.candidate_profile_id == profile.id)
    ).scalar_one()
    account.verification_status = status
    account.verification_score = score
    account.verification_source = "github_api"
    account.verified_at = utcnow() if status is VerificationStatus.VERIFIED else None
    return account


def set_coding_status(
    db: Session,
    profile: CandidateProfile,
    *,
    platform: CodingPlatform,
    status: VerificationStatus,
    score: float | None = None,
    payload: dict | None = None,
) -> CodingPlatformAccount | None:
    """Writes the verification outcome onto an already-claimed handle.

    `payload` is where a rating and contest count live — the same
    `verification_payload` column the real Codeforces client writes, which is
    what the recruiter drawer reads under "Supporting Signals". Returns None
    when the candidate never claimed this platform, so a caller can pass the
    same table row for students with and without a handle.
    """
    account = db.execute(
        select(CodingPlatformAccount).where(
            CodingPlatformAccount.candidate_profile_id == profile.id,
            CodingPlatformAccount.platform == platform,
        )
    ).scalar_one_or_none()
    if account is None:
        return None
    account.verification_status = status
    account.verification_score = score
    account.verification_source = f"{platform.value}_api"
    account.verification_payload = payload
    account.verified_at = utcnow() if status is VerificationStatus.VERIFIED else None
    return account


# --------------------------------------------------------------------------
# Profile content
# --------------------------------------------------------------------------


def add_project(
    db: Session,
    profile: CandidateProfile,
    *,
    title: str,
    repo_url: str,
    technologies: list[str],
    status: VerificationStatus,
    description: str | None = None,
    contribution_share: float | None = None,
    score: float | None = None,
    commit_count: int | None = None,
) -> Project:
    payload: dict | None = None
    if contribution_share is not None:
        payload = {
            "owner": repo_url.rstrip("/").split("/")[-2],
            "repo": repo_url.rstrip("/").split("/")[-1],
            "is_fork": False,
            "contribution_share": contribution_share,
            "detected_technologies": technologies,
        }
        # The drawer renders a commit count when the checker recorded one.
        # Omitted rather than defaulted to 0 where unknown — a zero here would
        # read as "checked, found nothing" instead of "not recorded".
        if commit_count is not None:
            payload["commit_count"] = commit_count

    project = Project(
        candidate_profile_id=profile.id,
        kind=ProjectKind.REPOSITORY,
        title=title,
        description=description,
        repo_url=repo_url,
        technologies=technologies,
        verification_status=status,
        verification_score=score,
        verification_source="github_api" if status != VerificationStatus.UNVERIFIED else None,
        verified_at=utcnow() if status is VerificationStatus.VERIFIED else None,
        verification_payload=payload,
    )
    db.add(project)
    db.flush()
    return project


def add_certificate(
    db: Session,
    profile: CandidateProfile,
    *,
    title: str,
    issuer: str,
    status: VerificationStatus,
    credential_url: str | None = None,
) -> Certificate:
    cert = Certificate(
        candidate_profile_id=profile.id,
        title=title,
        issuer=issuer,
        credential_url=credential_url,
        verification_status=status,
        verification_source="certificate_url_check" if status != VerificationStatus.UNVERIFIED else None,
        verified_at=utcnow() if status is VerificationStatus.VERIFIED else None,
    )
    db.add(cert)
    db.flush()
    return cert


def add_experience(
    db: Session,
    profile: CandidateProfile,
    *,
    company_name: str,
    title: str,
    employment_type,  # noqa: ANN001 — EmploymentType, kept loose so callers pass the enum directly
    start_date: date,
    end_date: date | None,
    technologies: list[str],
    description: str | None = None,
    position: int = 0,
) -> Experience:
    """Deliberately left `UNVERIFIED`. `Experience` has no third-party source
    of truth and can never reach `VERIFIED` (see the model docstring); seeding
    one as verified would put a claim on screen with a badge the real system
    could never award it.
    """
    row = Experience(
        candidate_profile_id=profile.id,
        company_name=company_name,
        title=title,
        employment_type=employment_type,
        start_date=start_date,
        end_date=end_date,
        description=description,
        technologies=technologies,
        position=position,
        verification_status=VerificationStatus.UNVERIFIED,
    )
    db.add(row)
    db.flush()
    return row


def add_completed_interview(
    db: Session,
    profile: CandidateProfile,
    project: Project,
    *,
    total_score: float,
    highlights: list[dict] | None = None,
    dimension_scores: dict[str, float] | None = None,
) -> Interview:
    """A completed, code-grounded interview with a full evidence report.

    Seeded under the **current** rubric, read from config rather than
    hardcoded — a hardcoded weight table is how a seed silently drifts from
    the scorer and produces demo reports whose dimensions the UI has no label
    for.

    `highlights` supplies real per-question prompts and answers; without it
    the questions are generated from the project title, which is enough for a
    cohort whose interviews are never opened. `dimension_scores` lets a
    persona score unevenly across the rubric (strong on accuracy, weaker on
    communication) instead of flat-lining every dimension at `total_score`,
    which is what makes the drawer's breakdown chart worth rendering.
    """
    rubric = get_rubric_weights()
    default_rationales = {
        "technical_accuracy": "Accurate and specific.",
        "code_understanding": "Matches the stored analysis.",
        "problem_solving": "Reasoned about tradeoffs, not just mechanics.",
        "repository_knowledge": "Grounded in the real repo.",
        "communication": "Clear and well-structured.",
    }

    def score_for(dimension: str) -> float:
        return (dimension_scores or {}).get(dimension, total_score)

    if highlights:
        questions = [
            {
                "sequence": index,
                "prompt": item["prompt"],
                "grounded_in": {"description": item.get("grounded_in", f"{project.title} source")},
                "transcript": item["transcript"],
                "time_taken_seconds": item.get("time_taken_seconds", 95),
                "exceeded_time_limit": False,
                "scores": [
                    {
                        "dimension": dimension,
                        "weight": weight,
                        "score": score_for(dimension),
                        "rationale": item.get("rationale") or default_rationales.get(dimension, "Scored against the rubric."),
                    }
                    for dimension, weight in rubric.items()
                ],
                "weighted_score": round(
                    sum(score_for(dimension) * weight for dimension, weight in rubric.items()), 2
                ),
            }
            for index, item in enumerate(highlights, start=1)
        ]
    else:
        questions = [
            {
                "sequence": i,
                "prompt": f"Walk through how {project.title.lower()} handles request {i}.",
                "grounded_in": {"description": f"file_{i}.py"},
                "transcript": "It validates input, calls the service layer, and returns a typed response.",
                "time_taken_seconds": 90,
                "exceeded_time_limit": False,
                "scores": [
                    {
                        "dimension": dimension,
                        "weight": weight,
                        "score": score_for(dimension),
                        "rationale": default_rationales.get(dimension, "Scored against the rubric."),
                    }
                    for dimension, weight in rubric.items()
                ],
                "weighted_score": round(
                    sum(score_for(dimension) * weight for dimension, weight in rubric.items()), 2
                ),
            }
            for i in range(1, 4)
        ]

    interview = Interview(
        candidate_profile_id=profile.id,
        project_id=project.id,
        grounding=InterviewGrounding.REPOSITORY,
        rubric_version=get_current_rubric_version(),
        status=InterviewStatus.COMPLETED,
        question_count=len(questions),
        total_score=total_score,
        started_at=utcnow() - timedelta(minutes=20),
        completed_at=utcnow(),
        evidence_report={
            "interview_id": str(uuid.uuid4()),
            "project_id": str(project.id),
            "total_score": total_score,
            "rubric_weights": dict(rubric),
            "questions": questions,
            "completed_at": utcnow().isoformat(),
        },
    )
    db.add(interview)
    db.flush()
    return interview


# --------------------------------------------------------------------------
# Jobs — the full draft -> extracted -> confirmed -> published walk
# --------------------------------------------------------------------------


def publish_job(db: Session, recruiter: RecruiterProfile, spec: dict) -> JobPosting:
    """Walks one job through the real state machine, standing in for the
    Celery extraction task.

    The seed patches `jobs.dispatch.dispatch` to a no-op, so
    `submit_for_extraction` parks the job in `EXTRACTING` and nothing ever
    arrives to move it on. Rather than reaching into the table and flipping a
    status, this calls `apply_extraction_result` with a **hand-built**
    `JobRequirementExtraction` — the same object the LLM adapter would have
    returned — and then the real `confirm_requirements`. That matters for two
    reasons beyond tidiness:

    * `confirm_requirements` is the only writer of `job_requirements` and the
      only place `embedding_text` is composed. Bypassing it would produce a
      published job with no requirements and no text to embed, which reads as
      "the matcher is broken" three modules away.
    * It keeps the mandatory human-in-the-loop gate honest. A seeded job is
      published *through* confirmation, not around it.

    No LLM call happens here, deliberately: the extraction is stated in
    `JOB_SPECS`/`DEMO_JOB` rather than inferred, so seeding works on a box
    with no model key at all.
    """
    job = recruiter_service.create_job(
        db,
        recruiter,
        JobCreateRequest(
            title=spec["title"],
            description=spec["description"],
            job_type=spec["job_type"],
            experience_level=spec["experience_level"],
            location=spec.get("location"),
            is_remote=spec.get("is_remote", False),
            deadline=spec.get("deadline"),
        ),
    )

    recruiter_service.submit_for_extraction(db, job)

    required = [(name, level) for name, level, is_required in _normalised_skills(spec) if is_required]
    desirable = [(name, level) for name, level, is_required in _normalised_skills(spec) if not is_required]
    recruiter_service.apply_extraction_result(
        db,
        job,
        JobRequirementExtraction(
            must_have_skills=[ExtractedSkill(name=name, min_proficiency=level) for name, level in required],
            desirable_skills=[ExtractedSkill(name=name, min_proficiency=level) for name, level in desirable],
            seniority=spec["experience_level"],
            role_type=spec["title"],
            is_remote=spec.get("is_remote", False),
            location_constraints=spec.get("location"),
        ),
    )

    confirmed = recruiter_service.confirm_requirements(
        db,
        job,
        JobRequirementsConfirmRequest(
            skills=[
                RequirementSkillRequest(
                    skill_name=name,
                    min_proficiency=level,
                    is_required=is_required,
                    weight=1.0 if is_required else 0.5,
                )
                for name, level, is_required in _normalised_skills(spec)
            ],
            seniority=spec["experience_level"],
        ),
    )
    return confirmed.job


def _normalised_skills(spec: dict) -> list[tuple[str, str, bool]]:
    """`(name, min_proficiency, is_required)`.

    Accepts both shapes the specs use: a 2-tuple `(name, level)` — every skill
    required, which is what the original `JOB_SPECS` rows are — and a 3-tuple
    that states `is_required`, which the demo job needs so it can carry
    nice-to-haves the radar chart plots against.
    """
    out: list[tuple[str, str, bool]] = []
    for entry in spec["skills"]:
        if len(entry) == 3:
            name, level, is_required = entry
        else:
            name, level = entry
            is_required = True
        out.append((name, level, bool(is_required)))
    return out


# --------------------------------------------------------------------------
# Embeddings + matching
# --------------------------------------------------------------------------


def recompute_all_matching(db: Session) -> None:
    """Embeds every candidate and published job, then runs the real matcher.

    The Celery path (`embed_and_match_job_task`) is dispatched-to-nowhere in
    the seed, so this stands in for it. It calls the same
    `embeddings.embed_*` and `matching.recompute_for_job` the worker calls —
    only the *embedder* is swapped (for the deterministic one patched in by
    `main()`), never the scoring code. A demo whose scores came from a
    different formula than production's would be worse than no demo.

    Jobs are recomputed rather than candidates because the two directions
    write the same `match_results` rows and per-job is the cheaper sweep: one
    pass per job over its prefiltered pool, instead of one pass per candidate
    over every open job.

    ## The step ordering is load-bearing — do not reorder

    `is_discoverable` is `is_indexed and has_completed_interview`, and
    `is_indexed` includes `snapshot.has_embedding`
    (`student/completeness.py::_evaluate`). Meanwhile the matcher's very first
    filter is `is_discoverable is True`
    (`matching/service.py::_prefiltered_candidate_ids`).

    So computing profile strength *before* the candidate embedding exists
    leaves every profile with `is_discoverable = false`, and the matcher then
    finds an empty pool for every job — no error, no warning, just a demo
    where every pipeline is empty and every job feed says "no matches yet".
    That is precisely what this seed did before: strength was recomputed at
    the end of the candidate loop, and embeddings were not written until here.

    Hence: embed, **then** recompute strength (which is what actually flips
    discoverability), then embed jobs, then match.
    """
    profiles = list(db.execute(select(CandidateProfile)).scalars())
    for profile in profiles:
        embeddings_module.embed_candidate_profile(db, profile)
    db.commit()

    # Re-derived now that the embedding rows exist. Cheap and idempotent —
    # `apply_completeness` writes derived values onto the row and nothing
    # else — so running it a second time for candidates whose caller already
    # did costs one query per profile and removes an ordering trap.
    for profile in profiles:
        student_service.recompute_and_persist_strength(db, profile.id)
    db.commit()

    jobs = list(
        db.execute(select(JobPosting).where(JobPosting.status == JobStatus.PUBLISHED)).scalars()
    )
    for job in jobs:
        embeddings_module.embed_job_posting(db, job)
    db.commit()

    for job in jobs:
        matching_service.recompute_for_job(db, job)
    db.commit()
