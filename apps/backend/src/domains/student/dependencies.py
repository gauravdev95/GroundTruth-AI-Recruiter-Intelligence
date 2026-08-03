"""FastAPI dependencies scoping every request to the caller's own profile.

The router never accepts a profile id from the client. The profile is
resolved from the authenticated user's own `user_id`, which makes
cross-candidate access structurally impossible rather than merely checked:
there is no request field a candidate could tamper with to reach another
student's data.

`verify_ownership` is still called as a defence-in-depth assertion, and
because it is the codebase's agreed place for the "403, never 404" rule
(`src/core/authorization.py`).
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from src.core.authorization import verify_ownership
from src.db.database import get_db
from src.domains.auth.dependencies import require_role
from src.domains.auth.models import CandidateProfile, User, UserRole
from src.domains.student import service

# Recruiters and unauthenticated callers are rejected here: `require_role`
# raises 403 for a wrong role and `get_current_user` raises 401 for no token.
require_candidate = require_role(UserRole.CANDIDATE)


def get_own_profile(
    user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
) -> CandidateProfile:
    profile = service.get_profile_for_user(db, user)
    verify_ownership(resource_owner_id=profile.user_id, current_user=user)
    return profile
