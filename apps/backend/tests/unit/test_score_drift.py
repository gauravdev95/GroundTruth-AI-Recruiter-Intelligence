"""Unit tests for `domains/pipeline/drift.py` — the one definition of
"how far has this candidate's live score moved from the score the recruiter
actually decided against".

Pure-function tests with no database: drift is deliberately a function of two
floats (see the module docstring), and the integration coverage of it landing
on the board lives in `tests/integration/test_marketplace_pipeline.py`.
"""

from __future__ import annotations

import pytest

from src.domains.matching.scoring import MEANINGFUL_DRIFT_POINTS
from src.domains.pipeline.drift import compute_drift


def test_positive_drift_is_live_minus_at_apply():
    drift = compute_drift(score_at_apply=60.0, live_score=72.5)
    assert drift.points == 12.5
    assert drift.direction == "up"
    assert drift.is_meaningful is True


def test_negative_drift_keeps_its_sign():
    """Signed, not absolute: "8 points weaker since applying" and "8 points
    stronger" are opposite situations for a recruiter and must not collapse."""
    drift = compute_drift(score_at_apply=72.5, live_score=60.0)
    assert drift.points == -12.5
    assert drift.direction == "down"
    assert drift.is_meaningful is True


def test_identical_scores_are_flat_and_not_meaningful():
    drift = compute_drift(score_at_apply=64.25, live_score=64.25)
    assert drift.points == 0.0
    assert drift.direction == "flat"
    assert drift.is_meaningful is False


def test_direction_reports_the_sign_even_below_the_threshold():
    """`direction` is the sign and `is_meaningful` is the magnitude — the two
    are separate on purpose, so a caller that wants the raw movement still
    gets it while the board only emphasises what clears the threshold."""
    drift = compute_drift(score_at_apply=60.0, live_score=61.5)
    assert drift.points == 1.5
    assert drift.direction == "up"
    assert drift.is_meaningful is False


@pytest.mark.parametrize("sign", (1, -1))
def test_threshold_is_inclusive_at_exactly_the_boundary(sign):
    """`abs(points) >= MEANINGFUL_DRIFT_POINTS`, symmetric in both
    directions — a drift exactly on the line counts."""
    drift = compute_drift(score_at_apply=60.0, live_score=60.0 + sign * MEANINGFUL_DRIFT_POINTS)
    assert drift.is_meaningful is True

    just_under = compute_drift(
        score_at_apply=60.0, live_score=60.0 + sign * (MEANINGFUL_DRIFT_POINTS - 0.01)
    )
    assert just_under.is_meaningful is False


def test_missing_live_score_is_unknown_not_zero():
    """A pruned `match_results` row means "this pair no longer scores",
    which is a different claim from "the score has not moved". Reporting 0.0
    here would tell a recruiter the candidate is unchanged."""
    drift = compute_drift(score_at_apply=68.0, live_score=None)
    assert drift.points is None
    assert drift.direction == "unknown"
    assert drift.is_meaningful is False
    assert drift.score_at_apply == 68.0


def test_missing_score_at_apply_is_unknown_not_zero():
    """The mirror case: an application backfilled by migration b2d5e8f14c73
    whose match row had already been pruned has no frozen score to compare
    against."""
    drift = compute_drift(score_at_apply=None, live_score=68.0)
    assert drift.points is None
    assert drift.direction == "unknown"
    assert drift.live_score == 68.0


def test_drift_is_rounded_to_the_stored_precision():
    """Both operands are `Numeric(5, 2)`; drift must not surface float
    subtraction noise that neither input actually carries."""
    drift = compute_drift(score_at_apply=60.10, live_score=72.30)
    assert drift.points == 12.2
