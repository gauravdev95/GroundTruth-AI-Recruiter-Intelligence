"""Unit tests for the pure-logic parts of `domains/verification/skills.py`
(category guessing, proficiency derivation). DB-backed persistence
(`get_or_create_skill`, `upsert_candidate_skill`) is covered by
`tests/integration/test_verification_tasks.py`, since it needs a real
`skills`/`candidate_skills` schema."""

from __future__ import annotations

from src.domains.skills.models import ProficiencyLevel, SkillCategory
from src.domains.verification.skills import _score_to_proficiency, guess_category


def test_guess_category_recognizes_common_languages():
    assert guess_category("Python") == SkillCategory.LANGUAGE
    assert guess_category("typescript") == SkillCategory.LANGUAGE


def test_guess_category_recognizes_frameworks():
    assert guess_category("react") == SkillCategory.FRAMEWORK
    assert guess_category("Django") == SkillCategory.FRAMEWORK


def test_guess_category_recognizes_databases():
    assert guess_category("PostgreSQL") == SkillCategory.DATABASE


def test_guess_category_defaults_to_other_for_unknown_technology():
    assert guess_category("some-obscure-internal-tool") == SkillCategory.OTHER


def test_proficiency_thresholds():
    assert _score_to_proficiency(0.0) == ProficiencyLevel.NOVICE
    assert _score_to_proficiency(0.24) == ProficiencyLevel.NOVICE
    assert _score_to_proficiency(0.25) == ProficiencyLevel.INTERMEDIATE
    assert _score_to_proficiency(0.50) == ProficiencyLevel.ADVANCED
    assert _score_to_proficiency(0.75) == ProficiencyLevel.EXPERT
    assert _score_to_proficiency(1.0) == ProficiencyLevel.EXPERT
