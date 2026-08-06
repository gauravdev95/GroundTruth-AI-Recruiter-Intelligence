"""Unit tests for the rank-fusion formula (`domains/matching/scoring.py`)."""

from __future__ import annotations

import pytest

from src.domains.matching.scoring import (
    TOP_K,
    compute_evidence_score,
    compute_match_score,
    get_match_threshold,
    get_match_weights,
)


def test_weights_sum_to_one():
    assert sum(get_match_weights().values()) == pytest.approx(1.0)


def test_weights_live_in_one_place():
    """One source of truth for the formula. Now `MatchingSettings.weights`
    rather than a module constant, so the weights are operator-configurable —
    see `test_configurable_weights.py` for the invariants that protects."""
    assert set(get_match_weights()) == {
        "semantic",
        "skill_evidence",
        "interview",
        "competency",
        "profile_strength",
    }


def test_top_k_is_a_single_write_side_cap():
    """One cap for both directions: the two are the same computation, so a
    job has no reason to persist a different number of pairs than a candidate
    does. It bounds the write so a recompute can never produce one row per
    student in the system."""
    assert TOP_K == 200


def test_evidence_score_averages_over_every_required_skill_not_just_matched_ones():
    # 3 required skills, candidate has evidence for only 1 of them at weight 0.9.
    score = compute_evidence_score(
        required_skill_names={"Python", "React", "PostgreSQL"},
        candidate_skill_weights={"python": 0.9},
    )
    assert score == pytest.approx(0.9 / 3, abs=1e-4)


def test_evidence_score_is_zero_with_no_required_skills():
    assert compute_evidence_score(required_skill_names=set(), candidate_skill_weights={"python": 1.0}) == 0.0


def test_evidence_score_matching_is_case_insensitive():
    score = compute_evidence_score(
        required_skill_names={"Python"}, candidate_skill_weights={"python": 0.5}
    )
    assert score == 0.5


def test_match_score_is_100_at_perfect_signals():
    assert (
        compute_match_score(
            semantic_score=1.0,
            evidence_score=1.0,
            profile_strength=100,
            interview_score=100.0,
            competency_score=1.0,
        )
        == 100.0
    )


def test_match_score_is_zero_at_zero_signals():
    assert compute_match_score(semantic_score=0.0, evidence_score=0.0, profile_strength=0) == 0.0


def test_match_score_weights_semantic_above_every_other_term():
    """Role fit is the largest single term; the evidence terms establish that
    the fit is real rather than outranking it."""
    weights = get_match_weights()
    assert weights["semantic"] == max(weights.values())
    assert weights["semantic"] > weights["skill_evidence"] > weights["interview"]

    semantic_only = compute_match_score(semantic_score=1.0, evidence_score=0.0, profile_strength=0)
    evidence_only = compute_match_score(semantic_score=0.0, evidence_score=1.0, profile_strength=0)
    strength_only = compute_match_score(semantic_score=0.0, evidence_score=0.0, profile_strength=100)
    assert semantic_only > evidence_only > strength_only


def test_match_score_clamps_out_of_range_profile_strength():
    # Defensive: profile_strength is stored 0-100 by completeness.py, but the
    # formula should not silently produce a >100 or negative contribution if
    # that invariant is ever violated upstream.
    over = compute_match_score(semantic_score=0.0, evidence_score=0.0, profile_strength=150)
    under = compute_match_score(semantic_score=0.0, evidence_score=0.0, profile_strength=-20)
    assert over == pytest.approx(get_match_weights()["profile_strength"] * 100, abs=0.01)
    assert under == 0.0


def test_match_threshold_is_a_real_bar_not_zero():
    """A deployment setting MATCH_THRESHOLD to 0 or 100 would make the cut
    meaningless in one direction or the other. `MatchingSettings` rejects both
    at load time; this asserts the configured value in force here."""
    assert 0 < get_match_threshold() < 100
