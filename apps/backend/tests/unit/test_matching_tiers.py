"""Tier resolution and the derived reasoning string
(`domains/matching/tiers.py`).

The percentile cases are the ones worth guarding: Tier B's whole reason for
existing is that it adapts to the pool, and every bug that has a shape here
is a bug that either spams every student on a strong job or silences the
notification entirely on a weak one.
"""

from __future__ import annotations

import pytest

from src.domains.matching.tiers import (
    TIER_A_MIN_SCORE,
    TIER_B_MIN_SCORE,
    MatchTier,
    build_reasoning,
    resolve_tier,
    tier_b_cutoff,
)


# --------------------------------------------------------------------------
# tier_b_cutoff
# --------------------------------------------------------------------------


def test_empty_pool_falls_back_to_the_absolute_floor():
    """With nothing to rank against, the relative test has no opinion."""
    assert tier_b_cutoff([]) == TIER_B_MIN_SCORE


def test_weak_pool_never_lowers_the_bar_below_the_floor():
    """The case the absolute floor exists for: a job whose entire pool is
    mediocre must not promote its best 15% into a push notification."""
    assert tier_b_cutoff([52.0, 51.0, 50.5, 50.0] * 10) == TIER_B_MIN_SCORE


def test_strong_pool_raises_the_bar_above_the_floor():
    """The case the percentile exists for: twenty candidates all above 70
    would otherwise all be notified."""
    scores = [70.0 + i for i in range(20)]  # 70..89
    # 15% of 20 = 3 slots: 89, 88, 87. The third is the cutoff.
    assert tier_b_cutoff(scores) == 87.0


def test_small_pool_still_gets_one_slot():
    """`ceil`, not `round`: 15% of 4 is 0.6, and a job with four candidates
    should still be able to recommend its best one."""
    assert tier_b_cutoff([95.0, 80.0, 75.0, 72.0]) == 95.0


def test_ties_at_the_cutoff_are_all_included():
    """"Top 15%" is a claim about people, so a candidate tying the last
    in-slot score is in — the alternative is breaking the tie arbitrarily and
    telling one of two identical candidates they are not a strong match."""
    scores = [90.0, 90.0, 90.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0]
    cutoff = tier_b_cutoff(scores)  # 15% of 10 = 2 slots -> 90.0
    assert cutoff == 90.0
    assert resolve_tier(90.0, cutoff_b=cutoff) is MatchTier.SMART_APPLY_RECOMMENDED


def test_cutoff_is_indifferent_to_input_order():
    unsorted_scores = [72.0, 95.0, 61.0, 88.0, 79.0, 55.0, 91.0]
    assert tier_b_cutoff(unsorted_scores) == tier_b_cutoff(sorted(unsorted_scores))


# --------------------------------------------------------------------------
# resolve_tier
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (49.9, None),
        (TIER_A_MIN_SCORE, MatchTier.DISCOVERABLE),
        (69.9, MatchTier.DISCOVERABLE),
        (TIER_B_MIN_SCORE, MatchTier.SMART_APPLY_RECOMMENDED),
        (100.0, MatchTier.SMART_APPLY_RECOMMENDED),
    ],
)
def test_boundaries_are_inclusive_at_the_floor(score, expected):
    assert resolve_tier(score, cutoff_b=TIER_B_MIN_SCORE) is expected


def test_a_pair_can_be_tier_a_despite_clearing_the_absolute_floor():
    """A 72 in a pool where the top 15% starts at 87 is discoverable and
    nothing more — this is the spam that the percentile prevents."""
    assert resolve_tier(72.0, cutoff_b=87.0) is MatchTier.DISCOVERABLE


# --------------------------------------------------------------------------
# build_reasoning
# --------------------------------------------------------------------------


def _skill(name: str, *, matched: bool, weight: float | None = 0.9) -> dict:
    return {
        "skill_name": name,
        "candidate_has_skill": matched,
        "candidate_proficiency": "advanced" if matched else None,
        "evidence_weight": weight if matched else None,
        "evidence_sources": [],
    }


def test_names_matched_must_haves_and_counts_them():
    reasons = {
        "required": [
            _skill("Rust", matched=True),
            _skill("PostgreSQL", matched=True),
            _skill("distributed systems", matched=True),
        ],
        "desirable": [],
    }
    assert build_reasoning(reasons) == (
        "Matches on Rust, PostgreSQL, distributed systems — 3 of 3 must-have skills verified"
    )


def test_the_denominator_is_every_must_have_not_just_the_matched_ones():
    """The count is the whole point of the sentence: "3 of 5" and "3 of 3"
    describe very different candidates and both name three skills."""
    reasons = {
        "required": [
            _skill("Rust", matched=True),
            _skill("PostgreSQL", matched=True),
            _skill("Kafka", matched=False),
            _skill("Kubernetes", matched=False),
        ],
        "desirable": [],
    }
    assert build_reasoning(reasons).endswith("2 of 4 must-have skills verified")


def test_only_three_skills_are_named_but_all_are_counted():
    reasons = {
        "required": [_skill(f"skill{i}", matched=True) for i in range(6)],
        "desirable": [],
    }
    reasoning = build_reasoning(reasons)
    assert reasoning.startswith("Matches on skill0, skill1, skill2 —")
    assert reasoning.endswith("6 of 6 must-have skills verified")


def test_zero_must_haves_matched_says_so_rather_than_advertising_desirables():
    """A card that lists only what the candidate *does* match, on someone who
    matches none of the requirements, reads as an endorsement."""
    reasons = {
        "required": [_skill("Rust", matched=False)],
        "desirable": [_skill("Docker", matched=True), _skill("Redis", matched=True)],
    }
    assert build_reasoning(reasons) == "Matches on Docker, Redis — no must-have skills verified"


def test_no_evidence_at_all_names_the_term_that_earned_the_score():
    reasons = {
        "required": [_skill("Rust", matched=False)],
        "desirable": [_skill("Docker", matched=False)],
    }
    assert build_reasoning(reasons) == "Semantic match only — no skill evidence"


def test_a_job_with_no_requirements_blames_the_job_not_the_candidate():
    """Distinct from the case above: the absence is the job's, and saying "no
    skill evidence" about a candidate nobody asked for skills from is a lie
    the recruiter has no way to spot."""
    assert build_reasoning({"required": [], "desirable": []}) == (
        "Semantic match — this job lists no required skills"
    )


@pytest.mark.parametrize("empty", [None, {}])
def test_a_missing_payload_does_not_raise(empty):
    """`match_reasons` is JSONB with a default; a row written before the
    current writer can legitimately hold neither key."""
    assert build_reasoning(empty) == "Semantic match — this job lists no required skills"


def test_malformed_entries_are_skipped_rather_than_rendered():
    reasons = {
        "required": [
            {"candidate_has_skill": True},  # no name
            _skill("Rust", matched=True),
            "not a dict at all",
        ],
        "desirable": [],
    }
    assert build_reasoning(reasons) == "Matches on Rust — 1 of 3 must-have skills verified"
