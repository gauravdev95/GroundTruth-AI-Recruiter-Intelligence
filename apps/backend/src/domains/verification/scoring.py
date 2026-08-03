"""Scoring formulas for repository verification.

Every threshold here is a named constant specifically so it is citable and
tunable in one place rather than a magic number buried in the task body —
these are heuristics, documented as such, not a formula transcribed from a
specification. See the module docstring in `src/jobs/tasks/verification.py`
for how these compose into a final `VerificationStatus`.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Contribution share -----------------------------------------------------
#
# contribution_share = candidate's total commits / total commits across all
# contributors, per GitHub's `/stats/contributors` endpoint. This is commit
# *count*, not lines changed — GitHub's contributor-stats endpoint reports
# both, but commit count is far less gameable by a single large auto-formatted
# commit than a lines-changed ratio would be, at the cost of not weighting a
# genuinely large contribution any higher than a trivial one. That trade is
# accepted here: `quality_score` is what absorbs "was this a real body of
# work", not the share formula itself.


def compute_contribution_share(contributor_stats: list[dict], github_login: str) -> float:
    total = sum(int(entry.get("total", 0) or 0) for entry in contributor_stats)
    if total <= 0:
        return 0.0
    mine = next(
        (
            int(entry.get("total", 0) or 0)
            for entry in contributor_stats
            if (entry.get("author") or {}).get("login", "").casefold() == github_login.casefold()
        ),
        0,
    )
    return round(mine / total, 4)


# --- Quality signals ---------------------------------------------------------
#
# Three independent, equally-weighted signals of "this is a maintained body
# of work" rather than a single commit dumped to satisfy a resume line:
# tests present (0.4), non-trivial size (0.3), and commit cadence spread
# across more than one week (0.3) rather than a single burst.

_QUALITY_WEIGHT_TESTS = 0.4
_QUALITY_WEIGHT_SIZE = 0.3
_QUALITY_WEIGHT_CADENCE = 0.3
MIN_FILES_FOR_NONTRIVIAL_SIZE = 5
MIN_ACTIVE_WEEKS_FOR_CADENCE = 2


def compute_quality_score(*, has_tests: bool, file_count: int, weekly_commit_counts: list[int]) -> float:
    score = 0.0
    if has_tests:
        score += _QUALITY_WEIGHT_TESTS
    if file_count >= MIN_FILES_FOR_NONTRIVIAL_SIZE:
        score += _QUALITY_WEIGHT_SIZE
    active_weeks = sum(1 for count in weekly_commit_counts if count > 0)
    if active_weeks >= MIN_ACTIVE_WEEKS_FOR_CADENCE:
        score += _QUALITY_WEIGHT_CADENCE
    return round(score, 4)


# --- Authenticity -------------------------------------------------------------
#
# A non-fork is authentic by construction. A fork is only credited as the
# candidate's own evidence if their contribution share clears the same
# threshold used to decide FLAGGED-vs-not below — a fork with a handful of
# typo-fix commits is not "the candidate's project".

FORK_LOW_CONTRIBUTION_THRESHOLD = 0.20


def compute_authenticity_score(*, is_fork: bool, contribution_share: float) -> float:
    if not is_fork:
        return 1.0
    return 1.0 if contribution_share >= FORK_LOW_CONTRIBUTION_THRESHOLD else 0.0


# --- Composition ---------------------------------------------------------------
#
# Overall score = 50% contribution share + 30% quality signals +
# 20% authenticity, on a 0-100 scale. Weighted toward contribution share
# because "did the candidate actually write this" is the question a
# recruiter cares most about; quality and authenticity are secondary checks
# that catch a technically-real-but-hollow contribution.

_WEIGHT_CONTRIBUTION = 0.5
_WEIGHT_QUALITY = 0.3
_WEIGHT_AUTHENTICITY = 0.2

CONTRIBUTION_REJECT_THRESHOLD = 0.05
VERIFIED_SCORE_THRESHOLD = 40.0


def score_repository(*, contribution_share: float, quality_score: float, authenticity_score: float) -> float:
    return round(
        100
        * (
            _WEIGHT_CONTRIBUTION * contribution_share
            + _WEIGHT_QUALITY * quality_score
            + _WEIGHT_AUTHENTICITY * authenticity_score
        ),
        2,
    )


@dataclass(frozen=True)
class RepositoryVerdict:
    status: str  # one of "verified" | "rejected" | "flagged"
    reason: str


def decide_repository_status(*, contribution_share: float, is_fork: bool, score: float) -> RepositoryVerdict:
    """Composes the three signals above into a final status.

    - `REJECTED`: the candidate essentially did not contribute (near-zero
      commit share) — the claim is actively contradicted, not just weak.
    - `FLAGGED`: a fork with too little divergence to count as the
      candidate's own work, or a score below the verified threshold.
    - `VERIFIED`: everything else, i.e. a real, non-trivial, sufficiently
      credited contribution.
    """
    if contribution_share < CONTRIBUTION_REJECT_THRESHOLD:
        return RepositoryVerdict(
            status="rejected",
            reason=f"Contribution share {contribution_share:.1%} is below the "
            f"{CONTRIBUTION_REJECT_THRESHOLD:.0%} threshold — the candidate does not "
            "appear to be a meaningful contributor to this repository.",
        )
    if is_fork and contribution_share < FORK_LOW_CONTRIBUTION_THRESHOLD:
        return RepositoryVerdict(
            status="flagged",
            reason=f"This is a fork and the candidate's contribution share "
            f"({contribution_share:.1%}) is below {FORK_LOW_CONTRIBUTION_THRESHOLD:.0%} — "
            "not enough divergence from upstream to credit as original work.",
        )
    if score >= VERIFIED_SCORE_THRESHOLD:
        return RepositoryVerdict(status="verified", reason=f"Composite score {score:.1f}/100.")
    return RepositoryVerdict(
        status="flagged",
        reason=f"Composite score {score:.1f}/100 is below the {VERIFIED_SCORE_THRESHOLD:.0f} "
        "verified threshold — some signal found, but not enough to confidently verify.",
    )
