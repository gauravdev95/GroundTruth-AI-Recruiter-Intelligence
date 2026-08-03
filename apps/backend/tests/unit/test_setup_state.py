"""Unit tests for setup-state derivation.

`build_setup_state` is a pure function of a completeness snapshot plus a resume
snapshot, so the whole step/percentage table is testable without a database.
The integration suite (`tests/integration/test_profile_setup.py`) then checks
that the endpoint feeds it the right snapshots.
"""

from __future__ import annotations

import uuid

import pytest

from src.domains.resume.models import ResumeDraftStatus, ResumeUploadStatus
from src.domains.student.completeness import ProfileCompleteness, SectionScore
from src.domains.student.models import VerificationStatus
from src.domains.student.setup_state import (
    SETUP_STEPS,
    ResumeParseState,
    ResumeSetupState,
    SetupStepStatus,
    _UPLOAD_STATUS_TO_PARSE_STATE,
    build_setup_state,
)


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


def _completeness(*sections: SectionScore, strength: int = 0, meets: bool = False) -> ProfileCompleteness:
    return ProfileCompleteness(
        profile_strength=strength,
        meets_section_requirements=meets,
        is_discoverable=False,
        sections=tuple(sections),
        blocking=(),
        onboarding_choice=None,
    )


def _empty_profile(**overrides: SectionScore) -> ProfileCompleteness:
    defaults = {
        "basic": _section("basic", mandatory=True, required=7, missing=("a headline",)),
        "technical": _section("technical", mandatory=True, required=2, missing=("your GitHub profile",)),
        "projects": _section("projects"),
        "certificates": _section("certificates"),
        "experience": _section("experience"),
    }
    defaults.update(overrides)
    return _completeness(*(defaults[meta.key] for meta in SETUP_STEPS))


NO_RESUME = ResumeSetupState(has_upload=False)


# --------------------------------------------------------------------------
# Step order and labels
# --------------------------------------------------------------------------


def test_steps_carry_the_five_labels_in_order() -> None:
    state = build_setup_state(_empty_profile(), NO_RESUME)

    assert [step.key for step in state.steps] == [
        "basic",
        "technical",
        "projects",
        "certificates",
        "experience",
    ]
    assert [step.title for step in state.steps] == [
        "Basic Information",
        "Technical Profiles",
        "Projects",
        "Certificates & Achievements",
        "Experience",
    ]
    assert [step.subtitle for step in state.steps] == [
        "Personal details & education",
        "GitHub, LeetCode & more",
        "Add & verify your projects",
        "Showcase your accomplishments",
        "Add your work experience",
    ]
    assert [step.index for step in state.steps] == [0, 1, 2, 3, 4]


def test_step_order_follows_setup_steps_not_the_completeness_order() -> None:
    """Sections arriving in a different order must not renumber the UI."""
    reversed_sections = _completeness(
        _section("experience"),
        _section("certificates"),
        _section("projects"),
        _section("technical", mandatory=True, required=2, missing=("x",)),
        _section("basic", mandatory=True, required=7, missing=("y",)),
    )
    state = build_setup_state(reversed_sections, NO_RESUME)
    assert [step.key for step in state.steps] == [meta.key for meta in SETUP_STEPS]


# --------------------------------------------------------------------------
# Status mapping — filled is not verified
# --------------------------------------------------------------------------


def test_unfilled_section_is_empty_whatever_its_verification_says() -> None:
    state = build_setup_state(
        _empty_profile(projects=_section("projects", filled=0, verification=VerificationStatus.VERIFIED)),
        NO_RESUME,
    )
    assert state.steps[2].status is SetupStepStatus.EMPTY


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
    assert state.steps[2].status is expected


def test_unverified_reads_as_saved_not_pending() -> None:
    """Nothing is running and nothing was contradicted, so a spinner-ish state
    would promise a check that is not happening."""
    state = build_setup_state(
        _empty_profile(
            experience=_section("experience", filled=2, verification=VerificationStatus.UNVERIFIED)
        ),
        NO_RESUME,
    )
    assert state.steps[4].status is SetupStepStatus.SAVED


# --------------------------------------------------------------------------
# current_step_index
# --------------------------------------------------------------------------


def test_empty_profile_points_at_the_first_step() -> None:
    state = build_setup_state(_empty_profile(), NO_RESUME)
    assert state.current_step_index == 0
    assert [step.is_current for step in state.steps] == [True, False, False, False, False]


def test_partially_filled_mandatory_section_keeps_the_pill() -> None:
    """A half-filled section 1 blocks discoverability; an untouched section 3
    does not. Pointing at the first *empty* step would walk the student past
    the one section they still owe fields on."""
    state = build_setup_state(
        _empty_profile(
            basic=_section("basic", mandatory=True, filled=2, required=7, missing=("your degree",))
        ),
        NO_RESUME,
    )
    assert state.current_step_index == 0
    assert state.steps[0].status is SetupStepStatus.SAVED


def test_complete_basic_advances_to_technical() -> None:
    state = build_setup_state(
        _empty_profile(basic=_section("basic", mandatory=True, filled=7, required=7)),
        NO_RESUME,
    )
    assert state.current_step_index == 1


def test_both_mandatory_complete_advances_to_first_empty_optional() -> None:
    state = build_setup_state(
        _empty_profile(
            basic=_section("basic", mandatory=True, filled=7, required=7),
            technical=_section("technical", mandatory=True, filled=2, required=2),
        ),
        NO_RESUME,
    )
    assert state.current_step_index == 2


def test_everything_filled_rests_on_the_last_step() -> None:
    """The screen always has exactly one active circle — the pill never vanishes."""
    state = build_setup_state(
        _completeness(
            _section("basic", mandatory=True, filled=7, required=7),
            _section("technical", mandatory=True, filled=2, required=2),
            _section("projects", filled=3),
            _section("certificates", filled=1),
            _section("experience", filled=1),
        ),
        NO_RESUME,
    )
    assert state.current_step_index == 4
    assert sum(step.is_current for step in state.steps) == 1


# --------------------------------------------------------------------------
# Percentage
# --------------------------------------------------------------------------


def test_completion_percentage_is_profile_strength_verbatim() -> None:
    state = build_setup_state(_empty_profile(), NO_RESUME)
    assert state.completion_percentage == 0

    state = build_setup_state(_completeness(*(_section(m.key) for m in SETUP_STEPS), strength=65), NO_RESUME)
    assert state.completion_percentage == 65


def test_meets_section_requirements_passes_through() -> None:
    state = build_setup_state(
        _completeness(*(_section(m.key) for m in SETUP_STEPS), meets=True),
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
