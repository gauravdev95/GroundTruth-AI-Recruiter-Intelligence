"""The one payload the profile setup entry screen renders.

`GET /api/v1/student/profile/setup-state` exists so that screen — the stepper,
the percentage pill, the resume card's resume-in-flight state — is one request
rather than three. Every field here is **derived**: from `completeness.py` for
anything about sections, and from the `resume_uploads` / `resume_extraction_drafts`
rows for anything about the resume. Nothing new is persisted, and nothing is
read from the request.

Two deliberate separations carried over from `completeness.py`:

* **Filled is not verified.** A step's status distinguishes `saved` (the student
  entered something) from `verified` (a worker confirmed it) and
  `pending_verification` (a check is running, or ran and did not confirm). The
  screen must never imply an unchecked claim is proven.
* **`current_step_index` is a hint, not a gate.** It decides which circle is
  filled violet and where the "Current Step" pill sits. Every step stays
  reachable — the builder is explicitly a multi-sitting flow, so refusing to
  open step 4 because step 2 is blank would only stop a student entering what
  they have to hand.

`ResumeUploadStatus` is renamed on the way out (`processing` -> `parsing`,
`extracted` -> `parsed`). The stored enum is the file's operational state and is
shared with the worker; the wire names are the ones the setup screen's state
machine is written in. Renaming the column instead would be a migration plus a
worker change for a vocabulary difference.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domains.auth.models import CandidateProfile
from src.domains.resume.models import (
    ResumeDraftStatus,
    ResumeExtractionDraft,
    ResumeUpload,
    ResumeUploadStatus,
)
from src.domains.student.completeness import (
    SECTION_BASIC,
    SECTION_CERTIFICATES,
    SECTION_CODING,
    SECTION_EXPERIENCE,
    SECTION_GITHUB,
    SECTION_PROJECTS,
    ProfileCompleteness,
    SectionScore,
)
from src.domains.student.models import VerificationStatus


class SetupStepStatus(str, enum.Enum):
    """What the stepper circle shows.

    `saved` and `verified` are separate values rather than one "done" so the UI
    cannot collapse them by accident — a checked circle means the section has
    content, and only `verified` licenses the verified badge.
    """

    EMPTY = "empty"
    SAVED = "saved"
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"


class ResumeParseState(str, enum.Enum):
    """The resume half of the setup flow, in the screen's own vocabulary."""

    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"


_UPLOAD_STATUS_TO_PARSE_STATE = {
    ResumeUploadStatus.UPLOADED: ResumeParseState.UPLOADED,
    ResumeUploadStatus.PROCESSING: ResumeParseState.PARSING,
    ResumeUploadStatus.EXTRACTED: ResumeParseState.PARSED,
    ResumeUploadStatus.FAILED: ResumeParseState.FAILED,
}


#: The two steps that are not profile sections. Both are real steps a student
#: walks through, so they are numbered and rendered like the rest, but neither
#: has a `SectionScore` behind it — their status comes from the profile row.
STEP_CHOOSE = "choose"
STEP_REVIEW = "review"


@dataclass(frozen=True)
class StepMeta:
    key: str
    title: str
    subtitle: str
    #: The `completeness.py` section this step saves, or None for the two
    #: bookend steps. Keeping the mapping explicit (rather than assuming
    #: `key == section key`) is what lets the flow have steps that are not
    #: sections without a parallel list to keep in sync.
    section_key: str | None


# Copy is served from here rather than hardcoded in the component so the labels
# the screen shows and the sections the API scores can never drift apart. Order
# is the step order and is load-bearing — `index` is positional, and it is what
# the client renders as "Step X of 8".
#
# GitHub and coding profiles are two steps, not the one `technical` step they
# used to be. They are asked at different points and carry different weight:
# GitHub is mandatory and starts the evidence pipeline, while a coding-platform
# handle is a supporting signal the student may skip. Presenting them as one
# step made the optional half look required, which is exactly the claim this
# codebase refuses to make about a Codeforces rating.
#
# Projects sits between them, immediately after GitHub, because linking the
# first repository is what starts the background pipeline — the optional steps
# that follow are the student's remaining form-filling time, which the analysis
# now runs underneath.
SETUP_STEPS: tuple[StepMeta, ...] = (
    StepMeta(STEP_CHOOSE, "Get Started", "Upload a resume or fill it in yourself", None),
    StepMeta(SECTION_BASIC, "Basic Information", "Personal details & education", SECTION_BASIC),
    StepMeta(SECTION_GITHUB, "Connect GitHub", "Read-only access to your public repositories", SECTION_GITHUB),
    StepMeta(SECTION_PROJECTS, "Link Projects", "Choose up to three repositories", SECTION_PROJECTS),
    StepMeta(SECTION_CODING, "Coding Profile", "Optional — a supporting signal", SECTION_CODING),
    StepMeta(SECTION_CERTIFICATES, "Certificates", "Optional — issuer-verified credentials", SECTION_CERTIFICATES),
    StepMeta(SECTION_EXPERIENCE, "Experience", "Optional — internships & jobs", SECTION_EXPERIENCE),
    StepMeta(STEP_REVIEW, "Review & Submit", "Check everything, then submit", None),
)

#: Index of the final step. Named so the client's "last step" special-casing
#: and the server's `current_step_index` clamp agree by construction.
REVIEW_STEP_INDEX = len(SETUP_STEPS) - 1


@dataclass(frozen=True)
class SetupStep:
    key: str
    index: int
    title: str
    subtitle: str
    status: SetupStepStatus
    is_mandatory: bool
    is_current: bool
    filled_count: int
    required_count: int


@dataclass(frozen=True)
class ResumeSetupState:
    """The most recent resume attempt, or `has_upload=False` if there is none."""

    has_upload: bool
    upload_id: uuid.UUID | None = None
    status: ResumeParseState | None = None
    async_job_id: uuid.UUID | None = None
    draft_id: uuid.UUID | None = None
    # `pending_review` here plus `status == parsed` is what sends a returning
    # student to the review screen rather than back to the drop zone.
    draft_status: ResumeDraftStatus | None = None
    original_filename: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class SetupState:
    completion_percentage: int
    current_step_index: int
    meets_section_requirements: bool
    is_discoverable: bool
    blocking: tuple[str, ...]
    steps: tuple[SetupStep, ...]
    resume: ResumeSetupState
    # Onboarding is finished — the student pressed Submit on the review step.
    # The only thing that opens the dashboard.
    is_submitted: bool
    # Whether pressing Submit would succeed right now. Separate from
    # `is_submitted` because the review step needs to render the difference
    # between "you can finish" and "you already did", and separate from
    # `meets_section_requirements` in *name* because that phrase is about
    # scoring while this one is about a button.
    can_submit: bool


def _step_status(section: SectionScore) -> SetupStepStatus:
    """Map one scored section onto the circle the stepper draws.

    `UNVERIFIED` deliberately reads as `saved`, not `pending_verification`:
    nothing is running and nothing was contradicted, so showing a spinner-ish
    state would promise a check that is not happening. Section 1 has no
    verification concept at all and can only ever be `empty` or `saved`.
    """
    if not section.is_filled:
        return SetupStepStatus.EMPTY

    match section.verification:
        case VerificationStatus.VERIFIED:
            return SetupStepStatus.VERIFIED
        case VerificationStatus.PENDING | VerificationStatus.FLAGGED | VerificationStatus.REJECTED:
            return SetupStepStatus.PENDING_VERIFICATION
        case _:
            return SetupStepStatus.SAVED


@dataclass(frozen=True)
class _StepState:
    """One step's derived state, before it is paired with its copy."""

    status: SetupStepStatus
    is_mandatory: bool
    is_complete: bool
    filled_count: int
    required_count: int


def _section_step_state(section: SectionScore) -> _StepState:
    return _StepState(
        status=_step_status(section),
        is_mandatory=section.is_mandatory,
        is_complete=section.is_complete,
        filled_count=section.filled_count,
        required_count=section.required_count,
    )


def _flag_step_state(*, done: bool) -> _StepState:
    """The two steps with no section behind them.

    Both are mandatory — a student cannot skip the fork or the submit — and
    both are binary, so `filled_count`/`required_count` are 0/1 or 1/1 rather
    than a count of fields. `SAVED`, never `VERIFIED`: neither answering the
    fork nor pressing Submit is a verification of anything.
    """
    return _StepState(
        status=SetupStepStatus.SAVED if done else SetupStepStatus.EMPTY,
        is_mandatory=True,
        is_complete=done,
        filled_count=1 if done else 0,
        required_count=1,
    )


def _current_step_index(states: tuple[_StepState, ...]) -> int:
    """Where the "Current Step" pill sits, and where a returning student lands.

    Three passes, in this order:

    1. **The first incomplete mandatory step, review excluded.** A half-filled
       section 1 is what actually blocks submission while an untouched section
       4 does not, so pointing at the first merely-*empty* step would walk a
       student past the one section they still owe fields on.

       Review is excluded from this pass even though it is mandatory, because
       it is permanently incomplete until the very last action of the flow.
       Including it would send a student who finished the two required
       sections straight to Submit, skipping the three optional steps they
       have not seen yet — the pill would recommend finishing before they were
       ever shown projects, certificates or experience.

    2. **The first empty step.** This is where the optional steps get their
       turn, and — once they are all touched — where review picks itself up,
       since an unsubmitted review step is `EMPTY`.

    3. **Review.** Everything is done and submitted; the pill rests on the last
       step rather than disappearing, so the screen always has exactly one
       active circle.
    """
    for index, state in enumerate(states):
        if index != REVIEW_STEP_INDEX and state.is_mandatory and not state.is_complete:
            return index

    for index, state in enumerate(states):
        if state.status is SetupStepStatus.EMPTY:
            return index

    return REVIEW_STEP_INDEX


def load_resume_state(db: Session, profile: CandidateProfile) -> ResumeSetupState:
    """Read the newest non-deleted upload and the newest draft made from it.

    Newest-only, not a list: the screen shows one resume card, and an older
    superseded attempt is history rather than something the student can act on.
    """
    upload = db.execute(
        select(ResumeUpload)
        .where(
            ResumeUpload.candidate_profile_id == profile.id,
            ResumeUpload.deleted_at.is_(None),
        )
        .order_by(ResumeUpload.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if upload is None:
        return ResumeSetupState(has_upload=False)

    draft = db.execute(
        select(ResumeExtractionDraft)
        .where(
            ResumeExtractionDraft.resume_upload_id == upload.id,
            ResumeExtractionDraft.candidate_profile_id == profile.id,
        )
        .order_by(ResumeExtractionDraft.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    return ResumeSetupState(
        has_upload=True,
        upload_id=upload.id,
        status=_UPLOAD_STATUS_TO_PARSE_STATE[upload.status],
        async_job_id=upload.async_job_id,
        draft_id=draft.id if draft is not None else None,
        draft_status=draft.status if draft is not None else None,
        original_filename=upload.original_filename,
        error=upload.error,
    )


def build_setup_state(
    completeness: ProfileCompleteness,
    resume: ResumeSetupState,
) -> SetupState:
    """Assemble the screen's payload. Pure — every input is already resolved."""
    by_key = {section.key: section for section in completeness.sections}

    # Iterate `SETUP_STEPS`, not `completeness.sections`, so step order is this
    # module's declared order and a reshuffle upstream cannot renumber the UI.
    states: list[_StepState] = []
    for meta in SETUP_STEPS:
        if meta.section_key is not None:
            states.append(_section_step_state(by_key[meta.section_key]))
        elif meta.key == STEP_CHOOSE:
            states.append(_flag_step_state(done=completeness.onboarding_choice is not None))
        else:
            states.append(_flag_step_state(done=completeness.is_onboarding_submitted))

    current = _current_step_index(tuple(states))

    steps = tuple(
        SetupStep(
            key=meta.key,
            index=index,
            title=meta.title,
            subtitle=meta.subtitle,
            status=state.status,
            is_mandatory=state.is_mandatory,
            is_current=index == current,
            filled_count=state.filled_count,
            required_count=state.required_count,
        )
        for index, (meta, state) in enumerate(zip(SETUP_STEPS, states))
    )

    return SetupState(
        # The scoring weights in `completeness.py` sum to 100, so strength *is*
        # the percentage. Named separately because the screen renders a
        # percentage and should not have to know that coincidence holds.
        completion_percentage=completeness.profile_strength,
        current_step_index=current,
        meets_section_requirements=completeness.meets_section_requirements,
        is_discoverable=completeness.is_discoverable,
        blocking=completeness.blocking,
        steps=steps,
        resume=resume,
        is_submitted=completeness.is_onboarding_submitted,
        # The submit gate is exactly the section requirements: basic, GitHub
        # and one project. Coding profiles, certificates and experience stay
        # optional for the same reason they are optional everywhere else — a
        # first-year with no internships must still be able to finish
        # onboarding, and a gate they cannot satisfy is a gate that ends the
        # signup.
        #
        # Consent is deliberately *not* part of this. It is given on the review
        # screen itself, so folding it in would leave `can_submit` false on the
        # only screen that can turn it true, and the client would have no way
        # to tell "you still owe a project" from "tick the box below". The
        # server still refuses a submission without it —
        # `service.submit_onboarding`.
        can_submit=completeness.meets_section_requirements,
    )
