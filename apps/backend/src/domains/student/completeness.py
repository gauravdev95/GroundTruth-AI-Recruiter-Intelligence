"""Server-side profile completeness and discoverability.

This module is the single authority for `profile_strength` and
`is_discoverable`. Both are derived **only** from persisted rows — never
from a request body — and are recomputed on every section save. No request
schema in `schemas.py` declares either field, and `extra="forbid"` turns an
attempt to supply one into a 422.

Scoring (totals 100):

| Section            | Points | Rule                                      |
|--------------------|--------|-------------------------------------------|
| 1 Basic (required) | 35     | 5 per field x 7 fields                    |
| 2 Technical (req.) | 30     | GitHub 15 + at least one CP profile 15    |
| 3 Projects         | 15     | 5 per project, capped at 3                |
| 4 Certificates     | 10     | 5 per certificate, capped at 2            |
| 5 Experience       | 10     | 5 per entry, capped at 2                  |

Discoverability has two levels, and they are deliberately distinct:

* `meets_section_requirements` — sections 1 and 2 are both complete. This is
  what the student controls, and what the UI reports as blocking. Optional
  sections raise strength but never gate it.
* `is_discoverable` — the above **and** a profile vector exists in
  `embeddings`. This is what the matching pre-filter reads, because a profile
  with no vector cannot be scored against a job at all.

Keeping them separate is load-bearing, not cosmetic: embedding is enqueued
only for profiles that meet the section requirements, so folding the vector
check into that same flag would mean no profile is ever embedded and none ever
becomes discoverable. The gap between the two is the window in which the
embedding worker runs, and the UI reports it as "indexing" rather than as a
missing requirement the student could act on.

Strength measures what is **filled**, not what is **verified**. Verification
state is reported alongside it but contributes zero points, so a student's
score cannot silently drop when a Phase II worker rejects a claim, and the
UI's "filled" and "verified" badges stay independent.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domains.auth.models import CandidateProfile, OnboardingChoice
from src.domains.student.models import (
    Certificate,
    CodingPlatformAccount,
    Experience,
    GithubAccount,
    Project,
    VerificationStatus,
)

SECTION_BASIC = "basic"
SECTION_TECHNICAL = "technical"
SECTION_PROJECTS = "projects"
SECTION_CERTIFICATES = "certificates"
SECTION_EXPERIENCE = "experience"

BASIC_POINTS = 35
TECHNICAL_POINTS = 30
PROJECTS_POINTS = 15
CERTIFICATES_POINTS = 10
EXPERIENCE_POINTS = 10

MAX_STRENGTH = BASIC_POINTS + TECHNICAL_POINTS + PROJECTS_POINTS + CERTIFICATES_POINTS + EXPERIENCE_POINTS

_BASIC_FIELDS: tuple[str, ...] = (
    "headline",
    "college",
    "degree",
    "branch",
    "graduation_year",
    "location",
    "target_role",
)
_POINTS_PER_BASIC_FIELD = BASIC_POINTS // len(_BASIC_FIELDS)  # 5
_GITHUB_POINTS = TECHNICAL_POINTS // 2  # 15
_CODING_PROFILE_POINTS = TECHNICAL_POINTS - _GITHUB_POINTS  # 15

_POINTS_PER_PROJECT = 5
_COUNTED_PROJECTS = PROJECTS_POINTS // _POINTS_PER_PROJECT  # 3
_POINTS_PER_CERTIFICATE = 5
_COUNTED_CERTIFICATES = CERTIFICATES_POINTS // _POINTS_PER_CERTIFICATE  # 2
_POINTS_PER_EXPERIENCE = 5
_COUNTED_EXPERIENCES = EXPERIENCE_POINTS // _POINTS_PER_EXPERIENCE  # 2

# Human-readable labels for the discoverability banner.
_BASIC_FIELD_LABELS = {
    "headline": "a headline",
    "college": "your college",
    "degree": "your degree",
    "branch": "your branch",
    "graduation_year": "your graduation year",
    "location": "your location",
    "target_role": "a target role",
}


@dataclass(frozen=True)
class SectionScore:
    key: str
    is_mandatory: bool
    points_earned: int
    points_possible: int
    filled_count: int
    required_count: int
    missing: tuple[str, ...]
    verification: VerificationStatus | None

    @property
    def is_complete(self) -> bool:
        """Complete = every requirement met. For optional sections, always true."""
        return not self.missing

    @property
    def is_filled(self) -> bool:
        """Filled = the student has entered something here at all."""
        return self.filled_count > 0


@dataclass(frozen=True)
class ProfileCompleteness:
    profile_strength: int
    # Sections 1 and 2 are both complete. This is *eligibility* — the student
    # has done everything asked of them — and it is deliberately not the same
    # as `is_discoverable`, which additionally requires the profile vector to
    # exist. The two must stay separate or the system deadlocks: embedding is
    # only enqueued for eligible profiles, so if eligibility itself required an
    # embedding, nothing would ever be embedded and nobody would ever become
    # discoverable.
    meets_section_requirements: bool
    # Eligible *and* embedded. Only these profiles enter the match computation
    # (`matching/service.py::_prefiltered_candidate_ids`) — a profile with no
    # vector cannot be scored against a job, so advertising it as discoverable
    # would promise a match that cannot be computed.
    is_discoverable: bool
    sections: tuple[SectionScore, ...]
    blocking: tuple[str, ...]
    # Not derived from section data — read straight off the profile row and
    # carried here because every caller that needs it (the onboarding gate) is
    # already fetching completeness, and a second round trip to learn whether
    # to show one screen would be the only request on that path.
    onboarding_choice: OnboardingChoice | None


@dataclass(frozen=True)
class ProfileSnapshot:
    """Everything the calculation reads. Assembled once per save by the service."""

    profile: CandidateProfile
    github_account: GithubAccount | None
    coding_profiles: tuple[CodingPlatformAccount, ...]
    projects: tuple[Project, ...]
    certificates: tuple[Certificate, ...]
    experiences: tuple[Experience, ...]
    # Whether an `embeddings` row exists for this profile at the current model
    # version. Passed in rather than queried here so this module stays a pure
    # function of its snapshot — the same property that lets the whole scoring
    # table be unit-tested without a database.
    has_embedding: bool = False


def _rollup_verification(statuses: list[VerificationStatus]) -> VerificationStatus | None:
    """Collapse many claim statuses into the one the section badge shows.

    Precedence is worst-first among actionable states: anything still pending
    keeps the section pending, a rejection surfaces next, then a flag (weaker
    than a rejection — the claim is visible, just unconfirmed), and only an
    all-verified section reads as verified.
    """
    if not statuses:
        return None
    if any(status is VerificationStatus.PENDING for status in statuses):
        return VerificationStatus.PENDING
    if any(status is VerificationStatus.REJECTED for status in statuses):
        return VerificationStatus.REJECTED
    if any(status is VerificationStatus.FLAGGED for status in statuses):
        return VerificationStatus.FLAGGED
    if all(status is VerificationStatus.VERIFIED for status in statuses):
        return VerificationStatus.VERIFIED
    return VerificationStatus.UNVERIFIED


def _score_basic(profile: CandidateProfile) -> SectionScore:
    missing: list[str] = []
    filled = 0
    for field in _BASIC_FIELDS:
        value = getattr(profile, field, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(_BASIC_FIELD_LABELS[field])
        else:
            filled += 1

    return SectionScore(
        key=SECTION_BASIC,
        is_mandatory=True,
        points_earned=filled * _POINTS_PER_BASIC_FIELD,
        points_possible=BASIC_POINTS,
        filled_count=filled,
        required_count=len(_BASIC_FIELDS),
        missing=tuple(missing),
        verification=None,
    )


def _score_technical(snapshot: ProfileSnapshot) -> SectionScore:
    has_github = snapshot.github_account is not None
    coding_count = len(snapshot.coding_profiles)

    missing: list[str] = []
    if not has_github:
        missing.append("your GitHub profile")
    if coding_count == 0:
        missing.append("at least one competitive programming profile")

    points = (_GITHUB_POINTS if has_github else 0) + (_CODING_PROFILE_POINTS if coding_count else 0)
    filled = int(has_github) + coding_count

    statuses = [account.verification_status for account in snapshot.coding_profiles]
    if snapshot.github_account is not None:
        statuses.append(snapshot.github_account.verification_status)

    return SectionScore(
        key=SECTION_TECHNICAL,
        is_mandatory=True,
        points_earned=points,
        points_possible=TECHNICAL_POINTS,
        filled_count=filled,
        # GitHub + one coding profile is the bar, regardless of how many
        # extra platforms are linked.
        required_count=2,
        missing=tuple(missing),
        verification=_rollup_verification(statuses),
    )


def _score_optional(
    *,
    key: str,
    count: int,
    points_per_item: int,
    counted_items: int,
    points_possible: int,
    statuses: list[VerificationStatus],
) -> SectionScore:
    return SectionScore(
        key=key,
        is_mandatory=False,
        points_earned=min(count, counted_items) * points_per_item,
        points_possible=points_possible,
        filled_count=count,
        required_count=0,
        # Optional sections are never "missing" anything — they cannot block
        # discoverability, so the banner must not list them as blockers.
        missing=(),
        verification=_rollup_verification(statuses),
    )


def compute_completeness(snapshot: ProfileSnapshot) -> ProfileCompleteness:
    """Derive strength, discoverability, and per-section state from stored rows."""
    basic = _score_basic(snapshot.profile)
    technical = _score_technical(snapshot)
    projects = _score_optional(
        key=SECTION_PROJECTS,
        count=len(snapshot.projects),
        points_per_item=_POINTS_PER_PROJECT,
        counted_items=_COUNTED_PROJECTS,
        points_possible=PROJECTS_POINTS,
        statuses=[project.verification_status for project in snapshot.projects],
    )
    certificates = _score_optional(
        key=SECTION_CERTIFICATES,
        count=len(snapshot.certificates),
        points_per_item=_POINTS_PER_CERTIFICATE,
        counted_items=_COUNTED_CERTIFICATES,
        points_possible=CERTIFICATES_POINTS,
        statuses=[certificate.verification_status for certificate in snapshot.certificates],
    )
    experience = _score_optional(
        key=SECTION_EXPERIENCE,
        count=len(snapshot.experiences),
        points_per_item=_POINTS_PER_EXPERIENCE,
        counted_items=_COUNTED_EXPERIENCES,
        points_possible=EXPERIENCE_POINTS,
        # Self-reported with no independent source of truth, so
        # `verify_experience_task` can only ever leave a row `UNVERIFIED` or
        # move it to `FLAGGED` — never `VERIFIED`. Still rolled up like every
        # other section so the badge is consistent across all five.
        statuses=[exp.verification_status for exp in snapshot.experiences],
    )

    sections = (basic, technical, projects, certificates, experience)
    strength = sum(section.points_earned for section in sections)
    blocking = tuple(item for section in sections if section.is_mandatory for item in section.missing)

    meets_section_requirements = basic.is_complete and technical.is_complete

    return ProfileCompleteness(
        # Clamped defensively: the weights above already sum to 100, and this
        # keeps a future weight change from ever persisting an out-of-range value.
        profile_strength=max(0, min(strength, MAX_STRENGTH)),
        meets_section_requirements=meets_section_requirements,
        is_discoverable=meets_section_requirements and snapshot.has_embedding,
        sections=sections,
        blocking=blocking,
        onboarding_choice=snapshot.profile.onboarding_choice,
    )


def apply_completeness(profile: CandidateProfile, completeness: ProfileCompleteness) -> None:
    """Write the derived values onto the profile row. The only place they are set."""
    profile.profile_strength = completeness.profile_strength
    profile.is_discoverable = completeness.is_discoverable
