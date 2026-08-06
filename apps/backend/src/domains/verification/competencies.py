"""Derives verified competencies from coding-platform accounts.

`skills.py` turns a *repository* into technology skills. This module is its
counterpart for the other evidence source: it turns a verified
`CodingPlatformAccount` into the algorithmic competencies that platform
actually evidences, so a candidate's LeetCode or Codeforces record contributes
to `candidate_skills` — and therefore to the match score's evidence term — the
same way a repository does.

Before this existed, `upsert_candidate_skill` had exactly one caller
(repository verification), so a candidate with a strong competitive-programming
record and no public repositories carried no derived skills at all.

Three rules, all load-bearing:

**1. Only `VERIFIED` accounts produce competencies.** A `FLAGGED` account —
HackerRank and CodeChef, which are checked by URL reachability alone — proves
a page resolves, not that the candidate owns it or solved anything. Minting a
"verified competency" from that would be exactly the self-declared-skill
problem this platform exists to remove, one indirection later.

**2. Competencies are a fixed, closed vocabulary.** Platforms evidence
problem-solving ability, not frameworks: no amount of Codeforces rating says
anything about React. The vocabulary is deliberately small, and every name here
is a `SkillCategory.OTHER` skill that a recruiter can require on a job posting
like any other.

**3. Weight comes from measured volume, not from the platform's own score.**
`verification_score` already encodes platform-specific scaling (Codeforces
scales rating/3500, LeetCode scales solved/500), so reusing it would make
"solved 250 LeetCode problems" and "rated 1750 on Codeforces" indistinguishable
from each other *and* from the account merely existing. `_volume_weight` reads
the raw counts back out of `verification_payload` instead.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from src.domains.skills.models import CandidateSkill, SkillCategory
from src.domains.student.models import CodingPlatform, CodingPlatformAccount, VerificationStatus
from src.domains.verification.skills import get_or_create_skill, upsert_candidate_skill

#: The closed competency vocabulary. Names are recruiter-facing and are matched
#: against `job_requirements` by name like any other skill, so they must read
#: like something a job description would actually ask for.
COMPETENCY_ALGORITHMS = "Data Structures & Algorithms"
COMPETENCY_PROBLEM_SOLVING = "Problem Solving"

COMPETENCY_NAMES: tuple[str, ...] = (COMPETENCY_ALGORITHMS, COMPETENCY_PROBLEM_SOLVING)

#: Solved-problem count at which volume weight saturates. 300 rather than a
#: rounder 500 because the curve below is already sub-linear and the top of the
#: range should be reachable by a strong student, not only by a specialist —
#: this weight feeds a hiring score, and a ceiling nobody reaches compresses
#: every real candidate into the bottom of the range.
SOLVED_SATURATION = 300

#: Codeforces rating at which volume weight saturates. 1900 is "candidate
#: master" — well above average, below the point where further rating says more
#: about contest specialisation than about employability.
RATING_SATURATION = 1900

#: Ceiling on any single platform's contribution. A coding profile is real
#: evidence but a *narrower* one than a repository: it shows algorithmic
#: ability under contest conditions, not the ability to build or maintain
#: software. Capping below 1.0 keeps it from ever outweighing repository
#: evidence for the same skill in `upsert_candidate_skill`'s max().
MAX_COMPETENCY_WEIGHT = 0.70

#: Floor for a verified account with no readable counts. The account *is*
#: verified against a real API, so it is worth more than nothing, but an
#: unparseable payload must not be rewarded as though it showed volume.
MIN_COMPETENCY_WEIGHT = 0.20


def _volume_weight(platform: CodingPlatform, payload: dict | None) -> float:
    """Map raw platform counts onto 0-`MAX_COMPETENCY_WEIGHT`.

    Sub-linear (square-root) rather than linear: the difference between 50 and
    150 solved problems is a far stronger signal about a candidate than the
    difference between 250 and 350, and a linear ramp would rank a grinder
    above a strong problem-solver purely on volume.
    """
    if not payload:
        return MIN_COMPETENCY_WEIGHT

    solved = payload.get("solved_count")
    rating = payload.get("rating") if platform is CodingPlatform.CODEFORCES else None

    ratios: list[float] = []
    if isinstance(solved, int) and solved > 0:
        ratios.append(min(1.0, solved / SOLVED_SATURATION))
    if isinstance(rating, int) and rating > 0:
        ratios.append(min(1.0, rating / RATING_SATURATION))

    if not ratios:
        return MIN_COMPETENCY_WEIGHT

    # Best available signal, not the mean: an unrated Codeforces account
    # (rating absent) should be judged on its solved count alone rather than
    # averaged against a zero it never had a chance to earn.
    ratio = max(ratios)
    weight = MAX_COMPETENCY_WEIGHT * (ratio**0.5)
    return round(max(MIN_COMPETENCY_WEIGHT, min(MAX_COMPETENCY_WEIGHT, weight)), 4)


def derive_competencies(
    db: Session, *, account: CodingPlatformAccount
) -> list[CandidateSkill]:
    """Write `account`'s competencies into `skills`/`candidate_skills`.

    Returns the affected rows, or an empty list if the account is not
    `VERIFIED` — callers can treat "no competencies" and "not verified" the
    same way, because they mean the same thing here.

    Idempotent: `upsert_candidate_skill` only ever raises a weight, so
    re-running a verification (or running two platforms for one candidate)
    converges on the strongest evidence rather than double-counting.
    """
    if account.verification_status is not VerificationStatus.VERIFIED:
        return []

    weight = _volume_weight(account.platform, account.verification_payload)

    results: list[CandidateSkill] = []
    for name in COMPETENCY_NAMES:
        skill = get_or_create_skill(db, name, category=SkillCategory.OTHER)
        results.append(
            upsert_candidate_skill(
                db,
                candidate_profile_id=account.candidate_profile_id,
                skill=skill,
                evidence_weight=weight,
            )
        )
    return results


def derive_competencies_for_account_id(
    db: Session, *, account_id: uuid.UUID
) -> list[CandidateSkill]:
    """`derive_competencies` for a caller that holds only an id.

    Exists because the verification task writes its result and derives skills
    in two separate sessions — see `jobs/tasks/verification.py`.
    """
    account = db.get(CodingPlatformAccount, account_id)
    if account is None:
        return []
    return derive_competencies(db, account=account)
