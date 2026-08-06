"""SQLAlchemy models for the matching engine.

Two tables, deliberately generic vs. deliberately specific:

`Embedding` is polymorphic (`entity_type` + `entity_id`), per
`docs/DATA_MODEL.md` §6 — the same table serves both a candidate profile's
vector and a job posting's vector, which is what makes "one embedding
service, isolated behind one module" (`domains/matching/embeddings.py`)
actually true rather than two near-duplicate tables.

`MatchResult` is the opposite: one row per `(job_posting, candidate)` pair,
because that pair *is* the unit of the computation the task asked for —
"ONE computation serving both directions". The recruiter's ranked list and
the student's job feed are both just `SELECT ... WHERE job_posting_id = ?`
/ `WHERE candidate_profile_id = ?` against this same table, ordered by the
same `match_score` column. Neither read path ever recomputes anything.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.database import Base
from src.domains.ai.embedding_constants import EMBEDDING_DIMENSIONS
from src.shared.db_mixins import TimestampMixin, UUIDPrimaryKeyMixin

# `EMBEDDING_DIMENSIONS` is fixed at compile time (not derived from runtime
# config) because the pgvector column type and its ANN index both need a
# concrete dimension — changing embedding models means a migration, not a
# config change, which is intentional: an index built for one
# dimensionality cannot silently serve vectors of another.


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def empty_match_reasons() -> dict[str, list]:
    """Default for `MatchResult.match_reasons`. A callable, not a literal —
    a shared mutable default would be aliased across every row created
    without an explicit value."""
    return {"required": [], "desirable": []}


class EmbeddableEntityType(str, enum.Enum):
    CANDIDATE_PROFILE = "candidate_profile"
    JOB_POSTING = "job_posting"


class Embedding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "model_version", name="uq_embedding_entity_model"),
    )

    entity_type: Mapped[EmbeddableEntityType] = mapped_column(
        SAEnum(EmbeddableEntityType, name="embeddable_entity_type", native_enum=True), nullable=False
    )
    # No FK: polymorphic, application-enforced — same reasoning as
    # `AuditLog.entity_id` and `evidence_records.source_id`'s design note.
    entity_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    vector: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)


class MatchResult(UUIDPrimaryKeyMixin, Base):
    """One row per `(job_posting, candidate)` pair that cleared the match
    threshold (`domains/matching/scoring.py::get_match_threshold`, env
    `MATCH_THRESHOLD`) — rows that don't clear it are simply absent, which is
    what "below-threshold results go to neither side" means as a query rather
    than a filter applied at read time. Because the threshold is configurable,
    a row's presence reflects the threshold in force at its last recompute,
    not necessarily the current one.

    Recomputed one side of the pair at a time (every candidate for a job on
    publish; every published job for a candidate on re-verification) — see
    `domains/matching/service.py::recompute_for_job` /
    `recompute_for_candidate`. Both **upsert** on `uq_match_result_pair`:
    a recompute updates the scores of pairs that still match, inserts pairs
    that newly match, and deletes only pairs that no longer match *and* have
    no application attached. An earlier implementation deleted every row for
    that side and reinserted, which silently dropped candidates off recruiter
    boards mid-hiring — including pairs a student had already applied through.

    `computed_at` is the pair's first-matched timestamp and never moves;
    `updated_at` records the most recent rescore. The two differ as soon as a
    pair survives a recompute, which is exactly when the distinction matters.
    """

    __tablename__ = "match_results"
    __table_args__ = (
        UniqueConstraint("job_posting_id", "candidate_profile_id", name="uq_match_result_pair"),
    )

    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    match_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, index=True)
    semantic_score: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)
    evidence_score: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)
    profile_strength_at_match: Mapped[int] = mapped_column(Integer, nullable=False)
    # The match-reason payload the recruiter view reads verbatim — built from
    # stored `candidate_skills`/`verification_payload` rows at compute time,
    # never narrated by an LLM after the fact (task constraint). Shape:
    # `{"required": [SkillMatchReason, ...], "desirable": [...]}`. One column
    # rather than the two it replaced: the halves are always written together
    # and always read together, so they are one value.
    match_reasons: Mapped[dict] = mapped_column(JSONB, nullable=False, default=empty_match_reasons)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    @property
    def matched_required_skills(self) -> list:
        return self.match_reasons.get("required", [])

    @property
    def matched_desirable_skills(self) -> list:
        return self.match_reasons.get("desirable", [])
