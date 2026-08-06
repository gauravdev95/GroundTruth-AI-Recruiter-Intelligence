"""The weight sets are operator-editable, so their invariants are asserted here.

A weight set that does not sum to 1.0 does not crash — it silently puts every
score in the system on a different scale than the one it is stored, compared,
displayed and thresholded on. Nothing downstream would notice, which is exactly
why these checks belong at settings-load time and are tested directly.
"""

from __future__ import annotations

import pytest

from src.config.config import InterviewSettings, MatchingSettings
from src.domains.ai.interview_schema import RUBRIC_DIMENSIONS
from src.domains.interview.models import (
    RUBRIC_V1_TO_V2,
    RUBRIC_VERSION_V1,
    RUBRIC_WEIGHTS_V1,
    get_rubric_weights,
)
from src.domains.matching.scoring import compute_match_score


def _matching(**overrides) -> MatchingSettings:
    return MatchingSettings(_env_file=None, **overrides)


def _interview(**overrides) -> InterviewSettings:
    return InterviewSettings(_env_file=None, **overrides)


# --- defaults ---------------------------------------------------------------


def test_default_weight_sets_are_valid() -> None:
    assert sum(_matching().weights.values()) == pytest.approx(1.0)
    assert sum(_interview().rubric_weights.values()) == pytest.approx(1.0)


def test_default_threshold_is_the_agreed_sixty() -> None:
    assert _matching().match_threshold == 60.0


# --- rejection of bad operator input ----------------------------------------


def test_match_weights_that_do_not_sum_to_one_are_rejected() -> None:
    with pytest.raises(ValueError, match="must sum to 1.0"):
        _matching(match_weight_semantic=0.9)


def test_rubric_weights_that_do_not_sum_to_one_are_rejected() -> None:
    with pytest.raises(ValueError, match="must sum to 1.0"):
        _interview(interview_weight_communication=0.5)


def test_negative_weights_are_rejected() -> None:
    """Sums to exactly 1.0 but is not a distribution: a negative term would let
    a candidate improve their match score by having *less* of something. The
    sum check alone cannot catch this, which is why both checks exist."""
    weights = dict(
        match_weight_semantic=0.65,
        match_weight_skill_evidence=0.25,
        match_weight_interview=-0.05,
        match_weight_competency=0.10,
        match_weight_profile_strength=0.05,
    )
    assert sum(weights.values()) == pytest.approx(1.0), "test set-up must isolate the negativity check"
    with pytest.raises(ValueError, match="non-negative"):
        _matching(**weights)


@pytest.mark.parametrize("bad", [0.0, 100.0, -5.0, 140.0])
def test_out_of_range_thresholds_are_rejected(bad) -> None:
    with pytest.raises(ValueError, match="MATCH_THRESHOLD"):
        _matching(match_threshold=bad)


def test_error_names_the_env_vars_an_operator_would_edit() -> None:
    """The message is the only thing a deployer sees when the process refuses
    to boot, so it has to name the variables, not just the sum."""
    with pytest.raises(ValueError, match="MATCH_WEIGHT_SEMANTIC"):
        _matching(match_weight_semantic=0.9)


def test_tolerance_absorbs_float_representation_but_not_typos() -> None:
    # 0.4 + 0.25 + 0.15 + 0.1 + 0.1 is not exactly 1.0 in IEEE 754.
    _matching(
        match_weight_semantic=0.4,
        match_weight_skill_evidence=0.25,
        match_weight_interview=0.15,
        match_weight_competency=0.1,
        match_weight_profile_strength=0.1,
    )
    # A 0.05 -> 0.5 fat-finger must not slip through the same tolerance.
    with pytest.raises(ValueError):
        _matching(match_weight_competency=0.5)


# --- the rubric version boundary --------------------------------------------


def test_v1_rubric_is_preserved_verbatim() -> None:
    """Interviews scored under v1 must keep rendering v1 dimensions — an
    evidence report is written once and never edited."""
    assert get_rubric_weights(RUBRIC_VERSION_V1) == RUBRIC_WEIGHTS_V1
    assert sum(RUBRIC_WEIGHTS_V1.values()) == pytest.approx(1.0)


def test_v1_mapping_covers_every_v1_dimension_and_targets_v2() -> None:
    assert set(RUBRIC_V1_TO_V2) == set(RUBRIC_WEIGHTS_V1)
    assert set(RUBRIC_V1_TO_V2.values()) <= set(RUBRIC_DIMENSIONS)


def test_configured_dimensions_match_the_provider_output_schema() -> None:
    """The weights are configurable but the dimension *names* are baked into
    the provider's structured-output literal. If these drift, every evaluation
    is rejected at runtime by `gemini_interview.py`'s completeness check."""
    assert set(_interview().rubric_weights) == set(RUBRIC_DIMENSIONS)


# --- the five-term formula --------------------------------------------------


def test_all_five_terms_move_the_score() -> None:
    """Guards against a term being added to config but never wired into the
    formula — the score would be capped below 100 with no other symptom."""
    base = dict(semantic_score=0.0, evidence_score=0.0, profile_strength=0, interview_score=0.0, competency_score=0.0)
    assert compute_match_score(**base) == 0.0

    for field, value in (
        ("semantic_score", 1.0),
        ("evidence_score", 1.0),
        ("profile_strength", 100),
        ("interview_score", 100.0),
        ("competency_score", 1.0),
    ):
        assert compute_match_score(**{**base, field: value}) > 0.0, f"{field} does not affect the score"


def test_all_terms_at_maximum_scores_exactly_one_hundred() -> None:
    assert compute_match_score(
        semantic_score=1.0,
        evidence_score=1.0,
        profile_strength=100,
        interview_score=100.0,
        competency_score=1.0,
    ) == pytest.approx(100.0)


def test_missing_interview_contributes_zero_not_a_renormalised_score() -> None:
    """A candidate with no interview genuinely has less evidence than one with
    a bad interview. Renormalising the other weights would hide that by scoring
    them as though the term did not apply to them."""
    without = compute_match_score(semantic_score=1.0, evidence_score=1.0, profile_strength=100)
    with_zero = compute_match_score(
        semantic_score=1.0, evidence_score=1.0, profile_strength=100, interview_score=0.0
    )
    assert without == with_zero
    assert without < 100.0


def test_out_of_range_inputs_are_clamped_not_extrapolated() -> None:
    assert compute_match_score(
        semantic_score=0.0, evidence_score=0.0, profile_strength=500, interview_score=900.0, competency_score=9.0
    ) == pytest.approx(
        100 * (_matching().match_weight_profile_strength + _matching().match_weight_interview + _matching().match_weight_competency),
        abs=0.01,
    )
