"""Student profile-builder API routes.

One GET and one PUT per section, plus a cross-section completeness overview
for the stepper's initial render. There is deliberately no combined
profile-update endpoint: each section is independently saveable so a student
can finish the profile over several sittings.

Thin by design: parse request -> call `service` -> return a schema, matching
`domains/auth/router.py`. Endpoints stay plain `def` to match this codebase's
sync-SQLAlchemy convention — FastAPI runs them in a threadpool.

Authorization is uniform: `get_own_profile` resolves the profile from the
authenticated candidate, so no route takes a profile id and a recruiter is
rejected with 403 before any handler body runs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.domains.auth.models import CandidateProfile
from src.domains.student import service
from src.domains.student.completeness import ProfileCompleteness
from src.domains.student.dependencies import get_own_profile
from src.domains.student.schemas import (
    BasicInfoRequest,
    BasicInfoResponse,
    CertificateResponse,
    CertificatesRequest,
    CertificatesResponse,
    CodingPlatformAccountResponse,
    ExperienceResponse,
    ExperiencesRequest,
    ExperiencesResponse,
    GithubAccountResponse,
    OnboardingChoiceRequest,
    ProfileCompletenessResponse,
    ProjectResponse,
    ProjectsRequest,
    ProjectsResponse,
    ResumeSetupStateResponse,
    SectionEnvelope,
    SectionStatus,
    SetupStateResponse,
    SetupStepResponse,
    TechnicalRequest,
    TechnicalResponse,
)
from src.domains.student.setup_state import build_setup_state, load_resume_state

router = APIRouter(prefix="/api/v1/student/profile", tags=["student-profile"])


def _completeness_response(completeness: ProfileCompleteness) -> ProfileCompletenessResponse:
    return ProfileCompletenessResponse(
        profile_strength=completeness.profile_strength,
        meets_section_requirements=completeness.meets_section_requirements,
        is_discoverable=completeness.is_discoverable,
        onboarding_choice=completeness.onboarding_choice,
        blocking=list(completeness.blocking),
        sections=[
            SectionStatus(
                key=section.key,
                is_complete=section.is_complete,
                is_filled=section.is_filled,
                is_mandatory=section.is_mandatory,
                filled_count=section.filled_count,
                required_count=section.required_count,
                points_earned=section.points_earned,
                points_possible=section.points_possible,
                verification=section.verification,
                missing=list(section.missing),
            )
            for section in completeness.sections
        ],
    )


# --------------------------------------------------------------------------
# Cross-section overview
# --------------------------------------------------------------------------


@router.get("/completeness", response_model=ProfileCompletenessResponse)
def read_completeness(
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> ProfileCompletenessResponse:
    """Strength, discoverability, and per-section state for the stepper."""
    return _completeness_response(service.get_completeness(db, profile))


@router.get("/setup-state", response_model=SetupStateResponse)
def read_setup_state(
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> SetupStateResponse:
    """Everything `/student/profile/setup` renders, in one request.

    Two reads — the completeness snapshot and the newest resume upload — rather
    than the three round trips the screen would otherwise make before it could
    draw a stepper without a wrong default in it.
    """
    state = build_setup_state(
        service.get_completeness(db, profile),
        load_resume_state(db, profile),
    )
    return SetupStateResponse(
        completion_percentage=state.completion_percentage,
        current_step_index=state.current_step_index,
        meets_section_requirements=state.meets_section_requirements,
        is_discoverable=state.is_discoverable,
        blocking=list(state.blocking),
        steps=[
            SetupStepResponse(
                key=step.key,
                index=step.index,
                title=step.title,
                subtitle=step.subtitle,
                status=step.status,
                is_mandatory=step.is_mandatory,
                is_current=step.is_current,
                filled_count=step.filled_count,
                required_count=step.required_count,
            )
            for step in state.steps
        ],
        resume=ResumeSetupStateResponse(
            has_upload=state.resume.has_upload,
            upload_id=state.resume.upload_id,
            status=state.resume.status,
            async_job_id=state.resume.async_job_id,
            draft_id=state.resume.draft_id,
            draft_status=state.resume.draft_status,
            original_filename=state.resume.original_filename,
            error=state.resume.error,
        ),
    )


@router.post("/onboarding", response_model=ProfileCompletenessResponse)
def choose_onboarding_path(
    payload: OnboardingChoiceRequest,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> ProfileCompletenessResponse:
    """Answers the one-time onboarding fork. Idempotent — see
    `service.set_onboarding_choice` for why re-answering is a no-op rather
    than a conflict."""
    return _completeness_response(service.set_onboarding_choice(db, profile, payload.choice))


# --------------------------------------------------------------------------
# Section 1 — Basic Information
# --------------------------------------------------------------------------


@router.get("/sections/basic", response_model=SectionEnvelope[BasicInfoResponse])
def read_basic_info(
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> SectionEnvelope[BasicInfoResponse]:
    return SectionEnvelope(
        data=BasicInfoResponse.model_validate(profile),
        completeness=_completeness_response(service.get_completeness(db, profile)),
    )


@router.put("/sections/basic", response_model=SectionEnvelope[BasicInfoResponse])
def update_basic_info(
    payload: BasicInfoRequest,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> SectionEnvelope[BasicInfoResponse]:
    completeness = service.replace_basic_info(db, profile, payload)
    return SectionEnvelope(
        data=BasicInfoResponse.model_validate(profile),
        completeness=_completeness_response(completeness),
    )


# --------------------------------------------------------------------------
# Section 2 — Technical Verification
# --------------------------------------------------------------------------


def _technical_response(db: Session, profile: CandidateProfile) -> TechnicalResponse:
    snapshot = service.load_snapshot(db, profile)
    return TechnicalResponse(
        github_account=(
            GithubAccountResponse.model_validate(snapshot.github_account)
            if snapshot.github_account is not None
            else None
        ),
        coding_profiles=[
            CodingPlatformAccountResponse.model_validate(account) for account in snapshot.coding_profiles
        ],
    )


@router.get("/sections/technical", response_model=SectionEnvelope[TechnicalResponse])
def read_technical(
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> SectionEnvelope[TechnicalResponse]:
    return SectionEnvelope(
        data=_technical_response(db, profile),
        completeness=_completeness_response(service.get_completeness(db, profile)),
    )


@router.put("/sections/technical", response_model=SectionEnvelope[TechnicalResponse])
def update_technical(
    payload: TechnicalRequest,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> SectionEnvelope[TechnicalResponse]:
    completeness = service.replace_technical(db, profile, payload)
    return SectionEnvelope(
        data=_technical_response(db, profile),
        completeness=_completeness_response(completeness),
    )


# --------------------------------------------------------------------------
# Section 3 — Skills & Projects
# --------------------------------------------------------------------------


def _projects_response(db: Session, profile: CandidateProfile) -> ProjectsResponse:
    snapshot = service.load_snapshot(db, profile)
    return ProjectsResponse(
        projects=[ProjectResponse.model_validate(project) for project in snapshot.projects]
    )


@router.get("/sections/projects", response_model=SectionEnvelope[ProjectsResponse])
def read_projects(
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> SectionEnvelope[ProjectsResponse]:
    return SectionEnvelope(
        data=_projects_response(db, profile),
        completeness=_completeness_response(service.get_completeness(db, profile)),
    )


@router.put("/sections/projects", response_model=SectionEnvelope[ProjectsResponse])
def update_projects(
    payload: ProjectsRequest,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> SectionEnvelope[ProjectsResponse]:
    completeness = service.replace_projects(db, profile, payload)
    return SectionEnvelope(
        data=_projects_response(db, profile),
        completeness=_completeness_response(completeness),
    )


# --------------------------------------------------------------------------
# Section 4 — Certificates & Achievements
# --------------------------------------------------------------------------


def _certificates_response(db: Session, profile: CandidateProfile) -> CertificatesResponse:
    snapshot = service.load_snapshot(db, profile)
    return CertificatesResponse(
        certificates=[CertificateResponse.model_validate(item) for item in snapshot.certificates]
    )


@router.get("/sections/certificates", response_model=SectionEnvelope[CertificatesResponse])
def read_certificates(
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> SectionEnvelope[CertificatesResponse]:
    return SectionEnvelope(
        data=_certificates_response(db, profile),
        completeness=_completeness_response(service.get_completeness(db, profile)),
    )


@router.put("/sections/certificates", response_model=SectionEnvelope[CertificatesResponse])
def update_certificates(
    payload: CertificatesRequest,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> SectionEnvelope[CertificatesResponse]:
    completeness = service.replace_certificates(db, profile, payload)
    return SectionEnvelope(
        data=_certificates_response(db, profile),
        completeness=_completeness_response(completeness),
    )


# --------------------------------------------------------------------------
# Section 5 — Experience
# --------------------------------------------------------------------------


def _experiences_response(db: Session, profile: CandidateProfile) -> ExperiencesResponse:
    snapshot = service.load_snapshot(db, profile)
    return ExperiencesResponse(
        experiences=[ExperienceResponse.model_validate(item) for item in snapshot.experiences]
    )


@router.get("/sections/experience", response_model=SectionEnvelope[ExperiencesResponse])
def read_experiences(
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> SectionEnvelope[ExperiencesResponse]:
    return SectionEnvelope(
        data=_experiences_response(db, profile),
        completeness=_completeness_response(service.get_completeness(db, profile)),
    )


@router.put("/sections/experience", response_model=SectionEnvelope[ExperiencesResponse])
def update_experiences(
    payload: ExperiencesRequest,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> SectionEnvelope[ExperiencesResponse]:
    completeness = service.replace_experiences(db, profile, payload)
    return SectionEnvelope(
        data=_experiences_response(db, profile),
        completeness=_completeness_response(completeness),
    )
