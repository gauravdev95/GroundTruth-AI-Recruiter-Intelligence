"""Unit tests for coding-platform competency derivation.

`_volume_weight` is a pure function of (platform, payload), so the weighting
curve is tested directly rather than through a Celery task — the shape of that
curve is a product decision and deserves assertions that name it.

The `VERIFIED`-only rule is tested at the `derive_competencies` level with a
stub account, because it is the rule most likely to be "simplified" away by a
future change and the one whose failure is least visible: it would not error,
it would just quietly start awarding skills for a URL that resolves.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest

from src.domains.student.models import CodingPlatform, VerificationStatus
from src.domains.verification.competencies import (
    COMPETENCY_NAMES,
    MAX_COMPETENCY_WEIGHT,
    MIN_COMPETENCY_WEIGHT,
    RATING_SATURATION,
    SOLVED_SATURATION,
    _volume_weight,
    derive_competencies,
)


@dataclass
class _StubAccount:
    """Only the four attributes `derive_competencies` reads."""

    verification_status: VerificationStatus
    platform: CodingPlatform = CodingPlatform.LEETCODE
    verification_payload: dict | None = None
    candidate_profile_id: uuid.UUID = uuid.uuid4()


# --- the VERIFIED-only rule -------------------------------------------------


@pytest.mark.parametrize(
    "status",
    [
        VerificationStatus.FLAGGED,
        VerificationStatus.REJECTED,
        VerificationStatus.PENDING,
        VerificationStatus.UNVERIFIED,
    ],
)
def test_only_verified_accounts_produce_competencies(status) -> None:
    """A reachability-only check lands on FLAGGED. Awarding a competency for it
    would reintroduce self-declared skills through the back door: the candidate
    typed a handle, a URL resolved, and nothing was proven about them.

    `db=None` is safe precisely because a non-VERIFIED account must return
    before touching the session — if that guard is ever removed this test fails
    with AttributeError rather than silently passing.
    """
    account = _StubAccount(verification_status=status, verification_payload={"solved_count": 900})
    assert derive_competencies(None, account=account) == []


# --- the weighting curve ----------------------------------------------------


def test_no_payload_falls_back_to_the_floor_not_zero() -> None:
    """The account verified against a real API, so it is worth more than
    nothing — but an unreadable payload must not be credited as volume."""
    assert _volume_weight(CodingPlatform.LEETCODE, None) == MIN_COMPETENCY_WEIGHT
    assert _volume_weight(CodingPlatform.LEETCODE, {}) == MIN_COMPETENCY_WEIGHT
    assert _volume_weight(CodingPlatform.LEETCODE, {"solved_count": 0}) == MIN_COMPETENCY_WEIGHT


def test_weight_never_exceeds_the_platform_ceiling() -> None:
    """Repository evidence must be able to outrank coding-profile evidence for
    the same skill; `upsert_candidate_skill` takes a max, so the only thing
    enforcing that is this ceiling."""
    huge = _volume_weight(CodingPlatform.CODEFORCES, {"solved_count": 99_999, "rating": 4000})
    assert huge == MAX_COMPETENCY_WEIGHT
    assert MAX_COMPETENCY_WEIGHT < 1.0


def test_weight_is_monotonic_in_solved_count() -> None:
    weights = [
        _volume_weight(CodingPlatform.LEETCODE, {"solved_count": n})
        for n in (10, 50, 150, 300)
    ]
    assert weights == sorted(weights)
    assert len(set(weights)) == len(weights), "each volume tier must be distinguishable"


def test_curve_is_sublinear() -> None:
    """Doubling solved count must add less than double the weight, or volume
    grinding would dominate the evidence term."""
    low = _volume_weight(CodingPlatform.LEETCODE, {"solved_count": 75})
    high = _volume_weight(CodingPlatform.LEETCODE, {"solved_count": 150})
    assert high < low * 2


def test_saturation_points_are_reachable() -> None:
    assert _volume_weight(CodingPlatform.LEETCODE, {"solved_count": SOLVED_SATURATION}) == (
        MAX_COMPETENCY_WEIGHT
    )
    assert _volume_weight(CodingPlatform.CODEFORCES, {"rating": RATING_SATURATION}) == (
        MAX_COMPETENCY_WEIGHT
    )


def test_rating_only_counts_for_codeforces() -> None:
    """`rating` means a contest rating on Codeforces; on other platforms the
    key either does not appear or does not mean the same thing, so it must not
    be read as volume."""
    payload = {"rating": RATING_SATURATION}
    assert _volume_weight(CodingPlatform.CODEFORCES, payload) == MAX_COMPETENCY_WEIGHT
    assert _volume_weight(CodingPlatform.LEETCODE, payload) == MIN_COMPETENCY_WEIGHT


def test_best_signal_wins_over_the_mean() -> None:
    """An unrated Codeforces account should be judged on solved count alone,
    not averaged against a rating it never had the chance to earn."""
    solved_only = _volume_weight(CodingPlatform.CODEFORCES, {"solved_count": SOLVED_SATURATION})
    both = _volume_weight(
        CodingPlatform.CODEFORCES, {"solved_count": SOLVED_SATURATION, "rating": 100}
    )
    assert solved_only == both == MAX_COMPETENCY_WEIGHT


def test_competency_vocabulary_is_closed_and_non_empty() -> None:
    """Platforms evidence algorithmic ability, never frameworks — the
    vocabulary must not grow into technology names."""
    assert COMPETENCY_NAMES
    assert len(set(COMPETENCY_NAMES)) == len(COMPETENCY_NAMES)
