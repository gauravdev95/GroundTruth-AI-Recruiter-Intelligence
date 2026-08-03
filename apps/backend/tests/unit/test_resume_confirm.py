"""Unit tests for the draft → section suggestion mapping.

Pure functions over a payload dict — no database, no LLM.
"""

from __future__ import annotations

from src.domains.ai.extraction_schema import ResumeExtraction
from src.domains.resume.confirm import suggest_sections


def _payload(**overrides) -> dict:
    base = {
        "contact": {
            "headline": "Final-year CS student",
            "location": "Mumbai, India",
            "github_username": "ada",
            "leetcode_handle": "ada_lc",
        },
        "education": [
            {
                "institution": "IIT Bombay",
                "degree": "B.Tech",
                "field_of_study": "Computer Science and Engineering",
                "graduation_year": 2026,
            }
        ],
        "skills": ["Python", "React"],
        "projects": [],
        "experience": [],
        "certificates": [],
    }
    base.update(overrides)
    return base


def test_maps_basic_information_from_education_and_contact() -> None:
    result = suggest_sections(_payload())

    assert result.basic["headline"] == "Final-year CS student"
    assert result.basic["college"] == "IIT Bombay"
    assert result.basic["degree"] == "btech"
    assert result.basic["branch"] == "cse"
    assert result.basic["graduation_year"] == 2026
    assert result.basic["location"] == "Mumbai, India"


def test_target_role_is_always_reported_as_unmapped() -> None:
    """No resume states a target role — it's forward-looking, not historical."""
    result = suggest_sections(_payload())

    assert any("Target role" in note for note in result.unmapped)
    assert "target_role" not in result.basic


def test_unrecognised_degree_is_flagged_not_guessed() -> None:
    """An unmatched controlled-vocabulary value must not silently become 'other'."""
    result = suggest_sections(
        _payload(education=[{"institution": "X", "degree": "Diploma in Widgetry"}])
    )

    assert "degree" not in result.basic
    assert any("Widgetry" in note for note in result.unmapped)


def test_maps_coding_platform_handles() -> None:
    result = suggest_sections(_payload())

    assert result.technical["github_username"] == "ada"
    assert result.technical["coding_profiles"] == [{"platform": "leetcode", "handle": "ada_lc"}]


def test_project_kind_follows_presence_of_a_repo_url() -> None:
    result = suggest_sections(
        _payload(
            projects=[
                {"title": "Compiler", "repo_url": "https://github.com/ada/c", "technologies": ["Rust"]},
                {"title": "Thesis", "description": "A described project"},
            ]
        )
    )

    assert result.projects[0]["kind"] == "repository"
    assert result.projects[1]["kind"] == "described"
    assert result.projects[1]["repo_url"] is None


def test_projects_are_capped_at_the_section_limit() -> None:
    result = suggest_sections(
        _payload(projects=[{"title": f"P{i}", "description": "x"} for i in range(6)])
    )

    assert len(result.projects) == 3


def test_experience_without_a_readable_start_date_is_flagged() -> None:
    """`start_date` is NOT NULL on the section, so it can't be suggested blank."""
    result = suggest_sections(
        _payload(experience=[{"company_name": "Acme", "title": "Intern", "start_date": "sometime"}])
    )

    assert result.experience[0]["start_date"] is None
    assert any("start date" in note for note in result.unmapped)


def test_employment_type_inferred_from_title_when_absent() -> None:
    result = suggest_sections(
        _payload(
            experience=[
                {
                    "company_name": "Acme",
                    "title": "Backend Engineering Intern",
                    "start_date": "2025-06-01",
                }
            ]
        )
    )

    assert result.experience[0]["employment_type"] == "internship"


def test_empty_extraction_produces_empty_suggestions() -> None:
    result = suggest_sections(ResumeExtraction().model_dump(mode="json"))

    assert result.basic == {}
    assert result.technical == {}
    assert result.projects == []
    assert result.experience == []
    assert result.certificates == []
