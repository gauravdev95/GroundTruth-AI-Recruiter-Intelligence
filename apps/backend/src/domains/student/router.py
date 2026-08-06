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

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.config import get_storage_settings
from src.core.exceptions import NotFound
from src.db.database import get_db
from src.domains.auth.models import CandidateProfile, TargetRole
from src.domains.auth.rate_limit import limiter
from src.domains.student import certificate_files, live_checks, profile_photos, service
from src.domains.student.activity import build_activity_feed
from src.domains.student.completeness import ProfileCompleteness
from src.domains.student.dependencies import get_own_profile
from src.domains.student.models import Certificate
from src.domains.student.schemas import (
    ActivityFeedResponse,
    ActivityStageResponse,
    BasicInfoRequest,
    BasicInfoResponse,
    CertificateFileUrlResponse,
    CertificateResponse,
    CertificatesRequest,
    CertificatesResponse,
    CertificateUploadResponse,
    CodingPlatformAccountResponse,
    CodingProfilesRequest,
    ExperienceResponse,
    ExperiencesRequest,
    ExperiencesResponse,
    GithubAccountResponse,
    OnboardingChoiceRequest,
    ProfileCompletenessResponse,
    ProfilePhotoResponse,
    ProfileSubmitRequest,
    ProfileSubmitResponse,
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
    VerifyCodingProfileRequest,
    VerifyCodingProfileResponse,
    VerifyGithubRequest,
    VerifyGithubResponse,
)
from src.domains.student.setup_state import build_setup_state, load_resume_state

router = APIRouter(prefix="/api/v1/student/profile", tags=["student-profile"])


def _basic_response(profile: CandidateProfile) -> BasicInfoResponse:
    """Assemble section 1 from the profile plus the account's name.

    Built by hand rather than `model_validate(profile)` because `full_name`
    lives on `User`, not `CandidateProfile` — the name belongs to the
    account, and copying it onto the profile to make one `model_validate`
    call work would create two answers to what a person is called.
    """
    return BasicInfoResponse(
        full_name=profile.user.full_name,
        phone_number=profile.phone_number,
        headline=profile.headline,
        college=profile.college,
        degree=profile.degree,
        branch=profile.branch,
        graduation_year=profile.graduation_year,
        location=profile.location,
        target_role=profile.target_role,
        target_roles=(
            [TargetRole(role) for role in profile.target_roles] if profile.target_roles else None
        ),
        about=profile.about,
        has_profile_photo=profile.profile_photo_object_key is not None,
    )


def _completeness_response(completeness: ProfileCompleteness) -> ProfileCompletenessResponse:
    return ProfileCompletenessResponse(
        profile_strength=completeness.profile_strength,
        meets_section_requirements=completeness.meets_section_requirements,
        is_discoverable=completeness.is_discoverable,
        onboarding_choice=completeness.onboarding_choice,
        is_onboarding_submitted=completeness.is_onboarding_submitted,
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
        is_submitted=state.is_submitted,
        can_submit=state.can_submit,
    )


@router.get("/onboarding/activity", response_model=ActivityFeedResponse)
def read_activity_feed(
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> ActivityFeedResponse:
    """The live analysis feed the post-submit screen polls.

    Read-only: builds nothing, enqueues nothing, and writes nothing. A
    polling endpoint that had side effects would run them once per poll.

    Not rate-limited, deliberately. The client polls this every few seconds
    while `is_running` is true and stops when it goes false, so the natural
    call volume is bounded by the work itself; a limiter here would break the
    screen for exactly the students with the most claims to check, which is
    the opposite of who should get the worst experience. The query cost is
    six indexed reads against rows already scoped to one profile.
    """
    feed = build_activity_feed(db, profile.id, now=datetime.now(timezone.utc))
    return ActivityFeedResponse(
        stages=[
            ActivityStageResponse(
                key=stage.key,
                label=stage.label,
                state=stage.state,
                total=stage.total,
                settled=stage.settled,
                started_at=stage.started_at,
                finished_at=stage.finished_at,
                detail=stage.detail,
            )
            for stage in feed.stages
        ],
        is_running=feed.is_running,
        as_of=feed.as_of,
    )


@router.post("/submit", response_model=ProfileSubmitResponse)
def submit_profile(
    payload: ProfileSubmitRequest,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> ProfileSubmitResponse:
    """Finish onboarding — the last step of the setup flow.

    Requires the review step's consent (`ProfileSubmitRequest`), which is
    recorded in the same transaction as the submission itself.

    Returns as soon as the submission is recorded. Every verification it starts
    runs in the background and the candidate is emailed when the results
    settle; nothing about this response waits on a third party.

    Idempotent, and a 409 only when the mandatory sections are incomplete —
    see `service.submit_onboarding`. A missing or `false` consent is a 422 from
    the schema, not a 409: it is a malformed submission rather than a profile
    that is not ready.
    """
    result = service.submit_onboarding(db, profile, consent=payload.consent)
    return ProfileSubmitResponse(
        is_submitted=True,
        submitted_at=result.submitted_at,
        queued_verifications=result.queued_verifications,
        completeness=_completeness_response(result.completeness),
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
        data=_basic_response(profile),
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
        data=_basic_response(profile),
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


@router.put("/sections/coding", response_model=SectionEnvelope[TechnicalResponse])
def update_coding_profiles(
    payload: CodingProfilesRequest,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> SectionEnvelope[TechnicalResponse]:
    """Onboarding stage 4 — coding profiles without touching GitHub.

    Returns the whole `TechnicalResponse` rather than the coding half alone, so
    the client's cache for this pair stays consistent from either writer. It is
    one query more than strictly needed and it removes the class of bug where
    saving the optional section leaves a stale GitHub account rendered beside
    the fresh handles.

    An empty `coding_profiles` is a valid body — "Skip for now" sends it. There
    is no GET beside this one: `GET /sections/technical` already returns both.
    """
    completeness = service.replace_coding_profiles(db, profile, payload)
    return SectionEnvelope(
        data=_technical_response(db, profile),
        completeness=_completeness_response(completeness),
    )


# --------------------------------------------------------------------------
# Profile photo
# --------------------------------------------------------------------------


@router.get("/photo", response_model=ProfilePhotoResponse)
def read_profile_photo(
    profile: CandidateProfile = Depends(get_own_profile),
) -> ProfilePhotoResponse:
    """A short-lived link to the student's photo, or nulls if there is none.

    Not a 404 for the no-photo case: the caller is an avatar component, and
    "no photo" is the ordinary answer it renders initials for.
    """
    key = profile.profile_photo_object_key
    if key is None:
        return ProfilePhotoResponse(url=None, content_type=None, expires_in_seconds=None)

    return ProfilePhotoResponse(
        url=profile_photos.download_url(key),
        content_type=profile.profile_photo_content_type,
        expires_in_seconds=get_storage_settings().s3_presign_expiry_seconds,
    )


@router.post("/photo", response_model=SectionEnvelope[BasicInfoResponse])
@limiter.limit("30/hour")
def upload_profile_photo(
    request: Request,
    file: UploadFile = File(...),
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> SectionEnvelope[BasicInfoResponse]:
    """Store a photo and attach it to the profile in one call.

    Unlike a certificate upload — which hands back an object key for the client
    to echo on the next section save — this attaches immediately. A certificate
    is one row of a list that has to be re-sent as a whole; a photo is singular,
    so there is nothing to reconcile it against and the extra round trip would
    only create a window where an uploaded object belongs to nobody.

    Returns the basic-info envelope so the caller's section 1 cache picks up
    `has_profile_photo` without a follow-up request.
    """
    completeness = service.store_profile_photo(
        db, profile, file.file, size_bytes=file.size or 0
    )
    return SectionEnvelope(
        data=_basic_response(profile),
        completeness=_completeness_response(completeness),
    )


@router.delete("/photo", response_model=SectionEnvelope[BasicInfoResponse])
def delete_profile_photo(
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> SectionEnvelope[BasicInfoResponse]:
    """Remove the photo. Idempotent — deleting when there is none is a no-op."""
    completeness = service.remove_profile_photo(db, profile)
    return SectionEnvelope(
        data=_basic_response(profile),
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


@router.post("/certificates/uploads", response_model=CertificateUploadResponse)
@limiter.limit("30/hour")
def upload_certificate_file(
    request: Request,
    file: UploadFile = File(...),
    profile: CandidateProfile = Depends(get_own_profile),
) -> CertificateUploadResponse:
    """Store a certificate PDF/image and return the key to attach it with.

    Separate from the certificates PUT rather than a multipart section save:
    the section is a JSON list that is replaced wholesale, and folding an
    arbitrary number of files into that request would make the one endpoint
    responsible for both a document store and a list reconciliation. Uploading
    first also means a failed upload costs the student a retry on one file
    rather than the whole section.

    Nothing is written to the database here — the object exists, and it becomes
    a *certificate's* file only when the section save references its key. An
    orphaned object is recoverable garbage; a row pointing at an object that
    was never stored is a broken download.
    """
    size_bytes = file.size or 0
    key, content_type, _suffix = certificate_files.store(
        file.file, candidate_profile_id=profile.id, size_bytes=size_bytes
    )
    return CertificateUploadResponse(
        file_object_key=key,
        # Truncated, not sanitised further: it is only ever rendered as text
        # and used as the download filename, never as a path — the stored key
        # is generated server-side (`certificate_files.build_key`).
        file_name=(file.filename or "certificate")[:255],
        file_content_type=content_type,
        file_size_bytes=size_bytes,
    )


@router.get("/certificates/{certificate_id}/file", response_model=CertificateFileUrlResponse)
def read_certificate_file_url(
    certificate_id: uuid.UUID,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> CertificateFileUrlResponse:
    """Mint a short-lived link to the candidate's own certificate file.

    The scope filter is the authorization: the query is bounded to this
    candidate's rows, so a certificate id belonging to someone else is a 404
    rather than a permission error — which is also the answer that leaks least.
    """
    certificate = db.execute(
        select(Certificate).where(
            Certificate.id == certificate_id,
            Certificate.candidate_profile_id == profile.id,
            Certificate.deleted_at.is_(None),
        )
    ).scalar_one_or_none()

    if certificate is None or not certificate.file_object_key:
        raise NotFound("No file is attached to this certificate")

    return CertificateFileUrlResponse(
        url=certificate_files.download_url(certificate.file_object_key),
        file_name=certificate.file_name or "certificate",
        expires_in_seconds=get_storage_settings().s3_presign_expiry_seconds,
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


# --------------------------------------------------------------------------
# Live verification — the "Verify" buttons on step 3
# --------------------------------------------------------------------------
#
# These run a third-party call inside the request, which every other endpoint
# in this file deliberately avoids. They are the exception because the whole
# point of the button is an answer *now*: a handle typo caught at save time
# instead of by an email hours later. They stay safe to expose because they
# write nothing — see `live_checks.py` — and they are rate limited per caller,
# since each one spends this deployment's budget against a shared third-party
# quota.


@router.post("/verify/github", response_model=VerifyGithubResponse)
@limiter.limit("20/hour")
def verify_github(
    request: Request,
    payload: VerifyGithubRequest,
    profile: CandidateProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
) -> VerifyGithubResponse:
    """Check that a GitHub username exists. Persists nothing."""
    result = live_checks.check_github(
        db, candidate_profile_id=profile.id, username=payload.github_username
    )
    return VerifyGithubResponse(
        outcome=result.outcome,
        message=result.message,
        github_username=result.github_username,
        profile_url=result.profile_url,
        avatar_url=result.avatar_url,
        public_repos=result.public_repos,
        is_oauth_connected=result.is_oauth_connected,
    )


@router.post("/verify/coding-profile", response_model=VerifyCodingProfileResponse)
@limiter.limit("40/hour")
def verify_coding_profile(
    request: Request,
    payload: VerifyCodingProfileRequest,
    profile: CandidateProfile = Depends(get_own_profile),
) -> VerifyCodingProfileResponse:
    """Check a competitive-programming handle. Persists nothing.

    A `verified` outcome is only possible on Codeforces and LeetCode; every
    other platform caps at `unconfirmed`, and the message says so rather than
    letting the UI imply a check that did not happen.
    """
    result = live_checks.check_coding_profile(
        platform=payload.platform, handle=payload.handle, custom_url=payload.profile_url
    )
    return VerifyCodingProfileResponse(
        outcome=result.outcome,
        message=result.message,
        platform=result.platform,
        handle=result.handle,
        profile_url=result.profile_url,
        details=result.details,
    )
