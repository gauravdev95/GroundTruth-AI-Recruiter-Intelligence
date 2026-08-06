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
    CODING_POINTS,
    EXPERIENCE_POINTS,
    GITHUB_POINTS,
    MAX_STRENGTH,
    PROJECTS_POINTS,
    SECTION_BASIC,
    SECTION_CODING,
    SECTION_GITHUB,
    SECTION_PROJECTS,
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
    # `has_embedding` and `completed_interview_scores` both default to
    # "satisfied" here so the section-scoring tests below exercise the rule they
    # are about. Discoverability's dependency on the vector and on a completed
    # interview each get their own test rather than becoming a precondition
    # every unrelated case has to restate.
    return ProfileSnapshot(
        profile=profile,
        github_account=kwargs.get("github_account"),
        coding_profiles=tuple(kwargs.get("coding_profiles", ())),
        projects=tuple(kwargs.get("projects", ())),
        certificates=tuple(kwargs.get("certificates", ())),
        experiences=tuple(kwargs.get("experiences", ())),
        has_embedding=kwargs.get("has_embedding", True),
        completed_interview_scores=tuple(kwargs.get("completed_interview_scores", (82.0,))),
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
    assert "your GitHub account" in result.blocking


def test_a_coding_profile_is_never_required_to_finish_onboarding() -> None:
    """The regression test for the section split. A Codeforces handle is a
    supporting signal this platform refuses to treat as a verified skill, so it
    must never be able to block a submission — it used to, back when GitHub and
    coding profiles were one mandatory `technical` section."""
    result = compute_completeness(
        _snapshot(_complete_basic_profile(), github_account=_github(), projects=[_project()])
    )

    assert result.meets_section_requirements is True
    assert result.blocking == ()
    assert _section(result, SECTION_CODING).is_mandatory is False


def test_a_project_is_required_to_finish_onboarding() -> None:
    """Every downstream artefact starts from a linked repository, so a profile
    with none is one the pipeline cannot act on."""
    no_projects = compute_completeness(
        _snapshot(_complete_basic_profile(), github_account=_github())
    )

    assert no_projects.meets_section_requirements is False
    assert "at least one project" in no_projects.blocking


def test_github_alone_does_not_meet_the_requirements() -> None:
    profile = _complete_basic_profile()

    github_only = compute_completeness(_snapshot(profile, github_account=_github()))
    assert github_only.is_discoverable is False
    assert github_only.profile_strength == BASIC_POINTS + GITHUB_POINTS

    projects_only = compute_completeness(_snapshot(profile, projects=[_project()]))
    assert projects_only.is_discoverable is False
    assert "your GitHub account" in projects_only.blocking


def test_mandatory_sections_complete_makes_profile_discoverable() -> None:
    result = compute_completeness(
        _snapshot(_complete_basic_profile(), github_account=_github(), projects=[_project()])
    )

    assert result.meets_section_requirements is True
    assert result.is_discoverable is True
    assert result.blocking == ()
    # The first project is worth 10 of the 20 — see `_score_projects`.
    assert result.profile_strength == BASIC_POINTS + GITHUB_POINTS + 10


def test_discoverability_also_requires_an_embedding() -> None:
    """The mandatory sections make a profile *eligible*; it only becomes
    discoverable once the vector exists, because the matching pre-filter cannot
    score a profile it has no embedding for. The gap between the two flags is
    the window the embedding worker runs in, and it is not something the
    student can act on — so it must not appear in `blocking`."""
    result = compute_completeness(
        _snapshot(
            _complete_basic_profile(),
            github_account=_github(),
            projects=[_project()],
            has_embedding=False,
        )
    )

    assert result.meets_section_requirements is True
    assert result.is_indexed is False
    assert result.is_discoverable is False
    assert result.blocking == ()


def test_discoverability_also_requires_a_completed_interview() -> None:
    """The final gate. A profile can be complete and embedded and still not be
    discoverable — the interview is what makes the evidence examinable rather
    than merely collected.

    Like the embedding gap, this is not a `blocking` item: the interview is
    invited automatically once verification settles, so it is progress the
    system owes the student, not a field they forgot."""
    result = compute_completeness(
        _snapshot(
            _complete_basic_profile(),
            github_account=_github(),
            projects=[_project()],
            completed_interview_scores=(),
        )
    )

    assert result.meets_section_requirements is True
    assert result.is_indexed is True
    assert result.is_discoverable is False
    assert result.has_completed_interview is False
    assert result.interview_score is None
    assert result.blocking == ()


def test_interview_score_takes_the_best_attempt_not_the_mean() -> None:
    """A candidate who sat a weak interview and a strong one has demonstrated
    the stronger performance. Averaging would punish them for attempting a
    second repository, which would discourage exactly the behaviour the
    platform wants."""
    result = compute_completeness(
        _snapshot(
            _complete_basic_profile(),
            github_account=_github(),
            projects=[_project()],
            completed_interview_scores=(41.0, 88.0, 60.0),
        )
    )
    assert result.interview_score == 88.0
    assert result.is_discoverable is True


def test_no_interview_is_none_not_zero() -> None:
    """None and 0.0 are different facts: the gate reads presence, the match
    score reads value. Conflating them would make an un-interviewed candidate
    indistinguishable from one who scored zero."""
    result = compute_completeness(
        _snapshot(_complete_basic_profile(), github_account=_github(), completed_interview_scores=())
    )
    assert result.interview_score is None


def test_evidence_score_ignores_unchecked_claims_rather_than_scoring_them_zero() -> None:
    """A candidate mid-verification must not look worse than one whose claims
    were checked and rejected."""
    pending_only = compute_completeness(
        _snapshot(
            _complete_basic_profile(),
            github_account=_github(VerificationStatus.PENDING),
            coding_profiles=[_coding()],
        )
    )
    assert pending_only.evidence_score == 0


def test_evidence_score_and_strength_move_independently() -> None:
    """The whole reason they are two numbers: completeness cannot fall when a
    worker rejects a claim, but evidence must."""
    profile = _complete_basic_profile()
    verified = _github(VerificationStatus.VERIFIED)
    verified.verification_score = 90

    rejected = _github(VerificationStatus.REJECTED)
    rejected.verification_score = 2

    strong = compute_completeness(_snapshot(profile, github_account=verified, coding_profiles=[_coding()]))
    weak = compute_completeness(_snapshot(profile, github_account=rejected, coding_profiles=[_coding()]))

    assert strong.profile_strength == weak.profile_strength
    assert strong.evidence_score > weak.evidence_score
    # A rejected claim contributes no evidence at all rather than a low score —
    # otherwise a candidate could dilute one bad claim by adding more claims.
    assert weak.evidence_score == 0


def test_coding_profiles_are_capped_at_two() -> None:
    profile = _complete_basic_profile()
    two = compute_completeness(
        _snapshot(
            profile,
            github_account=_github(),
            coding_profiles=[_coding(CodingPlatform.LEETCODE), _coding(CodingPlatform.CODEFORCES)],
        )
    )
    four = compute_completeness(
        _snapshot(
            profile,
            github_account=_github(),
            coding_profiles=[
                _coding(CodingPlatform.LEETCODE),
                _coding(CodingPlatform.CODEFORCES),
                _coding(CodingPlatform.HACKERRANK),
                _coding(CodingPlatform.CODECHEF),
            ],
        )
    )

    assert two.profile_strength == four.profile_strength
    assert _section(four, SECTION_CODING).points_earned == CODING_POINTS


def test_optional_sections_never_block_discoverability() -> None:
    result = compute_completeness(
        _snapshot(_complete_basic_profile(), github_account=_github(), projects=[_project()])
    )

    for key in (SECTION_CODING, "certificates", "experience"):
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
            coding_profiles=[_coding(CodingPlatform.LEETCODE), _coding(CodingPlatform.CODEFORCES)],
            projects=[_project(), _project(), _project()],
            certificates=[_certificate(), _certificate(), _certificate(), _certificate()],
            experiences=[_experience(), _experience(), _experience()],
        )
    )

    assert _section(result, SECTION_PROJECTS).points_earned == PROJECTS_POINTS
    # Four certificates, but only two are counted.
    assert _section(result, "certificates").points_earned == CERTIFICATES_POINTS
    assert _section(result, "experience").points_earned == EXPERIENCE_POINTS
    assert result.profile_strength == MAX_STRENGTH


def test_strength_never_exceeds_one_hundred() -> None:
    result = compute_completeness(
        _snapshot(
            _complete_basic_profile(),
            github_account=_github(),
            coding_profiles=[_coding(CodingPlatform.LEETCODE), _coding(CodingPlatform.CODEFORCES)],
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
        _snapshot(profile, github_account=_github(VerificationStatus.PENDING), projects=[_project()])
    )
    rejected = compute_completeness(
        _snapshot(profile, github_account=_github(VerificationStatus.REJECTED), projects=[_project()])
    )
    verified = compute_completeness(
        _snapshot(profile, github_account=_github(VerificationStatus.VERIFIED), projects=[_project()])
    )

    assert pending.profile_strength == rejected.profile_strength == verified.profile_strength
    # ...and a rejected mandatory claim still counts as filled, so the
    # student stays discoverable rather than silently dropping out of search.
    assert rejected.is_discoverable is True


def test_github_section_reports_unverified_when_nothing_linked() -> None:
    result = compute_completeness(_snapshot(_complete_basic_profile()))
    github = _section(result, SECTION_GITHUB)

    assert github.verification is None
    assert github.is_filled is False
    assert set(github.missing) == {"your GitHub account"}


def test_second_and_third_projects_are_worth_less_than_the_first() -> None:
    """The first project is what makes the evidence pipeline able to run; the
    others only add breadth, and the point split says so."""
    profile = _complete_basic_profile()
    one = _section(
        compute_completeness(_snapshot(profile, github_account=_github(), projects=[_project()])),
        SECTION_PROJECTS,
    )
    two = _section(
        compute_completeness(
            _snapshot(profile, github_account=_github(), projects=[_project(), _project()])
        ),
        SECTION_PROJECTS,
    )

    assert one.points_earned == 10
    assert two.points_earned == 15
    # One project satisfies the requirement — the ceiling is not the bar.
    assert one.is_complete is True
    assert one.required_count == 1
