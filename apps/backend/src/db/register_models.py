"""Imports every domain's `models` module for its side effects only.

SQLAlchemy resolves string-based `relationship()` targets (e.g.
`RecruiterProfile.company: Mapped["Company | None"]`) against whichever
classes have actually been imported into the shared `Base.registry` —
not just the domains a particular router mounts. Without this, mapper
configuration fails the first time *any* model is used, as soon as one
model's relationship references a class from an unimported module.

Import this module once, for its side effects, before the app starts
serving requests or Alembic runs — see `src/main.py` and `alembic/env.py`.
"""

from __future__ import annotations

from src.domains.auth import models as _auth_models  # noqa: F401
from src.domains.company import models as _company_models  # noqa: F401
from src.domains.skills import models as _skills_models  # noqa: F401
from src.platform import models as _platform_models  # noqa: F401
