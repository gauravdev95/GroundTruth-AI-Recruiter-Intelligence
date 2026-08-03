"""The embedding service — isolated behind this one module.

Nothing outside `domains/matching/` calls `domains.ai.llm.get_embedder()`
directly; everything else goes through `embed_candidate_profile` /
`embed_job_posting` here. Both build their entity's text blob and delegate
the actual API call to the AI seam (`domains/ai/llm.py::get_embedder`),
which is what "one embedding service... isolated behind one module" means
in practice — one place decides what text represents a candidate or a job,
one place calls the provider, one place upserts the `embeddings` row.
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


def build_candidate_embedding_text(db: Session, profile: CandidateProfile) -> str:
    """Only what the platform has *filled and derived* — never raw resume
    text, never an unconfirmed draft. Mirrors the structure
    `recruiter/service.py::_build_embedding_text` uses for jobs, so both
    sides of the eventual cosine similarity are built the same way (role
    framing, then a flat skills list)."""
    lines = [
        f"Headline: {profile.headline or ''}",
        f"Target role: {profile.target_role.value if profile.target_role else ''}",
        f"Degree: {(profile.degree.value if profile.degree else '')} "
        f"{(profile.branch.value if profile.branch else '')}".strip(),
        f"Location: {profile.location or ''}",
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
