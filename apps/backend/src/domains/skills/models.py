"""SQLAlchemy models for the skills domain.

`Skill` is the canonical taxonomy; `CandidateSkill` is the associative entity
linking a candidate to a skill with a derived proficiency and evidence
weight — see `docs/DATA_MODEL.md` §2 for the full design rationale.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum as SAEnum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base
from src.shared.db_mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SkillCategory(str, enum.Enum):
    LANGUAGE = "language"
    FRAMEWORK = "framework"
    DATABASE = "database"
    DEVOPS = "devops"
    CLOUD = "cloud"
    TOOL = "tool"
    SOFT_SKILL = "soft_skill"
    OTHER = "other"


class ProficiencyLevel(str, enum.Enum):
    NOVICE = "novice"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class Skill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A canonical skill in the platform-wide taxonomy."""

    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category: Mapped[SkillCategory] = mapped_column(
        SAEnum(SkillCategory, name="skill_category", native_enum=True), nullable=False
    )

    candidate_skills: Mapped[list["CandidateSkill"]] = relationship(back_populates="skill")


class CandidateSkill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A candidate's derived proficiency in a skill, with its evidence-weight rollup."""

    __tablename__ = "candidate_skills"
    __table_args__ = (UniqueConstraint("candidate_profile_id", "skill_id"),)

    candidate_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    proficiency: Mapped[ProficiencyLevel] = mapped_column(
        SAEnum(ProficiencyLevel, name="proficiency_level", native_enum=True), nullable=False
    )
    evidence_weight: Mapped[float] = mapped_column(Numeric(5, 4), default=0, nullable=False)

    candidate_profile: Mapped["CandidateProfile"] = relationship()  # noqa: F821
    skill: Mapped["Skill"] = relationship(back_populates="candidate_skills")
