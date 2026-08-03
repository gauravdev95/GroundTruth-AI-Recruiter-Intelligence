"""Unit tests for profile strength and discoverability.

Pure-function tests: `compute_completeness` reads a `ProfileSnapshot` of
detached model instances, so no database is involved.
"""

from __future__ import annotations

import uuid

import pytest

from src.domains.auth.models import Branch, CandidateProfile, DegreeType, TargetRole
from src.domains.student.completeness import (
    BASIC_POINTS,
    CERTIFICATES_POINTS,
    EXPERIENCE_POINTS,
    MAX_STRENGTH,
    PROJECTS_POINTS,
    SECTION_BASIC,
    SECTION_TECHNICAL,
    TECHNICAL_POINTS,
    ProfileSnapshot,
    compute_completeness,
)
from src.domains.student.models import (
    Certificate,
    CodingPlatform,
    CodingPlatformAccount,
    Experience,
    GithubAccount,
    Project,
    ProjectKind,
    VerificationStatus,
)


def _profile(**overrides) -> CandidateProfile:
    profile = CandidateProfile(id=uuid.uuid4(), user_id=uuid.uuid4(), phone_number="+14155552671")
    for key, value in overrides.items():
        setattr(profile, key, value)
    return profile


def _complete_basic_profile() -> CandidateProfile:
    return _profile(
        headline="Final-year CS student",
        college="IIT Bombay",
        degree=DegreeType.BTECH,
        branch=Branch.CSE,
        graduation_year=2026,
        location="Mumbai, India",
        target_role=TargetRole.BACKEND,
    )


def _snapshot(profile: CandidateProfile, **kwargs) -> ProfileSnapshot:
    # `has_embedding` defaults to True here so the section-scoring tests below
    # exercise the rule they are about. Discoverability's dependency on the
    # vector is its own test (`test_discoverability_also_requires_an_embedding`)
    # rather than a precondition every unrelated case has to restate.
    return ProfileSnapshot(
        profile=profile,
        github_account=kwargs.get("github_account"),
        coding_profiles=tuple(kwargs.get("coding_profiles", ())),
        projects=tuple(kwargs.get("projects", ())),
        certificates=tuple(kwargs.get("certificates", ())),
        experiences=tuple(kwargs.get("experiences", ())),
        has_embedding=kwargs.get("has_embedding", True),
    )


def _github(status: VerificationStatus = VerificationStatus.PENDING) -> GithubAccount:
    return GithubAccount(
        id=uuid.uuid4(),
        candidate_profile_id=uuid.uuid4(),
        github_username="ada",
        profile_url="https://github.com/ada",
        verification_status=status,
    )


def _coding(
    platform: CodingPlatform = CodingPlatform.LEETCODE,
    status: VerificationStatus = VerificationStatus.PENDING,
) -> CodingPlatformAccount:
    return CodingPlatformAccount(
        id=uuid.uuid4(),
        candidate_profile_id=uuid.uuid4(),
        platform=platform,
        handle="ada",
        profile_url="https://leetcode.com/u/ada/",
        verification_status=status,
    )


def _project(status: VerificationStatus = VerificationStatus.UNVERIFIED) -> Project:
    return Project(
        id=uuid.uuid4(),
        candidate_profile_id=uuid.uuid4(),
        kind=ProjectKind.REPOSITORY,
        title="Compiler",
        repo_url=f"https://github.com/ada/{uuid.uuid4().hex}",
        technologies=["Rust"],
        position=0,
        verification_status=status,
    )


def _certificate(status: VerificationStatus = VerificationStatus.UNVERIFIED) -> Certificate:
    return Certificate(
        id=uuid.uuid4(),
        candidate_profile_id=uuid.uuid4(),
        title="AWS SAA",
        issuer="Amazon",
        position=0,
        verification_status=status,
    )


def _experience() -> Experience:
    from datetime import date

    return Experience(
        id=uuid.uuid4(),
        candidate_profile_id=uuid.uuid4(),
        company_name="Acme",
        title="Backend Intern",
        employment_type="internship",
        start_date=date(2025, 6, 1),
        technologies=["Python"],
        position=0,
    )


def _section(result, key):
    return next(section for section in result.sections if section.key == key)


def test_empty_profile_scores_zero_and_is_not_discoverable() -> None:
    result = compute_completeness(_snapshot(_profile()))

    assert result.profile_strength == 0
    assert result.is_discoverable is False
    assert _section(result, SECTION_BASIC).is_filled is False


def test_basic_section_scores_proportionally() -> None:
    profile = _profile(headline="Student", college="IIT Bombay", degree=DegreeType.BTECH)

    result = compute_completeness(_snapshot(profile))

    basic = _section(result, SECTION_BASIC)
    assert basic.filled_count == 3
    assert basic.points_earned == 15
    assert basic.is_complete is False
    assert basic.is_filled is True


def test_complete_basic_alone_does_not_make_profile_discoverable() -> None:
    result = compute_completeness(_snapshot(_complete_basic_profile()))

    assert result.profile_strength == BASIC_POINTS
    assert result.is_discoverable is False
    assert "your GitHub profile" in result.blocking


def test_technical_needs_both_github_and_a_coding_profile() -> None:
    profile = _complete_basic_profile()

    github_only = compute_completeness(_snapshot(profile, github_account=_github()))
    assert github_only.is_discoverable is False
    assert github_only.profile_strength == BASIC_POINTS + 15
    assert "at least one competitive programming profile" in github_only.blocking

    coding_only = compute_completeness(_snapshot(profile, coding_profiles=[_coding()]))
    assert coding_only.is_discoverable is False
    assert "your GitHub profile" in coding_only.blocking


def test_sections_one_and_two_complete_makes_profile_discoverable() -> None:
    result = compute_completeness(
        _snapshot(_complete_basic_profile(), github_account=_github(), coding_profiles=[_coding()])
    )

    assert result.meets_section_requirements is True
    assert result.is_discoverable is True
    assert result.blocking == ()
    assert result.profile_strength == BASIC_POINTS + TECHNICAL_POINTS


def test_discoverability_also_requires_an_embedding() -> None:
    """Sections 1-2 make a profile *eligible*; it only becomes discoverable
    once the vector exists, because the matching pre-filter cannot score a
    profile it has no embedding for. The gap between the two flags is the
    window the embedding worker runs in, and it is not something the student
    can act on — so it must not appear in `blocking`."""
    result = compute_completeness(
        _snapshot(
            _complete_basic_profile(),
            github_account=_github(),
            coding_profiles=[_coding()],
            has_embedding=False,
        )
    )

    assert result.meets_section_requirements is True
    assert result.is_discoverable is False
    assert result.blocking == ()


def test_extra_coding_profiles_do_not_add_points() -> None:
    profile = _complete_basic_profile()
    one = compute_completeness(_snapshot(profile, github_account=_github(), coding_profiles=[_coding()]))
    three = compute_completeness(
        _snapshot(
            profile,
            github_account=_github(),
            coding_profiles=[
                _coding(CodingPlatform.LEETCODE),
                _coding(CodingPlatform.CODEFORCES),
                _coding(CodingPlatform.HACKERRANK),
            ],
        )
    )

    assert one.profile_strength == three.profile_strength


def test_optional_sections_never_block_discoverability() -> None:
    result = compute_completeness(
        _snapshot(_complete_basic_profile(), github_account=_github(), coding_profiles=[_coding()])
    )

    for key in ("projects", "certificates", "experience"):
        section = _section(result, key)
        assert section.is_mandatory is False
        assert section.missing == ()
        # An empty optional section is "complete" (nothing is required) but
        # not "filled" — the UI shows an empty badge, not a blocker.
        assert section.is_complete is True
        assert section.is_filled is False


def test_optional_sections_are_capped() -> None:
    profile = _complete_basic_profile()
    result = compute_completeness(
        _snapshot(
            profile,
            github_account=_github(),
            coding_profiles=[_coding()],
            projects=[_project(), _project(), _project()],
            certificates=[_certificate(), _certificate(), _certificate(), _certificate()],
            experiences=[_experience(), _experience(), _experience()],
        )
    )

    assert _section(result, "projects").points_earned == PROJECTS_POINTS
    # Four certificates, but only two are counted.
    assert _section(result, "certificates").points_earned == CERTIFICATES_POINTS
    assert _section(result, "experience").points_earned == EXPERIENCE_POINTS
    assert result.profile_strength == MAX_STRENGTH


def test_strength_never_exceeds_one_hundred() -> None:
    result = compute_completeness(
        _snapshot(
            _complete_basic_profile(),
            github_account=_github(),
            coding_profiles=[_coding()],
            projects=[_project() for _ in range(10)],
            certificates=[_certificate() for _ in range(10)],
            experiences=[_experience() for _ in range(10)],
        )
    )

    assert result.profile_strength == 100
    assert MAX_STRENGTH == 100


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([VerificationStatus.PENDING, VerificationStatus.VERIFIED], VerificationStatus.PENDING),
        ([VerificationStatus.VERIFIED, VerificationStatus.VERIFIED], VerificationStatus.VERIFIED),
        ([VerificationStatus.REJECTED, VerificationStatus.VERIFIED], VerificationStatus.REJECTED),
        ([VerificationStatus.UNVERIFIED, VerificationStatus.VERIFIED], VerificationStatus.UNVERIFIED),
    ],
)
def test_section_verification_rollup_precedence(statuses, expected) -> None:
    result = compute_completeness(
        _snapshot(_complete_basic_profile(), projects=[_project(status) for status in statuses])
    )

    assert _section(result, "projects").verification is expected


def test_verification_status_does_not_affect_strength() -> None:
    """Filled and verified are independent — a rejection must not cost points."""
    profile = _complete_basic_profile()
    pending = compute_completeness(
        _snapshot(profile, github_account=_github(VerificationStatus.PENDING), coding_profiles=[_coding()])
    )
    rejected = compute_completeness(
        _snapshot(profile, github_account=_github(VerificationStatus.REJECTED), coding_profiles=[_coding()])
    )
    verified = compute_completeness(
        _snapshot(profile, github_account=_github(VerificationStatus.VERIFIED), coding_profiles=[_coding()])
    )

    assert pending.profile_strength == rejected.profile_strength == verified.profile_strength
    # ...and a rejected mandatory claim still counts as filled, so the
    # student stays discoverable rather than silently dropping out of search.
    assert rejected.is_discoverable is True


def test_technical_section_reports_unverified_when_nothing_linked() -> None:
    result = compute_completeness(_snapshot(_complete_basic_profile()))
    technical = _section(result, SECTION_TECHNICAL)

    assert technical.verification is None
    assert technical.is_filled is False
    assert set(technical.missing) == {"your GitHub profile", "at least one competitive programming profile"}
