"""The matching pipeline — one computation, in the exact order the task
specified:

    a. relational pre-filter on hard constraints (keeps vector search small)
    b. cosine similarity, job vector against the remaining candidate vectors
    c. rank fusion (semantic + evidence + profile_strength)
    d. threshold cut, then top-K

`recompute_for_job` and `recompute_for_candidate` are the only two entry
points, called from `jobs/tasks/matching.py` after (re-)embedding.

**Both upsert; neither deletes wholesale.** They used to delete every row for
their side and reinsert, which read as "always a consistent replacement" and
was in fact a data-loss bug: a candidate re-verifying a repository dropped
every recruiter board they were on, mid-hiring, including boards where they
had already applied — and `apply_to_job` requires a live `MatchResult`, so the
application's own provenance vanished with it. A recompute now:

* updates pairs that still match,
* inserts pairs that newly match (and reports them, so the caller can notify),
* deletes pairs that no longer match **only if no application references them**.

A pair someone applied through is a historical fact, not a current opinion.
It stays, and `applications.score_at_apply` preserves the number the recruiter
actually decided against even as the live score moves.

Experience-level pre-filtering is honest about what data actually exists:
`candidate_profiles` has no "years of experience" field (this is a student
platform — nobody has one to report), so `experience_level=SENIOR` jobs
match zero candidates by relational pre-filter rather than guessing from a
proxy. `ENTRY`/`MID` use `graduation_year` as the closest real signal
(documented in `_passes_hard_constraints`), not invented data.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domains.auth.models import CandidateProfile
from src.domains.matching.embeddings import get_embedding
from src.domains.pipeline.models import Application
from src.domains.matching.models import EmbeddableEntityType, Embedding, MatchResult
from src.domains.matching.scoring import (
    TOP_K,
    compute_competency_score,
    compute_evidence_score,
    compute_match_score,
    get_match_threshold,
)
from src.domains.verification.competencies import COMPETENCY_NAMES
from src.domains.recruiter.models import ExperienceLevel, JobPosting, JobRequirement, JobStatus
from src.domains.skills.models import CandidateSkill, Skill
from src.domains.student.models import Project, VerificationStatus

# How large a semantic-similarity pool to pull from pgvector before applying
# rank fusion — larger than the eventual top-K so evidence/profile_strength
# can still reorder within a generous shortlist, but bounded so the ANN
# index (not a full table scan) is what does the heavy lifting.
SEMANTIC_POOL_SIZE = 200


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _graduation_year_window(experience_level: ExperienceLevel) -> tuple[int, int] | None:
    """Real proxy from real data, not an invented field. `None` means "no
    candidate on this platform is eligible" — correct for `SENIOR`, since
    nobody here reports years of professional experience."""
    current_year = _utcnow().year
    if experience_level is ExperienceLevel.SENIOR:
        return None
    # ENTRY and MID both mean "graduating around now" on a student platform
    # — there is no data distinguishing them further.
    return (current_year - 1, current_year + 2)


def _deadline_passed(job: JobPosting) -> bool:
    """A job past its deadline matches nobody. Checked at compute time rather
    than filtered at read time: a closed window is a hard constraint like any
    other, and leaving the rows in place would keep showing students jobs they
    can no longer apply to."""
    return job.deadline is not None and job.deadline < _utcnow().date()


def _prefiltered_candidate_ids(db: Session, job: JobPosting) -> list[uuid.UUID]:
    """Step (a): the relational pre-filter, run before any vector math."""
    if _deadline_passed(job):
        return []

    window = _graduation_year_window(job.experience_level)
    if window is None:
        return []

    conditions = [
        CandidateProfile.is_discoverable.is_(True),
        CandidateProfile.graduation_year.is_not(None),
        CandidateProfile.graduation_year >= window[0],
        CandidateProfile.graduation_year <= window[1],
    ]
    if not job.is_remote and job.location:
        # Substring match, not exact — "Bangalore" should match a candidate
        # who wrote "Bangalore, India". Missing candidate location is not
        # excluded (no data is not the same as a mismatch); an explicit
        # mismatch is.
        conditions.append(
            (CandidateProfile.location.is_(None))
            | (CandidateProfile.location.ilike(f"%{job.location}%"))
        )

    return list(db.execute(select(CandidateProfile.id).where(*conditions)).scalars())


def _semantic_pool(
    db: Session, *, job_vector: list[float], candidate_ids: list[uuid.UUID], limit: int
) -> list[tuple[uuid.UUID, float]]:
    """Step (b): cosine similarity, scoped to the pre-filtered id set so the
    ANN index only ever searches within a bounded pool, never the whole
    candidate base."""
    if not candidate_ids:
        return []

    distance = Embedding.vector.cosine_distance(job_vector)
    rows = db.execute(
        select(Embedding.entity_id, distance.label("distance"))
        .where(
            Embedding.entity_type == EmbeddableEntityType.CANDIDATE_PROFILE,
            Embedding.entity_id.in_(candidate_ids),
        )
        .order_by(distance)
        .limit(limit)
    ).all()
    return [(row.entity_id, round(1.0 - float(row.distance), 5)) for row in rows]


#: Competency names, casefolded once, for splitting them back out of the flat
#: skill-weight map. They live in `candidate_skills` like any other skill —
#: that is what lets a recruiter require "Problem Solving" on a job posting —
#: but they are weighted by their own term in the formula, so the two must be
#: separable at scoring time.
_COMPETENCY_KEYS: frozenset[str] = frozenset(name.casefold() for name in COMPETENCY_NAMES)


def _competency_weights(skill_weights: dict[str, float]) -> dict[str, float]:
    """The coding-profile competencies out of a candidate's skill weights.

    Derived from the map already loaded for the evidence term rather than a
    second query: competencies are ordinary `candidate_skills` rows, so they
    are already present, and re-fetching them per candidate would add a query
    per row in the scored pool.
    """
    return {name: weight for name, weight in skill_weights.items() if name in _COMPETENCY_KEYS}


def _candidate_skill_weights(db: Session, candidate_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, float]]:
    if not candidate_ids:
        return {}
    rows = db.execute(
        select(CandidateSkill.candidate_profile_id, Skill.name, CandidateSkill.evidence_weight)
        .join(Skill, Skill.id == CandidateSkill.skill_id)
        .where(CandidateSkill.candidate_profile_id.in_(candidate_ids))
    ).all()
    weights: dict[uuid.UUID, dict[str, float]] = {}
    for candidate_id, skill_name, evidence_weight in rows:
        weights.setdefault(candidate_id, {})[skill_name.casefold()] = float(evidence_weight)
    return weights


def _evidence_sources(projects: list[Project], skill_name: str) -> list[dict]:
    """Traces a matched skill back to concrete, stored evidence — the
    verified repositories whose detected technologies include it. Never
    LLM-narrated (task constraint): every field here is read straight off
    `Project.verification_payload`, written by `verify_repository_task`."""
    sources = []
    for project in projects:
        payload = project.verification_payload or {}
        detected = {name.casefold() for name in payload.get("detected_technologies", [])}
        if skill_name.casefold() in detected or skill_name.casefold() in {t.casefold() for t in project.technologies}:
            sources.append(
                {
                    "type": "project",
                    "project_id": str(project.id),
                    "title": project.title,
                    "repo_url": project.repo_url,
                    "verification_score": float(project.verification_score) if project.verification_score is not None else None,
                }
            )
    return sources[:3]


def _build_match_reasons(
    *,
    requirements: list[JobRequirement],
    skill_id_to_name: dict[uuid.UUID, str],
    candidate_skill_names: dict[str, float],
    candidate_proficiency: dict[str, str],
    candidate_projects: list[Project],
) -> tuple[list[dict], list[dict]]:
    required_reasons: list[dict] = []
    desirable_reasons: list[dict] = []

    for requirement in requirements:
        name = skill_id_to_name[requirement.skill_id]
        key = name.casefold()
        has_evidence = key in candidate_skill_names
        reason = {
            "skill_name": name,
            "candidate_has_skill": has_evidence,
            "candidate_proficiency": candidate_proficiency.get(key),
            "evidence_weight": candidate_skill_names.get(key),
            "evidence_sources": _evidence_sources(candidate_projects, name) if has_evidence else [],
        }
        (required_reasons if requirement.is_required else desirable_reasons).append(reason)

    return required_reasons, desirable_reasons


@dataclass(frozen=True)
class ScoredPair:
    """One computed `(job, candidate)` result, before it is reconciled against
    whatever is already persisted for that pair."""

    job_posting_id: uuid.UUID
    candidate_profile_id: uuid.UUID
    match_score: float
    semantic_score: float
    evidence_score: float
    profile_strength: int
    match_reasons: dict


@dataclass(frozen=True)
class RecomputeResult:
    """`newly_matched` is the notification trigger: pairs that did not exist
    before this run. An updated score on a pair the student has already been
    told about is not news, and notifying on it would turn every
    re-verification into a burst of duplicate alerts."""

    total: int
    newly_matched: tuple[ScoredPair, ...]
    removed: int
    retained_for_applications: int


def _application_linked_pairs(
    db: Session, *, job_posting_ids: list[uuid.UUID], candidate_profile_ids: list[uuid.UUID]
) -> set[tuple[uuid.UUID, uuid.UUID]]:
    """Pairs that an `applications` row depends on. Looked up by the natural
    key rather than by `applications.match_id` so a row whose FK was already
    nulled (an earlier prune, before this protection existed) is still
    recognised as spoken for."""
    if not job_posting_ids and not candidate_profile_ids:
        return set()

    conditions = []
    if job_posting_ids:
        conditions.append(Application.job_posting_id.in_(job_posting_ids))
    if candidate_profile_ids:
        conditions.append(Application.candidate_profile_id.in_(candidate_profile_ids))

    rows = db.execute(
        select(Application.job_posting_id, Application.candidate_profile_id).where(*conditions)
    ).all()
    return {(job_id, candidate_id) for job_id, candidate_id in rows}


def _reconcile(
    db: Session,
    *,
    scored: list[ScoredPair],
    existing: dict[tuple[uuid.UUID, uuid.UUID], MatchResult],
    protected: set[tuple[uuid.UUID, uuid.UUID]],
) -> RecomputeResult:
    """Upsert `scored` over `existing`, then drop what neither still matches
    nor is protected by an application.

    The conflict target is `uq_match_result_pair` — the same constraint the
    natural key `(job_posting_id, candidate_profile_id)` enforces — so a pair
    can never be duplicated no matter which direction recomputed it.
    """
    keep: set[tuple[uuid.UUID, uuid.UUID]] = set()
    newly_matched: list[ScoredPair] = []
    # One timestamp for the whole reconcile, not one per call site. A freshly
    # inserted row must have `computed_at == updated_at` *exactly* — two
    # separate `_utcnow()` calls left them microseconds apart, which is enough
    # for a reader asking "has this been rescored since it first matched?" to
    # answer yes for a row that never has (`matching/schemas.py`).
    now = _utcnow()

    for pair in scored:
        key = (pair.job_posting_id, pair.candidate_profile_id)
        keep.add(key)
        row = existing.get(key)

        if row is None:
            db.add(
                MatchResult(
                    job_posting_id=pair.job_posting_id,
                    candidate_profile_id=pair.candidate_profile_id,
                    match_score=pair.match_score,
                    semantic_score=pair.semantic_score,
                    evidence_score=pair.evidence_score,
                    profile_strength_at_match=pair.profile_strength,
                    match_reasons=pair.match_reasons,
                    computed_at=now,
                    updated_at=now,
                )
            )
            newly_matched.append(pair)
        else:
            # `computed_at` is deliberately untouched: it records when this
            # pair first matched, which is what "you matched N days ago" means
            # to a student. `updated_at` carries the rescore.
            row.match_score = pair.match_score
            row.semantic_score = pair.semantic_score
            row.evidence_score = pair.evidence_score
            row.profile_strength_at_match = pair.profile_strength
            row.match_reasons = pair.match_reasons
            row.updated_at = now

    removed = 0
    retained = 0
    for key, row in existing.items():
        if key in keep:
            continue
        if key in protected:
            # No longer above threshold, but an application depends on it.
            # Kept so the recruiter's board and the application's provenance
            # survive a candidate's later re-verification.
            retained += 1
            continue
        db.delete(row)
        removed += 1

    return RecomputeResult(
        total=len(keep) + retained,
        newly_matched=tuple(newly_matched),
        removed=removed,
        retained_for_applications=retained,
    )


def _existing_for_job(db: Session, job_id: uuid.UUID) -> dict[tuple[uuid.UUID, uuid.UUID], MatchResult]:
    return {
        (row.job_posting_id, row.candidate_profile_id): row
        for row in db.execute(
            select(MatchResult).where(MatchResult.job_posting_id == job_id)
        ).scalars()
    }


def pool_scores_for_job(db: Session, job_posting_id: uuid.UUID) -> list[float]:
    """Every persisted `match_score` for one job — the population Tier B's
    percentile is measured against (`domains/matching/tiers.py`).

    Deliberately the *whole* persisted pool, not the subset a given recompute
    happened to touch. A candidate-triggered recompute (`recompute_for_candidate`)
    produces one new pair for this job and knows nothing about the other
    two hundred; scoring its percentile against a pool of one would make
    every single new match the top of its own distribution, which is exactly
    the notification spam Tier B exists to prevent.
    """
    return [
        float(score)
        for score in db.execute(
            select(MatchResult.match_score).where(MatchResult.job_posting_id == job_posting_id)
        ).scalars()
    ]


def recompute_for_job(db: Session, job: JobPosting) -> RecomputeResult:
    """Recomputes every `match_results` row for this job as an upsert.

    A job that isn't `PUBLISHED` (closed, still draft) keeps no matches, but
    even then rows an application depends on are retained — a candidate who
    applied before the job closed must not vanish from the recruiter's own
    board.
    """
    existing = _existing_for_job(db, job.id)
    protected = _application_linked_pairs(
        db, job_posting_ids=[job.id], candidate_profile_ids=[]
    )

    def _finish_empty() -> RecomputeResult:
        result = _reconcile(db, scored=[], existing=existing, protected=protected)
        db.commit()
        return result

    if job.status is not JobStatus.PUBLISHED:
        return _finish_empty()

    job_embedding = get_embedding(db, entity_type=EmbeddableEntityType.JOB_POSTING, entity_id=job.id)
    if job_embedding is None:
        return _finish_empty()

    candidate_ids = _prefiltered_candidate_ids(db, job)
    pool = _semantic_pool(
        db, job_vector=job_embedding.vector, candidate_ids=candidate_ids, limit=SEMANTIC_POOL_SIZE
    )
    if not pool:
        return _finish_empty()

    pool_ids = [candidate_id for candidate_id, _ in pool]
    semantic_by_id = dict(pool)
    skill_weights_by_candidate = _candidate_skill_weights(db, pool_ids)

    requirements = list(
        db.execute(select(JobRequirement).where(JobRequirement.job_posting_id == job.id)).scalars()
    )
    skill_id_to_name = dict(
        db.execute(select(Skill.id, Skill.name).where(Skill.id.in_([r.skill_id for r in requirements]))).all()
    )
    required_skill_names = {skill_id_to_name[r.skill_id] for r in requirements if r.is_required}

    candidates_by_id = {
        c.id: c
        for c in db.execute(select(CandidateProfile).where(CandidateProfile.id.in_(pool_ids))).scalars()
    }
    projects_by_candidate: dict[uuid.UUID, list[Project]] = {}
    for project in db.execute(
        select(Project).where(
            Project.candidate_profile_id.in_(pool_ids),
            Project.verification_status == VerificationStatus.VERIFIED,
        )
    ).scalars():
        projects_by_candidate.setdefault(project.candidate_profile_id, []).append(project)

    proficiency_by_candidate: dict[uuid.UUID, dict[str, str]] = {}
    for candidate_id, skill_name, proficiency in db.execute(
        select(CandidateSkill.candidate_profile_id, Skill.name, CandidateSkill.proficiency)
        .join(Skill, Skill.id == CandidateSkill.skill_id)
        .where(CandidateSkill.candidate_profile_id.in_(pool_ids))
    ).all():
        proficiency_by_candidate.setdefault(candidate_id, {})[skill_name.casefold()] = proficiency.value

    # Read once for the whole pass, not per candidate: every pair in one
    # recompute must be cut against the same number, or a mid-run config
    # reload could persist a set of rows no single threshold explains.
    threshold = get_match_threshold()

    scored: list[ScoredPair] = []
    for candidate_id in pool_ids:
        candidate = candidates_by_id.get(candidate_id)
        if candidate is None:
            continue
        skill_weights = skill_weights_by_candidate.get(candidate_id, {})
        evidence_score = compute_evidence_score(
            required_skill_names=required_skill_names, candidate_skill_weights=skill_weights
        )
        match_score = compute_match_score(
            semantic_score=semantic_by_id[candidate_id],
            evidence_score=evidence_score,
            profile_strength=candidate.profile_strength,
            interview_score=float(candidate.interview_score) if candidate.interview_score else None,
            competency_score=compute_competency_score(
                required_skill_names=required_skill_names,
                competency_weights=_competency_weights(skill_weights),
            ),
        )
        if match_score < threshold:
            continue

        required_reasons, desirable_reasons = _build_match_reasons(
            requirements=requirements,
            skill_id_to_name=skill_id_to_name,
            candidate_skill_names=skill_weights,
            candidate_proficiency=proficiency_by_candidate.get(candidate_id, {}),
            candidate_projects=projects_by_candidate.get(candidate_id, []),
        )
        scored.append(
            ScoredPair(
                job_posting_id=job.id,
                candidate_profile_id=candidate_id,
                match_score=match_score,
                semantic_score=semantic_by_id[candidate_id],
                evidence_score=evidence_score,
                profile_strength=candidate.profile_strength,
                match_reasons={"required": required_reasons, "desirable": desirable_reasons},
            )
        )

    scored.sort(key=lambda pair: pair.match_score, reverse=True)
    result = _reconcile(db, scored=scored[:TOP_K], existing=existing, protected=protected)
    db.commit()
    return result


def recompute_for_candidate(db: Session, candidate_profile: CandidateProfile) -> RecomputeResult:
    """The student-feed side of the same computation: every currently
    `PUBLISHED` job re-scored against this one candidate. Deliberately not
    "for each job, call `recompute_for_job`" — that would recompute every
    *other* candidate's row for each job too, which a single candidate's
    re-verification has no reason to touch.

    Upserts, and never prunes a pair an application depends on — this is the
    path that used to silently drop a candidate off every recruiter board the
    moment they re-verified a repository.
    """
    existing = {
        (row.job_posting_id, row.candidate_profile_id): row
        for row in db.execute(
            select(MatchResult).where(MatchResult.candidate_profile_id == candidate_profile.id)
        ).scalars()
    }
    protected = _application_linked_pairs(
        db, job_posting_ids=[], candidate_profile_ids=[candidate_profile.id]
    )

    def _finish_empty() -> RecomputeResult:
        result = _reconcile(db, scored=[], existing=existing, protected=protected)
        db.commit()
        return result

    if not candidate_profile.is_discoverable:
        return _finish_empty()

    candidate_embedding = get_embedding(
        db, entity_type=EmbeddableEntityType.CANDIDATE_PROFILE, entity_id=candidate_profile.id
    )
    if candidate_embedding is None:
        return _finish_empty()

    published_jobs = list(
        db.execute(select(JobPosting).where(JobPosting.status == JobStatus.PUBLISHED)).scalars()
    )
    if not published_jobs:
        return _finish_empty()

    skill_weights = _candidate_skill_weights(db, [candidate_profile.id]).get(candidate_profile.id, {})
    proficiency = {
        name.casefold(): prof.value
        for name, prof in db.execute(
            select(Skill.name, CandidateSkill.proficiency)
            .join(CandidateSkill, CandidateSkill.skill_id == Skill.id)
            .where(CandidateSkill.candidate_profile_id == candidate_profile.id)
        ).all()
    }
    verified_projects = list(
        db.execute(
            select(Project).where(
                Project.candidate_profile_id == candidate_profile.id,
                Project.verification_status == VerificationStatus.VERIFIED,
            )
        ).scalars()
    )

    # Same reasoning as `recompute_for_job`: one threshold for the whole pass.
    threshold = get_match_threshold()

    scored: list[ScoredPair] = []
    for job in published_jobs:
        job_embedding = get_embedding(db, entity_type=EmbeddableEntityType.JOB_POSTING, entity_id=job.id)
        if job_embedding is None:
            continue
        if job.id not in {j.id for j in _prefiltered_job_ids_for_candidate(db, candidate_profile, [job])}:
            continue

        distance = _cosine_distance(candidate_embedding.vector, job_embedding.vector)
        semantic_score = round(1.0 - distance, 5)

        requirements = list(
            db.execute(select(JobRequirement).where(JobRequirement.job_posting_id == job.id)).scalars()
        )
        skill_id_to_name = dict(
            db.execute(
                select(Skill.id, Skill.name).where(Skill.id.in_([r.skill_id for r in requirements]))
            ).all()
        )
        required_skill_names = {skill_id_to_name[r.skill_id] for r in requirements if r.is_required}
        evidence_score = compute_evidence_score(
            required_skill_names=required_skill_names, candidate_skill_weights=skill_weights
        )
        match_score = compute_match_score(
            semantic_score=semantic_score,
            evidence_score=evidence_score,
            profile_strength=candidate_profile.profile_strength,
            interview_score=(
                float(candidate_profile.interview_score) if candidate_profile.interview_score else None
            ),
            competency_score=compute_competency_score(
                required_skill_names=required_skill_names,
                competency_weights=_competency_weights(skill_weights),
            ),
        )
        if match_score < threshold:
            continue

        required_reasons, desirable_reasons = _build_match_reasons(
            requirements=requirements,
            skill_id_to_name=skill_id_to_name,
            candidate_skill_names=skill_weights,
            candidate_proficiency=proficiency,
            candidate_projects=verified_projects,
        )
        scored.append(
            ScoredPair(
                job_posting_id=job.id,
                candidate_profile_id=candidate_profile.id,
                match_score=match_score,
                semantic_score=semantic_score,
                evidence_score=evidence_score,
                profile_strength=candidate_profile.profile_strength,
                match_reasons={"required": required_reasons, "desirable": desirable_reasons},
            )
        )

    scored.sort(key=lambda pair: pair.match_score, reverse=True)
    result = _reconcile(db, scored=scored[:TOP_K], existing=existing, protected=protected)
    db.commit()
    return result


def _prefiltered_job_ids_for_candidate(
    db: Session, candidate: CandidateProfile, jobs: list[JobPosting]
) -> list[JobPosting]:
    """The same hard constraints as `_prefiltered_candidate_ids`, applied
    from the candidate's side — one job at a time here since the caller
    already holds the candidate fixed and is iterating jobs."""
    result = []
    for job in jobs:
        if _deadline_passed(job):
            continue
        window = _graduation_year_window(job.experience_level)
        if window is None:
            continue
        if candidate.graduation_year is None or not (window[0] <= candidate.graduation_year <= window[1]):
            continue
        if not job.is_remote and job.location and candidate.location:
            if job.location.casefold() not in candidate.location.casefold():
                continue
        result.append(job)
    return result


def _cosine_distance(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine distance for the candidate-side loop, where each
    job is checked one at a time against a single already-fetched candidate
    vector — not worth a round trip to Postgres per job when both vectors
    are already in memory. `recompute_for_job`'s pool search is the one
    that needs the ANN index; this does not.
    """
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 1.0
    cosine_similarity = dot / (norm_a * norm_b)
    return 1.0 - cosine_similarity


def _prune(
    db: Session,
    *,
    rows: list[MatchResult],
    protected: set[tuple[uuid.UUID, uuid.UUID]],
) -> int:
    removed = 0
    for row in rows:
        if (row.job_posting_id, row.candidate_profile_id) in protected:
            continue
        db.delete(row)
        removed += 1
    db.commit()
    return removed


def remove_matches_for_job(db: Session, job_posting_id: uuid.UUID) -> int:
    """Drops this job's matches — except pairs an application depends on.

    Closing a job removes it from every student's feed, but a candidate who
    already applied is in the recruiter's pipeline, and deleting their match
    row would strip the score and reasons off a live application.
    """
    rows = list(
        db.execute(select(MatchResult).where(MatchResult.job_posting_id == job_posting_id)).scalars()
    )
    protected = _application_linked_pairs(
        db, job_posting_ids=[job_posting_id], candidate_profile_ids=[]
    )
    return _prune(db, rows=rows, protected=protected)


def remove_matches_for_candidate(db: Session, candidate_profile_id: uuid.UUID) -> int:
    """Drops this candidate's matches — except pairs an application depends
    on. A student who becomes non-discoverable leaves the index, but does not
    thereby withdraw applications they already submitted."""
    rows = list(
        db.execute(
            select(MatchResult).where(MatchResult.candidate_profile_id == candidate_profile_id)
        ).scalars()
    )
    protected = _application_linked_pairs(
        db, job_posting_ids=[], candidate_profile_ids=[candidate_profile_id]
    )
    return _prune(db, rows=rows, protected=protected)
