"""Write path for `companies` — zero write sites before this module.

`get_or_create_company` is the only place a `Company` row is created,
called from `domains/auth/service.py::register_recruiter` at signup. Dedup
is case-insensitive on `name` at the application layer (Postgres `UNIQUE`
stays case-sensitive on `String`), matching the same pattern
`domains/verification/skills.py::get_or_create_skill` already established
for `skills.name`.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.domains.company.models import Company


def _domain_of(email: str) -> str | None:
    if "@" not in email:
        return None
    return email.rsplit("@", 1)[-1].strip().lower() or None


def get_or_create_company(db: Session, *, name: str, recruiter_email: str) -> Company:
    normalized = name.strip()
    existing = db.execute(
        select(Company).where(func.lower(Company.name) == normalized.casefold())
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    company = Company(name=normalized, domain=_domain_of(recruiter_email))
    db.add(company)
    db.flush()
    return company
