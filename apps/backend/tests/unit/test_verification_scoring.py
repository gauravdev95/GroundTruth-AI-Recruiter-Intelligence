"""Unit tests for the repository verification scoring formulas
(`domains/verification/scoring.py`) — the contribution-share, quality, and
authenticity math, and how they compose into a final verdict.
"""

from __future__ import annotations

import pytest

from src.domains.verification.scoring import (
    CONTRIBUTION_REJECT_THRESHOLD,
    FORK_LOW_CONTRIBUTION_THRESHOLD,
    VERIFIED_SCORE_THRESHOLD,
    compute_authenticity_score,
    compute_contribution_share,
    compute_quality_score,
    decide_repository_status,
    score_repository,
)


def test_contribution_share_is_candidates_commits_over_total():
    stats = [
        {"author": {"login": "ada"}, "total": 30},
        {"author": {"login": "grace"}, "total": 70},
    ]
    assert compute_contribution_share(stats, "ada") == 0.3


def test_contribution_share_is_case_insensitive_on_login():
    stats = [{"author": {"login": "Ada"}, "total": 10}]
    assert compute_contribution_share(stats, "ada") == 1.0


def test_contribution_share_is_zero_when_login_not_found():
    stats = [{"author": {"login": "grace"}, "total": 100}]
    assert compute_contribution_share(stats, "ada") == 0.0


def test_contribution_share_is_zero_when_total_commits_is_zero():
    assert compute_contribution_share([], "ada") == 0.0


def test_quality_score_rewards_all_three_signals():
    full = compute_quality_score(has_tests=True, file_count=10, weekly_commit_counts=[1, 0, 2])
    assert full == pytest.approx(1.0)

    none = compute_quality_score(has_tests=False, file_count=1, weekly_commit_counts=[0, 0])
    assert none == 0.0


def test_quality_score_cadence_needs_at_least_two_active_weeks():
    one_active_week = compute_quality_score(has_tests=False, file_count=1, weekly_commit_counts=[5, 0, 0])
    assert one_active_week == 0.0
    two_active_weeks = compute_quality_score(has_tests=False, file_count=1, weekly_commit_counts=[5, 0, 3])
    assert two_active_weeks == pytest.approx(0.3)


def test_authenticity_is_full_for_a_non_fork_regardless_of_share():
    assert compute_authenticity_score(is_fork=False, contribution_share=0.0) == 1.0


def test_authenticity_requires_meaningful_divergence_for_a_fork():
    assert compute_authenticity_score(is_fork=True, contribution_share=0.01) == 0.0
    assert compute_authenticity_score(is_fork=True, contribution_share=FORK_LOW_CONTRIBUTION_THRESHOLD) == 1.0


def test_score_repository_is_weighted_50_30_20():
    score = score_repository(contribution_share=1.0, quality_score=1.0, authenticity_score=1.0)
    assert score == 100.0
    score_half = score_repository(contribution_share=0.5, quality_score=0.0, authenticity_score=0.0)
    assert score_half == 25.0  # 0.5 * 0.5 * 100


def test_decide_status_rejects_near_zero_contribution():
    verdict = decide_repository_status(
        contribution_share=CONTRIBUTION_REJECT_THRESHOLD - 0.001, is_fork=False, score=90.0
    )
    assert verdict.status == "rejected"


def test_decide_status_flags_a_fork_with_low_divergence():
    verdict = decide_repository_status(contribution_share=0.10, is_fork=True, score=80.0)
    assert verdict.status == "flagged"


def test_decide_status_verifies_a_real_non_fork_contribution():
    verdict = decide_repository_status(contribution_share=0.9, is_fork=False, score=VERIFIED_SCORE_THRESHOLD)
    assert verdict.status == "verified"


def test_decide_status_flags_a_weak_but_nonzero_contribution():
    verdict = decide_repository_status(
        contribution_share=0.5, is_fork=False, score=VERIFIED_SCORE_THRESHOLD - 1
    )
    assert verdict.status == "flagged"
