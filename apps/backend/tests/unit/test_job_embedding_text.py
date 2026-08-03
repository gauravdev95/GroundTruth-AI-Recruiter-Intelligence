"""Unit test for `recruiter/service.py::_build_embedding_text` — the
confirmed, human-approved text the embedding service actually embeds."""

from __future__ import annotations

from types import SimpleNamespace

from src.domains.recruiter.models import ExperienceLevel, JobType
from src.domains.recruiter.service import _build_embedding_text


def _job(**overrides):
    defaults = dict(
        title="Backend Engineer",
        experience_level=ExperienceLevel.MID,
        job_type=JobType.FULL_TIME,
        is_remote=False,
        location="Bangalore",
        description="Build APIs.",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_includes_must_have_and_desirable_skills_separately():
    text = _build_embedding_text(_job(), [("Python", True), ("Django", True), ("Docker", False)])
    assert "Must-have skills: Python, Django" in text
    assert "Desirable skills: Docker" in text


def test_omits_empty_skill_sections():
    text = _build_embedding_text(_job(), [])
    assert "Must-have skills" not in text
    assert "Desirable skills" not in text


def test_remote_overrides_location_text():
    text = _build_embedding_text(_job(is_remote=True, location="Bangalore"), [])
    assert "Location: Remote" in text
    assert "Bangalore" not in text


def test_missing_location_reads_as_not_specified():
    text = _build_embedding_text(_job(location=None), [])
    assert "Location: Not specified" in text


def test_includes_title_level_and_description():
    text = _build_embedding_text(_job(), [])
    assert "Title: Backend Engineer" in text
    assert "Experience level: mid" in text
    assert "Description: Build APIs." in text
