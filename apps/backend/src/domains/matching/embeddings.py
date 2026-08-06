"""The embedding service — isolated behind this one module.

Nothing outside `domains/matching/` calls `domains.ai.llm.get_embedder()`
directly; everything else goes through `embed_candidate_profile` /
`embed_job_posting` here. Both build their entity's text blob and delegate
the actual encoding to the AI seam (`domains/ai/llm.py::get_embedder`),
which is what "one embedding service... isolated behind one module" means
in practice — one place decides what text represents a candidate or a job,
one place calls the model, one place upserts the `embeddings` row.

That the model is now local rather than a hosted API changes nothing in this
module: `Embedder.embed` has the same signature, the same typed errors, and
the same fixed output width, which is the point of the seam.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.config import get_embedding_settings
from src.domains.ai.llm import get_embedder
from src.domains.auth.models import CandidateProfile
from src.domains.matching.models import Embedding, EmbeddableEntityType
from src.domains.recruiter.models import JobPosting
from src.domains.skills.models import CandidateSkill, Skill


def _target_roles(profile: CandidateProfile) -> list[str]:
    """The student's roles, newest representation first.

    `target_roles` is the source of truth; the scalar `target_role` is its
    first element and is only consulted for profiles written before the array
    column existed, which the migration backfilled but which a fixture or a
    direct insert can still produce.
    """
    if profile.target_roles:
        return list(profile.target_roles)
    return [profile.target_role.value] if profile.target_role else []


def build_candidate_embedding_text(db: Session, profile: CandidateProfile) -> str:
    """Only what the platform has *filled and derived* — never raw resume
    text, never an unconfirmed draft. Mirrors the structure
    `recruiter/service.py::_build_embedding_text` uses for jobs, so both
    sides of the eventual cosine similarity are built the same way (role
    framing, then a flat skills list)."""
    lines = [
        f"Headline: {profile.headline or ''}",
        # Every role the student selected, not just the primary one. A
        # candidate who chose backend *and* ML should surface for both kinds of
        # job, and embedding only `target_role` would silently discard the
        # second and third choices they made at onboarding. Falls back to the
        # scalar for profiles saved before the array existed.
        f"Target roles: {', '.join(_target_roles(profile))}",
        f"Degree: {(profile.degree.value if profile.degree else '')} "
        f"{(profile.branch.value if profile.branch else '')}".strip(),
        f"Location: {profile.location or ''}",
        # Self-written and unverified, so it is included for *semantic* signal
        # only — it can move the cosine similarity term but reaches no other
        # part of the match score, and contributes no evidence or completeness.
        f"About: {profile.about or ''}",
    ]

    skill_rows = db.execute(
        select(Skill.name, CandidateSkill.proficiency)
        .join(CandidateSkill, CandidateSkill.skill_id == Skill.id)
        .where(CandidateSkill.candidate_profile_id == profile.id)
    ).all()
    if skill_rows:
        lines.append(
            "Skills: " + ", ".join(f"{name} ({proficiency.value})" for name, proficiency in skill_rows)
        )

    return "\n".join(line for line in lines if line.strip())


def _upsert_embedding(
    db: Session, *, entity_type: EmbeddableEntityType, entity_id: uuid.UUID, vector: list[float]
) -> Embedding:
    model_version = get_embedding_settings().embedding_model
    existing = db.execute(
        select(Embedding).where(
            Embedding.entity_type == entity_type,
            Embedding.entity_id == entity_id,
            Embedding.model_version == model_version,
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.vector = vector
        db.flush()
        return existing

    embedding = Embedding(
        entity_type=entity_type, entity_id=entity_id, vector=vector, model_version=model_version
    )
    db.add(embedding)
    db.flush()
    return embedding


def embed_candidate_profile(db: Session, profile: CandidateProfile) -> Embedding:
    text = build_candidate_embedding_text(db, profile)
    vector = get_embedder().embed(text)
    return _upsert_embedding(
        db, entity_type=EmbeddableEntityType.CANDIDATE_PROFILE, entity_id=profile.id, vector=vector
    )


def embed_job_posting(db: Session, job: JobPosting) -> Embedding:
    text = job.embedding_text or job.description
    vector = get_embedder().embed(text)
    return _upsert_embedding(
        db, entity_type=EmbeddableEntityType.JOB_POSTING, entity_id=job.id, vector=vector
    )


def get_embedding(
    db: Session, *, entity_type: EmbeddableEntityType, entity_id: uuid.UUID
) -> Embedding | None:
    model_version = get_embedding_settings().embedding_model
    return db.execute(
        select(Embedding).where(
            Embedding.entity_type == entity_type,
            Embedding.entity_id == entity_id,
            Embedding.model_version == model_version,
        )
    ).scalar_one_or_none()
