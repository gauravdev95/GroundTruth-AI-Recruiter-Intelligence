"""SQLAlchemy models for the company domain.

`Company` is the deduplicated organization a recruiter's `company_name`
free-text field eventually gets matched/linked to (see
`domains/auth/models.RecruiterProfile.company_id`).
"""

from __future__ import annotations

import enum

from sqlalchemy import Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base
from src.shared.db_mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CompanySize(str, enum.Enum):
    SIZE_1_10 = "1-10"
    SIZE_11_50 = "11-50"
    SIZE_51_200 = "51-200"
    SIZE_201_1000 = "201-1000"
    SIZE_1000_PLUS = "1000+"


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A deduplicated employer organization."""

    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size: Mapped[CompanySize | None] = mapped_column(
        SAEnum(CompanySize, name="company_size", native_enum=True), nullable=True
    )

    recruiter_profiles: Mapped[list["RecruiterProfile"]] = relationship(  # noqa: F821
        back_populates="company"
    )
