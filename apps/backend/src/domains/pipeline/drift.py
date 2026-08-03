"""Score drift: the frozen `applications.score_at_apply` against the live
`match_results.match_score` for the same pair.

The two numbers exist for different reasons and neither replaces the other.
`score_at_apply` is what the recruiter's shortlisting decision was actually
made against and never moves (`pipeline/models.py::Application`). The live
score moves every time either side is re-embedded and re-scored
(`matching/service.py::_reconcile`). A recruiter looking at a board a week
into a hiring round needs to know when those two have come apart, and in
which direction — a candidate who has since verified a repository and gained
8 points is a different situation from one whose score fell 8 points because
they let their profile go stale.

Kept as a pure function over two floats — no `Session`, no ORM — so the
board query, the application-detail endpoint and the tests all compute drift
exactly one way, and the rule can be unit-tested without a database.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.domains.matching.scoring import MEANINGFUL_DRIFT_POINTS

DriftDirection = Literal["up", "down", "flat", "unknown"]


@dataclass(frozen=True)
class ScoreDrift:
    """`points` is signed: live minus at-apply, so a positive number always
    reads as "this candidate got stronger since they applied".

    `direction` is `"unknown"` exactly when one of the two scores is missing,
    which is a real state, not an error:

    * `score_at_apply is None` — the application predates the column
      (backfilled applications whose match row had already been pruned and
      whose snapshot carried no score; see migration `b2d5e8f14c73`).
    * `live_score is None` — the `match_results` row is gone. Closing a job
      prunes matches, and `remove_matches_for_job` only protects pairs an
      application depends on *at that moment*; a pair can also be dropped by
      a recompute that no longer clears the threshold, and the FK is
      `ondelete="SET NULL"` precisely so this never takes the application
      with it.

    Reporting drift as 0.0 in either case would be a lie — "these scores
    agree" is a much stronger claim than "one of these scores does not
    exist".
    """

    score_at_apply: float | None
    live_score: float | None
    points: float | None
    direction: DriftDirection
    is_meaningful: bool


def compute_drift(*, score_at_apply: float | None, live_score: float | None) -> ScoreDrift:
    """The single definition of drift for this codebase.

    `direction` and `is_meaningful` answer two separate questions on purpose:
    direction is the *sign* of the movement (`"flat"` only when the two
    scores are genuinely identical), and `is_meaningful` is the *magnitude*
    test, `abs(points) >= MEANINGFUL_DRIFT_POINTS` — see that constant for
    why the threshold is 5.0 points. Collapsing them (reporting sub-threshold
    drift as `"flat"`) would throw away the real number for any caller that
    isn't the board, so the board applies the emphasis rule itself.
    """
    if score_at_apply is None or live_score is None:
        return ScoreDrift(
            score_at_apply=score_at_apply,
            live_score=live_score,
            points=None,
            direction="unknown",
            is_meaningful=False,
        )

    # Rounded to the stored precision of both operands (`Numeric(5, 2)`), so
    # drift can never surface float-representation noise that neither input
    # actually carries.
    points = round(live_score - score_at_apply, 2)
    is_meaningful = abs(points) >= MEANINGFUL_DRIFT_POINTS

    if points > 0:
        direction: DriftDirection = "up"
    elif points < 0:
        direction = "down"
    else:
        direction = "flat"

    return ScoreDrift(
        score_at_apply=score_at_apply,
        live_score=live_score,
        points=points,
        direction=direction,
        is_meaningful=is_meaningful,
    )
