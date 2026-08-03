"""Unit tests for the pure-logic pieces of `domains/matching/service.py` —
the relational pre-filter's experience-level proxy and the pure-Python
cosine distance used on the candidate-feed side. Neither touches the
database.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domains.matching.service import _cosine_distance, _graduation_year_window
from src.domains.recruiter.models import ExperienceLevel


def test_senior_jobs_match_no_candidates_by_design():
    """No field on this student platform reports years of professional
    experience, so a SENIOR job is honestly unmatchable rather than guessed
    at — this is the documented limitation, not a bug."""
    assert _graduation_year_window(ExperienceLevel.SENIOR) is None


def test_entry_and_mid_use_the_same_recent_graduate_window():
    entry = _graduation_year_window(ExperienceLevel.ENTRY)
    mid = _graduation_year_window(ExperienceLevel.MID)
    assert entry == mid
    assert entry is not None

    current_year = datetime.now(timezone.utc).year
    low, high = entry
    assert low <= current_year <= high


def test_cosine_distance_is_zero_for_identical_vectors():
    v = [1.0, 2.0, 3.0]
    assert _cosine_distance(v, v) == pytest.approx(0.0, abs=1e-9)


def test_cosine_distance_is_one_for_orthogonal_vectors():
    assert _cosine_distance([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)


def test_cosine_distance_is_two_for_opposite_vectors():
    assert _cosine_distance([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(2.0)


def test_cosine_distance_handles_a_zero_vector_without_dividing_by_zero():
    assert _cosine_distance([0.0, 0.0], [1.0, 1.0]) == 1.0
