"""Unit tests for setup-state derivation.

`build_setup_state` is a pure function of a completeness snapshot plus a resume
snapshot, so the whole step/percentage table is testable without a database.
The integration suite (`tests/integration/test_profile_setup.py`) then checks
that the endpoint feeds it the right snapshots.

The flow has eight steps, and two of them are not profile sections: `choose`
(the resume-or-manual fork) and `review` (the submit step). Their status comes
off the profile row rather than a `SectionScore`, which is the thing most of
the ordering tests below are really pinning down.

`github` and `coding` are separate steps, not the single `technical` step they
once were: only GitHub is mandatory, and presenting them as one step made the
optional half look required.
"""

from __future__ import annotations

import uuid

import pytest

from src.domains.resume.models import ResumeDraftStatus, ResumeUploadStatus
from src.domains.auth.models import OnboardingChoice
from src.domains.student.completeness import ProfileCompleteness, SectionScore
from src.domains.student.models import VerificationStatus
from src.domains.student.setup_state import (
    REVIEW_STEP_INDEX,
    SETUP_STEPS,
    ResumeParseState,
    ResumeSetupState,
    SetupStepStatus,
    _UPLOAD_STATUS_TO_PARSE_STATE,
    build_setup_state,
)

#: Section steps in order, i.e. `SETUP_STEPS` minus the two bookends. Derived
#: rather than written out, so a new step cannot make these tests pass by
#: agreeing with a stale copy of the list.
SECTION_KEYS = [meta.section_key for meta in SETUP_STEPS if meta.section_key is not None]

#: Index of each section step in the eight-step list. Every assertion below
#: goes through this rather than a literal, because inserting a step should
#: move the tests with it.
STEP_INDEX = {
    meta.key: index for index, meta in enumerate(SETUP_STEPS) if meta.section_key is not None
}


def _section(
    key: str,
    *,
    mandatory: bool = False,
    filled: int = 0,
    required: int = 0,
    missing: tuple[str, ...] = (),
    verification: VerificationStatus | None = None,
    points: int = 0,
) -> SectionScore:
    return SectionScore(
        key=key,
        is_mandatory=mandatory,
        points_earned=points,
        points_possible=100,
        filled_count=filled,
        required_count=required,
        missing=missing,
        verification=verification,
    )


def _completeness(
    *sections: SectionScore,
    strength: int = 0,
    meets: bool = False,
    choice: OnboardingChoice | None = None,
    submitted: bool = False,
) -> ProfileCompleteness:
    return ProfileCompleteness(
        profile_strength=strength,
        evidence_score=0,
        interview_score=None,
        meets_section_requirements=meets,
        is_indexed=False,
        is_discoverable=False,
        has_completed_interview=False,
        sections=tuple(sections),
        blocking=(),
        onboarding_choice=choice,
        is_onboarding_submitted=submitted,
    )


def _empty_profile(**overrides) -> ProfileCompleteness:
    """A profile that has answered the fork and nothing else.

    The fork is pre-answered in the default because that is the state every
    other step is reached from — a student who has not chosen a lane is on
    step 1 and none of the section assertions apply. `choice=None` is passed
    explicitly by the one test that cares.
    """
    defaults = {
        "basic": _section("basic", mandatory=True, required=7, missing=("a headline",)),
        "github": _section("github", mandatory=True, required=1, missing=("your GitHub account",)),
        "projects": _section("projects", mandatory=True, required=1, missing=("at least one project",)),
        "coding": _section("coding"),
        "certificates": _section("certificates"),
        "experience": _section("experience"),
    }
    kwargs = {k: v for k, v in overrides.items() if k not in defaults}
    defaults.update({k: v for k, v in overrides.items() if k in defaults})
    kwargs.setdefault("choice", OnboardingChoice.MANUAL_ENTRY)
    return _completeness(*(defaults[key] for key in SECTION_KEYS), **kwargs)


NO_RESUME = ResumeSetupState(has_upload=False)


# --------------------------------------------------------------------------
# Step order and labels
# --------------------------------------------------------------------------


def test_the_flow_is_eight_steps_bookended_by_choose_and_review() -> None:
    state = build_setup_state(_empty_profile(), NO_RESUME)

    assert [step.key for step in state.steps] == [
        "choose",
        "basic",
        "github",
        "projects",
        "coding",
        "certificates",
        "experience",
        "review",
    ]
    assert [step.index for step in state.steps] == [0, 1, 2, 3, 4, 5, 6, 7]
    assert REVIEW_STEP_INDEX == 7


def test_every_step_carries_copy() -> None:
    """The labels are served from the server so the eight the screen shows and
    the sections the API scores cannot drift apart."""
    state = build_setup_state(_empty_profile(), NO_RESUME)
    assert all(step.title and step.subtitle for step in state.steps)


def test_step_order_follows_setup_steps_not_the_completeness_order() -> None:
    """Sections arriving in a different order must not renumber the UI."""
    reversed_sections = _completeness(
        _section("experience"),
        _section("certificates"),
        _section("coding"),
        _section("projects", mandatory=True, required=1, missing=("z",)),
        _section("github", mandatory=True, required=1, missing=("x",)),
        _section("basic", mandatory=True, required=7, missing=("y",)),
        choice=OnboardingChoice.MANUAL_ENTRY,
    )
    state = build_setup_state(reversed_sections, NO_RESUME)
    assert [step.key for step in state.steps] == [meta.key for meta in SETUP_STEPS]


# --------------------------------------------------------------------------
# The two steps that are not sections
# --------------------------------------------------------------------------


def test_unanswered_fork_is_the_current_step() -> None:
    """A student who has not picked a lane belongs on step 1, whatever else is
    filled in — the fork is mandatory."""
    state = build_setup_state(_empty_profile(choice=None), NO_RESUME)
    assert state.current_step_index == 0
    assert state.steps[0].status is SetupStepStatus.EMPTY


def test_answering_the_fork_marks_step_one_done() -> None:
    state = build_setup_state(_empty_profile(choice=OnboardingChoice.RESUME_UPLOAD), NO_RESUME)
    assert state.steps[0].status is SetupStepStatus.SAVED
    assert state.steps[0].is_mandatory is True


def test_review_step_reflects_submission_not_completeness() -> None:
    """Filling every section does not tick the review step — pressing Submit
    does. That distinction is the whole point of the new gate."""
    complete = dict(
        basic=_section("basic", mandatory=True, filled=7, required=7),
        github=_section("github", mandatory=True, filled=1, required=1),
        projects=_section("projects", mandatory=True, filled=1, required=1),
    )
    unsubmitted = build_setup_state(_empty_profile(**complete, meets=True), NO_RESUME)
    assert unsubmitted.steps[REVIEW_STEP_INDEX].status is SetupStepStatus.EMPTY
    assert unsubmitted.is_submitted is False
    assert unsubmitted.can_submit is True

    submitted = build_setup_state(
        _empty_profile(**complete, meets=True, submitted=True), NO_RESUME
    )
    assert submitted.steps[REVIEW_STEP_INDEX].status is SetupStepStatus.SAVED
    assert submitted.is_submitted is True


def test_cannot_submit_until_the_mandatory_sections_are_complete() -> None:
    state = build_setup_state(_empty_profile(), NO_RESUME)
    assert state.can_submit is False


# --------------------------------------------------------------------------
# Status mapping — filled is not verified
# --------------------------------------------------------------------------


def test_unfilled_section_is_empty_whatever_its_verification_says() -> None:
    state = build_setup_state(
        _empty_profile(projects=_section("projects", filled=0, verification=VerificationStatus.VERIFIED)),
        NO_RESUME,
    )
    assert state.steps[STEP_INDEX["projects"]].status is SetupStepStatus.EMPTY


@pytest.mark.parametrize(
    ("verification", "expected"),
    [
        (None, SetupStepStatus.SAVED),
        (VerificationStatus.UNVERIFIED, SetupStepStatus.SAVED),
        (VerificationStatus.PENDING, SetupStepStatus.PENDING_VERIFICATION),
        (VerificationStatus.FLAGGED, SetupStepStatus.PENDING_VERIFICATION),
        (VerificationStatus.REJECTED, SetupStepStatus.PENDING_VERIFICATION),
        (VerificationStatus.VERIFIED, SetupStepStatus.VERIFIED),
    ],
)
def test_filled_section_status_maps_from_verification(
    verification: VerificationStatus | None, expected: SetupStepStatus
) -> None:
    state = build_setup_state(
        _empty_profile(projects=_section("projects", filled=1, verification=verification)),
        NO_RESUME,
    )
    assert state.steps[STEP_INDEX["projects"]].status is expected


def test_unverified_reads_as_saved_not_pending() -> None:
    """Nothing is running and nothing was contradicted, so a spinner-ish state
    would promise a check that is not happening."""
    state = build_setup_state(
        _empty_profile(
            experience=_section("experience", filled=2, verification=VerificationStatus.UNVERIFIED)
        ),
        NO_RESUME,
    )
    assert state.steps[STEP_INDEX["experience"]].status is SetupStepStatus.SAVED


# --------------------------------------------------------------------------
# current_step_index
# --------------------------------------------------------------------------


def test_empty_profile_points_at_the_first_unfinished_step() -> None:
    state = build_setup_state(_empty_profile(), NO_RESUME)
    assert state.current_step_index == STEP_INDEX["basic"]
    assert sum(step.is_current for step in state.steps) == 1


def test_partially_filled_mandatory_section_keeps_the_pill() -> None:
    """A half-filled section 1 blocks submission; an untouched section 4 does
    not. Pointing at the first *empty* step would walk the student past the one
    section they still owe fields on."""
    state = build_setup_state(
        _empty_profile(
            basic=_section("basic", mandatory=True, filled=2, required=7, missing=("your degree",))
        ),
        NO_RESUME,
    )
    assert state.current_step_index == STEP_INDEX["basic"]
    assert state.steps[STEP_INDEX["basic"]].status is SetupStepStatus.SAVED


def test_complete_basic_advances_to_github() -> None:
    state = build_setup_state(
        _empty_profile(basic=_section("basic", mandatory=True, filled=7, required=7)),
        NO_RESUME,
    )
    assert state.current_step_index == STEP_INDEX["github"]


def test_github_without_a_project_still_points_at_projects() -> None:
    """Projects is mandatory now, so a connected GitHub account does not let
    the pill skip ahead to the optional steps."""
    state = build_setup_state(
        _empty_profile(
            basic=_section("basic", mandatory=True, filled=7, required=7),
            github=_section("github", mandatory=True, filled=1, required=1),
        ),
        NO_RESUME,
    )
    assert state.current_step_index == STEP_INDEX["projects"]


def test_all_mandatory_complete_advances_to_the_first_empty_optional() -> None:
    state = build_setup_state(
        _empty_profile(
            basic=_section("basic", mandatory=True, filled=7, required=7),
            github=_section("github", mandatory=True, filled=1, required=1),
            projects=_section("projects", mandatory=True, filled=1, required=1),
        ),
        NO_RESUME,
    )
    assert state.current_step_index == STEP_INDEX["coding"]


def test_everything_filled_but_unsubmitted_rests_on_review() -> None:
    """Review is mandatory and unfinished until Submit, so a student who filled
    every section lands on the step that finishes the flow."""
    state = build_setup_state(
        _empty_profile(
            basic=_section("basic", mandatory=True, filled=7, required=7),
            github=_section("github", mandatory=True, filled=1, required=1),
            projects=_section("projects", mandatory=True, filled=3, required=1),
            coding=_section("coding", filled=1),
            certificates=_section("certificates", filled=1),
            experience=_section("experience", filled=1),
            meets=True,
        ),
        NO_RESUME,
    )
    assert state.current_step_index == REVIEW_STEP_INDEX
    assert sum(step.is_current for step in state.steps) == 1


def test_submitted_profile_still_has_exactly_one_current_step() -> None:
    """The pill never vanishes — with everything done it rests on review."""
    state = build_setup_state(
        _empty_profile(
            basic=_section("basic", mandatory=True, filled=7, required=7),
            github=_section("github", mandatory=True, filled=1, required=1),
            projects=_section("projects", mandatory=True, filled=3, required=1),
            coding=_section("coding", filled=1),
            certificates=_section("certificates", filled=1),
            experience=_section("experience", filled=1),
            meets=True,
            submitted=True,
        ),
        NO_RESUME,
    )
    assert state.current_step_index == REVIEW_STEP_INDEX
    assert sum(step.is_current for step in state.steps) == 1


# --------------------------------------------------------------------------
# Percentage
# --------------------------------------------------------------------------


def test_completion_percentage_is_profile_strength_verbatim() -> None:
    state = build_setup_state(_empty_profile(), NO_RESUME)
    assert state.completion_percentage == 0

    state = build_setup_state(
        _completeness(*(_section(key) for key in SECTION_KEYS), strength=65), NO_RESUME
    )
    assert state.completion_percentage == 65


def test_meets_section_requirements_passes_through() -> None:
    state = build_setup_state(
        _completeness(*(_section(key) for key in SECTION_KEYS), meets=True),
        NO_RESUME,
    )
    assert state.meets_section_requirements is True
    # Distinct from discoverability, which additionally needs an embedding.
    assert state.is_discoverable is False


# --------------------------------------------------------------------------
# Resume state
# --------------------------------------------------------------------------


def test_no_upload_reports_has_upload_false() -> None:
    state = build_setup_state(_empty_profile(), NO_RESUME)
    assert state.resume.has_upload is False
    assert state.resume.status is None


def test_every_upload_status_maps_to_a_parse_state() -> None:
    """A new `ResumeUploadStatus` member must not silently KeyError the endpoint."""
    assert set(_UPLOAD_STATUS_TO_PARSE_STATE) == set(ResumeUploadStatus)
    assert _UPLOAD_STATUS_TO_PARSE_STATE[ResumeUploadStatus.PROCESSING] is ResumeParseState.PARSING
    assert _UPLOAD_STATUS_TO_PARSE_STATE[ResumeUploadStatus.EXTRACTED] is ResumeParseState.PARSED


def test_resume_snapshot_is_carried_through_unchanged() -> None:
    upload_id, draft_id, job_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    resume = ResumeSetupState(
        has_upload=True,
        upload_id=upload_id,
        status=ResumeParseState.PARSED,
        async_job_id=job_id,
        draft_id=draft_id,
        draft_status=ResumeDraftStatus.PENDING_REVIEW,
        original_filename="ada.pdf",
        error=None,
    )
    state = build_setup_state(_empty_profile(), resume)

    assert state.resume.upload_id == upload_id
    assert state.resume.draft_id == draft_id
    assert state.resume.draft_status is ResumeDraftStatus.PENDING_REVIEW
    assert state.resume.original_filename == "ada.pdf"
