"""Unit tests for the rank-fusion formula (`domains/matching/scoring.py`)."""

from __future__ import annotations

import pytest

from src.domains.matching.scoring import (
    MATCH_THRESHOLD,
    MATCH_WEIGHTS,
    TOP_K,
    compute_evidence_score,
    compute_match_score,
)


def test_weights_sum_to_one():
    assert sum(MATCH_WEIGHTS.values()) == pytest.approx(1.0)


def test_weights_live_in_one_constant():
    """One source of truth for the formula — the three separate module
    constants this replaced made "what is the formula" a grep."""
    assert set(MATCH_WEIGHTS) == {"semantic", "evidence", "profile_strength"}


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
    assert compute_match_score(semantic_score=1.0, evidence_score=1.0, profile_strength=100) == 100.0


def test_match_score_is_zero_at_zero_signals():
    assert compute_match_score(semantic_score=0.0, evidence_score=0.0, profile_strength=0) == 0.0


def test_match_score_weights_semantic_more_than_evidence_or_strength():
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
    assert over == pytest.approx(MATCH_WEIGHTS["profile_strength"] * 100, abs=0.01)
    assert under == 0.0


def test_match_threshold_is_a_real_bar_not_zero():
    assert 0 < MATCH_THRESHOLD < 100
