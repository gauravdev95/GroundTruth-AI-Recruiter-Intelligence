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
    SECTION_EXPERIENCE,
    SECTION_PROJECTS,
    SECTION_TECHNICAL,
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


@dataclass(frozen=True)
class StepMeta:
    key: str
    title: str
    subtitle: str


# Copy is served from here rather than hardcoded in the component so the five
# labels the screen shows and the five sections the API scores can never drift
# apart. Order is the step order and is load-bearing — `index` is positional.
SETUP_STEPS: tuple[StepMeta, ...] = (
    StepMeta(SECTION_BASIC, "Basic Information", "Personal details & education"),
    StepMeta(SECTION_TECHNICAL, "Technical Profiles", "GitHub, LeetCode & more"),
    StepMeta(SECTION_PROJECTS, "Projects", "Add & verify your projects"),
    StepMeta(SECTION_CERTIFICATES, "Certificates & Achievements", "Showcase your accomplishments"),
    StepMeta(SECTION_EXPERIENCE, "Experience", "Add your work experience"),
)


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


def _current_step_index(sections: tuple[SectionScore, ...], statuses: tuple[SetupStepStatus, ...]) -> int:
    """Where the "Current Step" pill sits.

    Mandatory-but-incomplete wins over merely-empty, because a half-filled
    section 1 is what actually blocks discoverability while an untouched
    section 3 does not. Pointing at the first *empty* step instead would walk a
    student past the one section they still owe fields on.

    With everything complete the pill rests on the last step rather than
    disappearing — the screen always has exactly one active circle.
    """
    for index, section in enumerate(sections):
        if section.is_mandatory and not section.is_complete:
            return index

    for index, status in enumerate(statuses):
        if status is SetupStepStatus.EMPTY:
            return index

    return len(SETUP_STEPS) - 1


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
    ordered = tuple(by_key[meta.key] for meta in SETUP_STEPS)
    statuses = tuple(_step_status(section) for section in ordered)
    current = _current_step_index(ordered, statuses)

    steps = tuple(
        SetupStep(
            key=meta.key,
            index=index,
            title=meta.title,
            subtitle=meta.subtitle,
            status=statuses[index],
            is_mandatory=section.is_mandatory,
            is_current=index == current,
            filled_count=section.filled_count,
            required_count=section.required_count,
        )
        for index, (meta, section) in enumerate(zip(SETUP_STEPS, ordered))
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
    )
