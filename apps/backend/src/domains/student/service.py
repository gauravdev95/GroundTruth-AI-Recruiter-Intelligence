"""Business logic for the student profile builder.

Each section is saved independently — there is no combined write path — so a
student can complete the profile across several sittings. Every save follows
the same shape:

    mutate rows -> flush -> recompute completeness -> persist strength -> commit

`profile_strength` and `is_discoverable` are recomputed from the flushed rows
on every save (`completeness.py`), so they cannot drift from the data and are
never read from the request.

**Reconciliation, not truncate-and-reinsert.** A PUT replaces a section's
contents, but the list sections match incoming items against existing rows by
a natural key first. Blindly deleting and reinserting would reset
`verification_status` on every save, throwing away results a Phase II worker
had already written — a student re-saving section 3 to fix a typo would
silently un-verify their repositories. Unmatched existing rows are
soft-deleted; genuinely new or changed claims are the only ones queued for
verification.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.exceptions import Conflict, Forbidden, NotFound
from src.domains.auth.models import CandidateProfile, User
from src.domains.student import evidence, profile_photos, schemas
from src.domains.student.completeness import (
    ProfileCompleteness,
    ProfileSnapshot,
    apply_completeness,
    compute_completeness,
)
from src.domains.student.models import (
    Certificate,
    CodingPlatformAccount,
    Experience,
    GithubAccount,
    Project,
    ProjectKind,
    VerificationStatus,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def get_profile_for_user(db: Session, user: User) -> CandidateProfile:
    profile = db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise NotFound("Candidate profile not found")
    return profile


def _active_github_account(db: Session, profile_id: uuid.UUID) -> GithubAccount | None:
    return db.execute(
        select(GithubAccount)
        .where(GithubAccount.candidate_profile_id == profile_id, GithubAccount.deleted_at.is_(None))
        .order_by(GithubAccount.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _active_coding_profiles(db: Session, profile_id: uuid.UUID) -> list[CodingPlatformAccount]:
    return list(
        db.execute(
            select(CodingPlatformAccount)
            .where(
                CodingPlatformAccount.candidate_profile_id == profile_id,
                CodingPlatformAccount.deleted_at.is_(None),
            )
            .order_by(CodingPlatformAccount.created_at)
        ).scalars()
    )


def _active_projects(db: Session, profile_id: uuid.UUID) -> list[Project]:
    return list(
        db.execute(
            select(Project)
            .where(Project.candidate_profile_id == profile_id, Project.deleted_at.is_(None))
            .order_by(Project.position, Project.created_at)
        ).scalars()
    )


def _active_certificates(db: Session, profile_id: uuid.UUID) -> list[Certificate]:
    return list(
        db.execute(
            select(Certificate)
            .where(Certificate.candidate_profile_id == profile_id, Certificate.deleted_at.is_(None))
            .order_by(Certificate.position, Certificate.created_at)
        ).scalars()
    )


def _active_experiences(db: Session, profile_id: uuid.UUID) -> list[Experience]:
    return list(
        db.execute(
            select(Experience)
            .where(Experience.candidate_profile_id == profile_id, Experience.deleted_at.is_(None))
            .order_by(Experience.position, Experience.created_at)
        ).scalars()
    )


def _has_profile_embedding(db: Session, candidate_profile_id: uuid.UUID) -> bool:
    """Whether a vector exists for this profile at the current embedding model
    version. Imported inline to keep the student domain from taking a
    module-level dependency on `domains/matching/`, matching how
    `_sync_matching_index` already reaches across that boundary."""
    from src.domains.matching.embeddings import get_embedding
    from src.domains.matching.models import EmbeddableEntityType

    return (
        get_embedding(
            db,
            entity_type=EmbeddableEntityType.CANDIDATE_PROFILE,
            entity_id=candidate_profile_id,
        )
        is not None
    )


def _completed_interview_scores(db: Session, candidate_profile_id: uuid.UUID) -> tuple[float, ...]:
    """Total scores of this candidate's COMPLETED interviews.

    Both groundings count. A profile interview is a genuine completed
    interview — it is the escape hatch that keeps a candidate with no
    verifiable repository from being permanently undiscoverable — so filtering
    to repository interviews here would silently reinstate the deadlock the
    escape hatch exists to prevent.

    Imported inline for the same boundary reason as `_has_profile_embedding`.
    """
    from src.domains.interview.models import Interview, InterviewStatus

    rows = db.execute(
        select(Interview.total_score).where(
            Interview.candidate_profile_id == candidate_profile_id,
            Interview.status == InterviewStatus.COMPLETED,
            Interview.total_score.is_not(None),
        )
    ).scalars()
    return tuple(float(score) for score in rows)


def load_snapshot(db: Session, profile: CandidateProfile) -> ProfileSnapshot:
    return ProfileSnapshot(
        profile=profile,
        github_account=_active_github_account(db, profile.id),
        coding_profiles=tuple(_active_coding_profiles(db, profile.id)),
        projects=tuple(_active_projects(db, profile.id)),
        certificates=tuple(_active_certificates(db, profile.id)),
        experiences=tuple(_active_experiences(db, profile.id)),
        has_embedding=_has_profile_embedding(db, profile.id),
        completed_interview_scores=_completed_interview_scores(db, profile.id),
    )


def _finalize(
    db: Session,
    profile: CandidateProfile,
    queued: list[evidence.QueuedVerification | None] | None = None,
) -> ProfileCompleteness:
    """Flush pending writes, recompute strength from them, then commit once.

    `queued` is dispatched to Celery only **after** `db.commit()` — the same
    commit-before-publish ordering `resume/service.py::create_upload` uses,
    and for the same reason: a publish that races ahead of the row it
    references is worse than a job that briefly sits `PENDING`.
    """
    db.flush()
    completeness = compute_completeness(load_snapshot(db, profile))
    apply_completeness(profile, completeness)
    db.commit()
    if queued:
        evidence.dispatch_all(queued)
    _sync_matching_index(db, profile.id, completeness.meets_section_requirements)
    return completeness


def get_completeness(db: Session, profile: CandidateProfile) -> ProfileCompleteness:
    return compute_completeness(load_snapshot(db, profile))


def set_onboarding_choice(
    db: Session, profile: CandidateProfile, choice: schemas.OnboardingChoice
) -> ProfileCompleteness:
    """Records the student's answer to the "Upload Resume vs. Build Manually"
    fork, once.

    A second call is a no-op rather than an error: the fork lives at a URL a
    student can navigate back to, and re-answering it should neither fail nor
    quietly rewrite history — the first answer is the one that happened. No
    profile data changes here, so `profile_strength` cannot move; completeness
    is returned only so the caller gets the same envelope every other
    profile write returns.
    """
    if profile.onboarding_choice is None:
        profile.onboarding_choice = choice
        db.commit()
        db.refresh(profile)
    return compute_completeness(load_snapshot(db, profile))


def _queue_unchecked_claims(
    db: Session, snapshot: ProfileSnapshot
) -> list[evidence.QueuedVerification | None]:
    """Queue background verification for every claim nothing has looked at yet.

    Only `UNVERIFIED` rows are queued, and the exclusions are the point:

    * `VERIFIED` is skipped so submitting does not undo a result. A GitHub
      account connected by OAuth is written straight to `VERIFIED`
      (`github_oauth.py`), and re-queueing it would drop it back to `PENDING`
      and then re-decide it from a *weaker* check than the one that already
      passed.
    * `PENDING` is skipped because a check is already running; `evidence.py`
      would suppress the duplicate anyway, so this only avoids the pointless
      round trip.
    * `REJECTED`/`FLAGGED` are skipped because re-running an identical check
      against unchanged data produces an identical answer. Editing the claim is
      what re-queues it, and editing is the only thing that could change the
      outcome.
    """
    queued: list[evidence.QueuedVerification | None] = []

    def unchecked(row) -> bool:
        return row.verification_status is VerificationStatus.UNVERIFIED

    if snapshot.github_account is not None and unchecked(snapshot.github_account):
        queued.append(evidence.queue_github_account(db, snapshot.github_account))

    queued.extend(
        evidence.queue_coding_platform_account(db, account)
        for account in snapshot.coding_profiles
        if unchecked(account)
    )
    queued.extend(
        evidence.queue_project_repository(db, project)
        for project in snapshot.projects
        if unchecked(project)
    )
    queued.extend(
        evidence.queue_certificate(db, certificate)
        for certificate in snapshot.certificates
        if unchecked(certificate)
    )
    queued.extend(
        evidence.queue_experience(db, experience)
        for experience in snapshot.experiences
        if unchecked(experience)
    )
    return queued


@dataclass(frozen=True)
class SubmissionResult:
    """What `submit_onboarding` produced. A record rather than a tuple because
    the router renders all three and a positional triple reads as noise."""

    completeness: ProfileCompleteness
    submitted_at: datetime
    queued_verifications: int


def submit_onboarding(
    db: Session, profile: CandidateProfile, *, consent: bool
) -> SubmissionResult:
    """Finish onboarding: stamp the submission and start every pending check.

    This is the only writer of `onboarding_submitted_at`, and the timestamp is
    what opens the dashboard — see that column for why the gate is an explicit
    act rather than the derived `meets_section_requirements` it replaced.

    **Idempotent.** Re-submitting is a no-op that returns the same state rather
    than a conflict: the review step is at a URL a student can reach twice, and
    a double-click must not be an error. It also does not re-queue anything —
    `_queue_unchecked_claims` already skips everything that has been looked at.

    **Nothing here blocks on verification.** The claims are queued inside this
    transaction and published to Celery after it commits (the ordering
    `_finalize` uses and for the same reason); the student is returned to
    immediately. Results land over the following minutes and the candidate is
    emailed once they settle (`jobs/tasks/verification.py::_finish`).

    Raises `Conflict` when the mandatory sections are not complete. That is the
    same bar `meets_section_requirements` describes everywhere else — basic
    info, GitHub, and at least one project. The rest stay optional, because a
    first-year with no internships must still be able to finish signing up.

    **Consent is recorded in the same transaction as the submission.** The
    caller has already validated that the box was ticked (`ProfileSubmitRequest`
    rejects `false` outright); what happens here is the write, stamped at the
    same instant as `onboarding_submitted_at` and committed with it. The two
    timestamps are separate columns answering separate questions, but there is
    no ordering in which one lands without the other — a profile analysed under
    a consent record that failed to write is the failure this arrangement
    exists to make impossible.
    """
    completeness = compute_completeness(load_snapshot(db, profile))

    if profile.onboarding_submitted_at is not None:
        return SubmissionResult(
            completeness=completeness,
            submitted_at=profile.onboarding_submitted_at,
            queued_verifications=0,
        )

    if not completeness.meets_section_requirements:
        raise Conflict(
            "Finish the required steps before submitting: " + ", ".join(completeness.blocking)
        )

    # Re-checked here even though `ProfileSubmitRequest` already rejects a
    # `false`. This function is what writes the consent record, so it is the
    # place that must be unable to write one that was never given — a future
    # caller that is not the HTTP route (a backfill script, a test helper)
    # would otherwise bypass the only check.
    if not consent:
        raise Conflict(
            "Consent is required to analyse your repositories and generate interview questions"
        )

    submitted_at = _utcnow()
    profile.onboarding_submitted_at = submitted_at
    # Not overwritten if already set: a student who reached this line has not
    # submitted before (the idempotent early return above saw to that), so the
    # only way a consent timestamp already exists is a submission that failed
    # after this point, and the earlier moment is the true one.
    if profile.onboarding_consent_at is None:
        profile.onboarding_consent_at = submitted_at
    queued = _queue_unchecked_claims(db, load_snapshot(db, profile))

    return SubmissionResult(
        completeness=_finalize(db, profile, queued),
        submitted_at=submitted_at,
        queued_verifications=sum(1 for item in queued if item is not None),
    )


def recompute_and_persist_strength(
    db: Session, candidate_profile_id: uuid.UUID, *, sync_matching_index: bool = True
) -> ProfileCompleteness | None:
    """Recompute `profile_strength`/`is_discoverable` outside of a section save.

    `profile_strength` only measures what is **filled**, not what is
    **verified** (`completeness.py`'s module docstring), so a verification
    consumer landing `VERIFIED`/`REJECTED`/`FLAGGED` never moves the number
    itself. It is still called after every verification write for two
    reasons: `SectionStatus.verification` (surfaced per-claim in the same
    response) must reflect the new status immediately, and a `github_user_id`
    resolved by `verify_github_account_task` changes what `load_snapshot`
    reads even though it changes no point total. Returns `None` if the
    profile no longer exists (a candidate can delete their account while a
    background verification is in flight).

    `sync_matching_index=False` is for the one caller that *is* the embedding
    worker (`jobs/tasks/matching.py::embed_and_match_candidate_task`): it calls
    this to persist the `is_discoverable` flip its own embedding just enabled,
    and re-running the sync there would enqueue another copy of the task that
    is currently running — an endless loop rather than a refresh.
    """
    profile = db.get(CandidateProfile, candidate_profile_id)
    if profile is None:
        return None
    db.flush()
    completeness = compute_completeness(load_snapshot(db, profile))
    apply_completeness(profile, completeness)
    db.commit()
    if sync_matching_index:
        _sync_matching_index(db, profile.id, completeness.meets_section_requirements)
    return completeness


def _sync_matching_index(db: Session, candidate_profile_id: uuid.UUID, is_eligible: bool) -> None:
    """Keeps the matching engine in step with discoverability, from
    **every** caller that can change it — a section save (this module) or a
    verification task (`jobs/tasks/verification.py::_finish`) alike.

    Keyed on *eligibility* (sections 1-2 complete), not on `is_discoverable`:
    the embedding this enqueues is the very thing `is_discoverable`
    additionally requires, so gating the enqueue on it would be circular and
    nothing would ever be embedded. `embed_and_match_candidate_task` flips
    `is_discoverable` once the vector lands.

    This is the fix for a real consistency gap: discoverability was
    previously only synced to `match_results` from the verification-task
    path, so (a) a candidate who filled sections 1-2 without any
    verification having completed yet was never embedded/matched at all,
    and (b) a candidate who *un*-filled a mandatory field (e.g. deleted
    their GitHub username) kept every stale `match_results` row forever —
    violating "a profile that becomes non-discoverable leaves the vector
    index". Centralizing the sync here, at the one choke point every
    strength recompute passes through, is what actually guarantees it.
    """
    from src.domains.matching import service as matching_service

    if is_eligible:
        _enqueue_embed_and_match(db, candidate_profile_id)
    else:
        matching_service.remove_matches_for_candidate(db, candidate_profile_id)


def _enqueue_embed_and_match(db: Session, candidate_profile_id: uuid.UUID) -> None:
    from src.jobs import dispatch as job_dispatch
    from src.jobs.celery_app import QUEUE_MATCHING
    from src.jobs.tasks.matching import embed_and_match_candidate_task
    from src.platform.models import AsyncJob

    job = AsyncJob(
        job_type="embed_and_match_candidate", payload={"candidate_profile_id": str(candidate_profile_id)}
    )
    db.add(job)
    db.commit()
    job_dispatch.dispatch(job, embed_and_match_candidate_task, queue=QUEUE_MATCHING)


# --------------------------------------------------------------------------
# Section 1 — Basic Information
# --------------------------------------------------------------------------


def replace_basic_info(
    db: Session, profile: CandidateProfile, payload: schemas.BasicInfoRequest
) -> ProfileCompleteness:
    # The name lives on the account, not the profile — this is the one field
    # in this section that writes through to `User`. It arrives here because
    # signup no longer collects it (see `auth/schemas.py`), so for most
    # students this save is the first time the platform learns their name.
    profile.user.full_name = payload.full_name
    # `None` means the field was omitted entirely, which must not wipe a
    # number the student supplied on a previous save. `""` is an explicit
    # clear and does overwrite.
    if payload.phone_number is not None:
        profile.phone_number = payload.phone_number
    profile.headline = payload.headline
    profile.college = payload.college
    profile.degree = payload.degree
    profile.branch = payload.branch
    profile.graduation_year = payload.graduation_year
    profile.location = payload.location
    # Both written here, in one statement, because they are one fact: the array
    # is the student's full preference set and the scalar is its first element.
    # This is the only writer of either, which is what lets
    # `CandidateProfile.target_role` promise it always equals `target_roles[0]`
    # without a constraint or a trigger enforcing it.
    profile.target_roles = [role.value for role in payload.target_roles]
    profile.target_role = payload.target_roles[0]
    profile.about = payload.about
    return _finalize(db, profile)


def store_profile_photo(
    db: Session, profile: CandidateProfile, fileobj: BinaryIO, *, size_bytes: int
) -> ProfileCompleteness:
    """Attach a photo, replacing and deleting any previous one.

    The upload happens **before** the old key is cleared, and the old object is
    only deleted once the row already points at the new one. The reverse order
    would leave a window in which a failed upload has already destroyed the
    photo the student had.

    Returns completeness like every other write on this profile, even though a
    photo scores nothing — the caller is a section-shaped endpoint and its
    envelope is the same shape as the rest.
    """
    previous_key = profile.profile_photo_object_key

    key, content_type = profile_photos.store(
        fileobj, candidate_profile_id=profile.id, size_bytes=size_bytes
    )
    profile.profile_photo_object_key = key
    profile.profile_photo_content_type = content_type

    completeness = _finalize(db, profile)
    # After the commit inside `_finalize`, so a rollback can never leave the
    # profile pointing at an object this call has already deleted.
    if previous_key is not None and previous_key != key:
        profile_photos.discard(previous_key)
    return completeness


def remove_profile_photo(db: Session, profile: CandidateProfile) -> ProfileCompleteness:
    """Detach the photo and delete the object. A no-op if there is none."""
    previous_key = profile.profile_photo_object_key
    profile.profile_photo_object_key = None
    profile.profile_photo_content_type = None

    completeness = _finalize(db, profile)
    profile_photos.discard(previous_key)
    return completeness


# --------------------------------------------------------------------------
# Section 2 — Technical Verification
# --------------------------------------------------------------------------


def replace_technical(
    db: Session, profile: CandidateProfile, payload: schemas.TechnicalRequest
) -> ProfileCompleteness:
    queued: list[evidence.QueuedVerification | None] = []
    queued.append(_reconcile_github_account(db, profile, payload.github_username))
    queued.extend(_reconcile_coding_profiles(db, profile, payload.coding_profiles))
    return _finalize(db, profile, queued)


def replace_coding_profiles(
    db: Session, profile: CandidateProfile, payload: schemas.CodingProfilesRequest
) -> ProfileCompleteness:
    """Onboarding stage 4 — the coding profiles alone.

    Reuses `_reconcile_coding_profiles`, so an empty list soft-deletes every
    existing handle exactly as an empty list on the combined endpoint always
    has. What it deliberately does *not* do is touch the GitHub account: the
    two are separate sections now, and a save on the optional one must not be
    able to retire the mandatory one's row.
    """
    queued = _reconcile_coding_profiles(db, profile, payload.coding_profiles)
    return _finalize(db, profile, queued)


def _reconcile_github_account(
    db: Session, profile: CandidateProfile, username: str
) -> evidence.QueuedVerification | None:
    existing = _active_github_account(db, profile.id)

    if existing is not None:
        if existing.github_username.casefold() == username.casefold():
            # Unchanged: leave the row (and whatever a worker has already
            # concluded about it) exactly as it is.
            return None
        # Changed identity: retire the old claim rather than mutating it, so
        # any verification already attached to the old username stays
        # historically accurate.
        existing.deleted_at = _utcnow()

    account = GithubAccount(
        candidate_profile_id=profile.id,
        github_username=username,
        profile_url=schemas.build_github_profile_url(username),
        verification_status=VerificationStatus.UNVERIFIED,
    )
    db.add(account)
    db.flush()  # assign account.id before it is referenced in a job payload
    return evidence.queue_github_account(db, account)


def _reconcile_coding_profiles(
    db: Session, profile: CandidateProfile, items: list[schemas.CodingPlatformItem]
) -> list[evidence.QueuedVerification | None]:
    existing_by_platform = {account.platform: account for account in _active_coding_profiles(db, profile.id)}
    submitted_platforms = {item.platform for item in items}
    queued: list[evidence.QueuedVerification | None] = []

    for platform, account in existing_by_platform.items():
        if platform not in submitted_platforms:
            account.deleted_at = _utcnow()

    for item in items:
        current = existing_by_platform.get(item.platform)
        profile_url = schemas.build_coding_platform_url(
            item.platform, item.handle, custom_url=item.profile_url
        )

        if current is not None:
            if current.handle == item.handle and current.profile_url == profile_url:
                # `profile_url` is compared too, not just the handle: for the
                # OTHER platform the student supplies the URL, so the same
                # handle can point somewhere new — and the URL is the thing
                # the verification worker actually fetches.
                continue
            # Same platform, new handle: update in place. The unique
            # (candidate, platform) constraint makes soft-delete-then-insert
            # collide, since the constraint ignores `deleted_at`.
            current.handle = item.handle
            current.profile_url = profile_url
            current.custom_platform_name = item.custom_platform_name
            current.verified_at = None
            queued.append(evidence.queue_coding_platform_account(db, current))
            continue

        account = CodingPlatformAccount(
            candidate_profile_id=profile.id,
            platform=item.platform,
            handle=item.handle,
            profile_url=profile_url,
            custom_platform_name=item.custom_platform_name,
            verification_status=VerificationStatus.UNVERIFIED,
        )
        db.add(account)
        db.flush()
        queued.append(evidence.queue_coding_platform_account(db, account))

    return queued


# --------------------------------------------------------------------------
# Section 3 — Skills & Projects
# --------------------------------------------------------------------------


def _project_key(kind: str, repo_url: str | None, title: str) -> tuple[str, str]:
    """Natural key: a repo is identified by URL, a described project by title."""
    if repo_url:
        return ("repo", repo_url.casefold())
    return ("title", f"{kind}:{title.casefold()}")


def replace_projects(
    db: Session, profile: CandidateProfile, payload: schemas.ProjectsRequest
) -> ProfileCompleteness:
    existing = _active_projects(db, profile.id)
    existing_by_key = {
        _project_key(project.kind.value, project.repo_url, project.title): project for project in existing
    }
    seen_keys: set[tuple[str, str]] = set()
    queued: list[evidence.QueuedVerification | None] = []

    for position, item in enumerate(payload.projects):
        key = _project_key(item.kind.value, item.repo_url, item.title)
        seen_keys.add(key)
        current = existing_by_key.get(key)

        if current is not None:
            # Same project, possibly edited metadata. The repo URL is what
            # verification is about and it is part of the key, so it cannot
            # have changed here — status is preserved deliberately.
            current.kind = item.kind
            current.title = item.title
            current.description = item.description
            current.live_demo_url = item.live_demo_url
            current.claimed_technologies = item.claimed_technologies
            current.is_primary = item.is_primary
            # `technologies` is deliberately NOT assigned. On this table it is
            # worker-owned: `verify_repository_task` writes what
            # `manifests.py` detected. Copying a request value over it would
            # let an edit to the title erase a completed analysis, and would
            # reintroduce self-declared technologies through the back door —
            # which is what `claimed_technologies` above exists to keep apart.
            current.position = position
            continue

        project = Project(
            candidate_profile_id=profile.id,
            kind=item.kind,
            title=item.title,
            description=item.description,
            repo_url=item.repo_url,
            live_demo_url=item.live_demo_url,
            # Empty until the verification worker detects them. A described
            # project has no manifest to analyse and so stays empty forever —
            # the honest result, not a gap to fill in by hand.
            technologies=[],
            claimed_technologies=item.claimed_technologies,
            is_primary=item.is_primary,
            position=position,
            verification_status=VerificationStatus.UNVERIFIED,
        )
        db.add(project)
        db.flush()
        queued.append(evidence.queue_project_repository(db, project))

    for key, project in existing_by_key.items():
        if key not in seen_keys:
            project.deleted_at = _utcnow()

    return _finalize(db, profile, queued)


def set_projects_from_github(
    db: Session, profile: CandidateProfile, *, selected_full_names: list[str]
) -> ProfileCompleteness:
    """Repo-picker write path — `POST /api/v1/student/github/repos/select`.

    Deliberately implemented as "build the equivalent `ProjectsRequest` and
    call `replace_projects`" rather than a parallel write path: this is the
    only way the picker gets the same natural-key reconciliation (re-picking
    the same repo doesn't reset an in-flight verification), the same
    `MAX_PROJECTS` cap, and the same verification-queueing that a manually
    typed repo URL gets, with no duplicated logic to drift out of sync.

    Existing *described* projects (no GitHub URL) are preserved up to
    whatever room is left under the cap; existing *repository* projects not
    in `selected_full_names` are dropped, matching "repo selection" being a
    replace, not an append, operation for that project kind.
    """
    existing = _active_projects(db, profile.id)
    described = [p for p in existing if p.kind is not ProjectKind.REPOSITORY]

    selected = selected_full_names[: schemas.MAX_PROJECTS]
    remaining_slots = max(0, schemas.MAX_PROJECTS - len(selected))

    items: list[schemas.ProjectItem] = [
        # `technologies` is not carried across: `ProjectItem` no longer accepts
        # it, and the stored value on a described project is worker-owned
        # anyway. `replace_projects` preserves the existing row's detected
        # technologies rather than reading them from this item.
        schemas.ProjectItem(
            kind=ProjectKind.DESCRIBED,
            title=p.title,
            description=p.description,
        )
        for p in described[:remaining_slots]
    ]
    for full_name in selected:
        repo_name = full_name.rsplit("/", 1)[-1]
        items.append(
            schemas.ProjectItem(
                kind=ProjectKind.REPOSITORY,
                title=repo_name,
                repo_url=f"https://github.com/{full_name}",
            )
        )

    return replace_projects(db, profile, schemas.ProjectsRequest(projects=items))


# --------------------------------------------------------------------------
# Section 4 — Certificates & Achievements
# --------------------------------------------------------------------------


def _certificate_key(credential_url: str | None, title: str, issuer: str) -> tuple[str, str]:
    if credential_url:
        return ("url", credential_url.casefold())
    return ("title", f"{title.casefold()}|{issuer.casefold()}")


def _apply_certificate_file(
    profile: CandidateProfile, certificate: Certificate, item: schemas.CertificateItem
) -> None:
    """Attach, detach, or leave alone the uploaded copy of a certificate.

    Three cases, and the third is the one worth naming: an item that carries
    **no** key is not a request to remove the file. The response never returns
    the object key (`CertificateResponse`), so an ordinary re-save of an
    untouched certificate always arrives without one — treating that as a
    delete would wipe the attachment every time the student edited a title.
    Removal is therefore the explicit `remove_file` flag.

    The prefix check is authorization, not validation: keys are handed out by
    `certificate_files.build_key`, which namespaces them per profile, so a key
    belonging to another candidate is refused even though it names a real
    object. Without this, one guessed key would attach someone else's document
    to this profile.
    """
    from src.domains.student import certificate_files

    if item.remove_file:
        certificate.file_object_key = None
        certificate.file_name = None
        certificate.file_content_type = None
        certificate.file_size_bytes = None
        return

    if item.file_object_key is None:
        return

    if not certificate_files.owns_key(profile.id, item.file_object_key):
        raise Forbidden("That uploaded file does not belong to this profile")

    certificate.file_object_key = item.file_object_key
    certificate.file_name = item.file_name
    certificate.file_content_type = item.file_content_type
    certificate.file_size_bytes = item.file_size_bytes


def replace_certificates(
    db: Session, profile: CandidateProfile, payload: schemas.CertificatesRequest
) -> ProfileCompleteness:
    existing = _active_certificates(db, profile.id)
    existing_by_key = {
        _certificate_key(certificate.credential_url, certificate.title, certificate.issuer): certificate
        for certificate in existing
    }
    seen_keys: set[tuple[str, str]] = set()
    queued: list[evidence.QueuedVerification | None] = []

    for position, item in enumerate(payload.certificates):
        key = _certificate_key(item.credential_url, item.title, item.issuer)
        seen_keys.add(key)
        current = existing_by_key.get(key)

        if current is not None:
            current.title = item.title
            current.issuer = item.issuer
            current.issued_at = item.issued_at
            _apply_certificate_file(profile, current, item)
            current.position = position
            continue

        certificate = Certificate(
            candidate_profile_id=profile.id,
            title=item.title,
            issuer=item.issuer,
            issued_at=item.issued_at,
            credential_url=item.credential_url,
            position=position,
            verification_status=VerificationStatus.UNVERIFIED,
        )
        _apply_certificate_file(profile, certificate, item)
        db.add(certificate)
        db.flush()
        queued.append(evidence.queue_certificate(db, certificate))

    for key, certificate in existing_by_key.items():
        if key not in seen_keys:
            certificate.deleted_at = _utcnow()

    return _finalize(db, profile, queued)


# --------------------------------------------------------------------------
# Section 5 — Experience
# --------------------------------------------------------------------------


def replace_experiences(
    db: Session, profile: CandidateProfile, payload: schemas.ExperiencesRequest
) -> ProfileCompleteness:
    """Rows are matched by natural key for the same reconciliation reason as
    every other section — avoid accumulating soft-deleted churn on every save
    — and, since `verification_status` was added to this table, to preserve
    it across an edit exactly like `replace_projects`/`replace_certificates`
    do: only a genuinely new entry is queued for verification."""
    existing = _active_experiences(db, profile.id)
    existing_by_key = {
        (exp.company_name.casefold(), exp.title.casefold(), exp.start_date): exp for exp in existing
    }
    seen_keys: set[tuple[str, str, object]] = set()
    queued: list[evidence.QueuedVerification | None] = []

    for position, item in enumerate(payload.experiences):
        key = (item.company_name.casefold(), item.title.casefold(), item.start_date)
        seen_keys.add(key)
        current = existing_by_key.get(key)

        if current is not None:
            current.employment_type = item.employment_type
            current.end_date = item.end_date
            current.description = item.description
            current.technologies = item.technologies
            current.position = position
            continue

        experience = Experience(
            candidate_profile_id=profile.id,
            company_name=item.company_name,
            title=item.title,
            employment_type=item.employment_type,
            start_date=item.start_date,
            end_date=item.end_date,
            description=item.description,
            technologies=item.technologies,
            position=position,
            verification_status=VerificationStatus.UNVERIFIED,
        )
        db.add(experience)
        db.flush()
        queued.append(evidence.queue_experience(db, experience))

    for key, experience in existing_by_key.items():
        if key not in seen_keys:
            experience.deleted_at = _utcnow()

    return _finalize(db, profile, queued)
