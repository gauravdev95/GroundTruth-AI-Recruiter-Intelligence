"""Normalises detected technologies into `skills`/`candidate_skills`.

Both tables have existed since migration `48b43c88a821` with zero write
sites (`PROGRESS.md` §2.6). This module is the write site: called from
`verify_repository_task` with the `DetectedTechnology` list `manifests.py`
produced, it is the only place in the codebase that creates a `Skill` or a
`CandidateSkill` row.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.domains.skills.models import CandidateSkill, ProficiencyLevel, Skill, SkillCategory
from src.domains.verification.manifests import DetectedTechnology

# Coarse keyword -> category map. Deliberately small and conservative: an
# unrecognized technology defaults to OTHER rather than guessing wrong, since
# `SkillCategory` drives recruiter-facing filtering (DATA_MODEL.md §2).
_CATEGORY_KEYWORDS: tuple[tuple[SkillCategory, tuple[str, ...]], ...] = (
    (
        SkillCategory.LANGUAGE,
        (
            "python", "javascript", "typescript", "java", "go", "rust", "ruby", "php",
            "kotlin", "c++", "c#", "swift", "scala", "elixir",
        ),
    ),
    (
        SkillCategory.FRAMEWORK,
        (
            "react", "vue", "angular", "django", "flask", "fastapi", "express", "spring",
            "next", "nuxt", "rails", "laravel", "svelte", ".net",
        ),
    ),
    (
        SkillCategory.DATABASE,
        ("postgres", "postgresql", "mysql", "mongodb", "redis", "sqlite", "cassandra", "dynamodb"),
    ),
    (SkillCategory.DEVOPS, ("docker", "kubernetes", "terraform", "ansible", "jenkins", "github-actions")),
    (SkillCategory.CLOUD, ("aws", "gcp", "azure", "boto3", "google-cloud")),
)


def guess_category(technology_name: str) -> SkillCategory:
    """Matches on word boundaries, not raw substring containment — "go" as
    plain `in` would also match inside "django", "mongo", "algorithm". A
    keyword containing non-word characters (".net", "c++", "c#") falls back
    to substring containment since `\\b` doesn't apply around punctuation."""
    normalized = technology_name.casefold()
    for category, keywords in _CATEGORY_KEYWORDS:
        for keyword in keywords:
            if re.search(r"[^\w]", keyword):
                if keyword in normalized:
                    return category
            elif re.search(rf"\b{re.escape(keyword)}\b", normalized):
                return category
    return SkillCategory.OTHER


def _score_to_proficiency(evidence_weight: float) -> ProficiencyLevel:
    """`evidence_weight` (0-1) -> the controlled-vocabulary proficiency the
    schema requires. Thresholds chosen so a single verified-but-modest
    repository lands at NOVICE/INTERMEDIATE rather than EXPERT — proficiency
    is meant to accumulate across evidence, and one data point should not
    max it out."""
    if evidence_weight >= 0.75:
        return ProficiencyLevel.EXPERT
    if evidence_weight >= 0.50:
        return ProficiencyLevel.ADVANCED
    if evidence_weight >= 0.25:
        return ProficiencyLevel.INTERMEDIATE
    return ProficiencyLevel.NOVICE


def get_or_create_skill(db: Session, name: str, *, category: SkillCategory | None = None) -> Skill:
    normalized = name.strip()
    existing = db.execute(
        select(Skill).where(func.lower(Skill.name) == normalized.casefold())
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    skill = Skill(name=normalized, category=category or guess_category(normalized))
    db.add(skill)
    db.flush()
    return skill


def upsert_candidate_skill(
    db: Session, *, candidate_profile_id: uuid.UUID, skill: Skill, evidence_weight: float
) -> CandidateSkill:
    """Creates or strengthens a candidate's link to `skill`.

    `evidence_weight` only ever increases: a second, independent piece of
    evidence for a skill the candidate already has should not lower their
    standing because it happened to score slightly weaker than the first.
    """
    existing = db.execute(
        select(CandidateSkill).where(
            CandidateSkill.candidate_profile_id == candidate_profile_id,
            CandidateSkill.skill_id == skill.id,
        )
    ).scalar_one_or_none()

    clamped = max(0.0, min(1.0, evidence_weight))

    if existing is not None:
        if clamped > float(existing.evidence_weight):
            existing.evidence_weight = clamped
            existing.proficiency = _score_to_proficiency(clamped)
        return existing

    candidate_skill = CandidateSkill(
        candidate_profile_id=candidate_profile_id,
        skill_id=skill.id,
        proficiency=_score_to_proficiency(clamped),
        evidence_weight=clamped,
    )
    db.add(candidate_skill)
    db.flush()
    return candidate_skill


def apply_detected_technologies(
    db: Session,
    *,
    candidate_profile_id: uuid.UUID,
    technologies: list[DetectedTechnology],
    evidence_weight: float,
) -> list[CandidateSkill]:
    """Writes every detected technology into `skills`/`candidate_skills`.

    `evidence_weight` is shared across every technology in this call — the
    repository's own verification score (0-1), since manifest-level
    detection has no way to weight one dependency in a `package.json` more
    confidently than another. A skill backed by multiple repositories will
    still end up weighted by its *strongest* piece of evidence, per
    `upsert_candidate_skill`.
    """
    results: list[CandidateSkill] = []
    for tech in technologies:
        skill = get_or_create_skill(db, tech.name)
        results.append(
            upsert_candidate_skill(
                db, candidate_profile_id=candidate_profile_id, skill=skill, evidence_weight=evidence_weight
            )
        )
    return results
