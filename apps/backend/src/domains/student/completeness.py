"""Server-side profile completeness and discoverability.

This module is the single authority for `profile_strength` and
`is_discoverable`. Both are derived **only** from persisted rows — never
from a request body — and are recomputed on every section save. No request
schema in `schemas.py` declares either field, and `extra="forbid"` turns an
attempt to supply one into a 422.

Scoring (totals 100):

| Section              | Points | Rule                                    |
|----------------------|--------|-----------------------------------------|
| 1 Basic (required)   | 35     | 5 per field x 7 fields                  |
| 2 GitHub (required)  | 15     | a connected/claimed GitHub account      |
| 3 Projects (required)| 20     | 10 for the first, +5 each for 2 more    |
| 4 Coding profiles    | 10     | 5 per profile, capped at 2              |
| 5 Certificates       | 10     | 5 per certificate, capped at 2          |
| 6 Experience         | 10     | 5 per entry, capped at 2                |

**GitHub and coding profiles are two sections, not one.** They were a single
`technical` section scored 15 + 15, which made a competitive-programming
handle mandatory to finish onboarding. That is the wrong bar: a Codeforces
rating is a supporting signal that this platform explicitly refuses to treat
as a verified skill, so requiring one to submit a profile gated the entire
product on a number it does not believe. GitHub is the input the evidence
pipeline actually runs on, so it carries the mandatory half alone.

**Projects became mandatory (>= 1).** Every downstream artefact — repository
verification, the code-grounded interview, the evidence report — begins with a
linked repository. A profile with none reaches the dashboard and can never
become discoverable through the repository path, so accepting it at submit
time was accepting a profile the pipeline cannot act on. The first project is
worth double (10 of the 20) because it is the one that changes what the
platform can do; the second and third only add breadth.

Discoverability now has three levels, and they are deliberately distinct:

* `meets_section_requirements` — basic, GitHub and projects are all complete. This is
  what the student controls directly, and what the UI reports as blocking.
  Optional sections raise strength but never gate it.
* `is_indexed` — the above **and** a profile vector exists in `embeddings`.
  A profile with no vector cannot be scored against a job at all.
* `is_discoverable` — the above **and** a completed AI interview exists.
  This is what the matching pre-filter reads.

Keeping them separate is load-bearing, not cosmetic. Each stage gates the
enqueueing of the next: embedding is enqueued only for profiles that meet the
section requirements, and the interview is only invited once verification has
settled. Folding any later check into an earlier flag deadlocks the whole
chain — nothing would ever be embedded, so nothing would ever be interviewed,
so nobody would ever become discoverable. The gaps between the three are the
windows in which the workers run, and the UI reports them as progress rather
than as requirements the student has failed to meet.

**The interview gate has an escape hatch, and it is mandatory.** A repository
interview requires a `VERIFIED` repository. A candidate with none — no public
code, or a GitHub outage that degraded every check to `UNVERIFIED` — would be
permanently undiscoverable with no action available to them. The profile
interview (`domains/interview/`, `grounding=PROFILE`) exists for exactly that
case, and `jobs/tasks/verification.py` invites it once verification settles.

Three numbers, not one:

* `profile_strength` measures what is **filled**, not what is verified. It
  still contributes zero points for verification state, so a student's
  completeness cannot silently drop when a worker rejects a claim.
* `evidence_score` measures how strong the **verified** evidence is. This one
  *can* fall when a claim is rejected — that is its job.
* `interview_score` is the aggregate across completed interviews.

Collapsing them into a single "strength" would make each unanswerable: a
complete profile built on weak evidence and a sparse profile built on strong
evidence would produce the same number.
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
SECTION_GITHUB = "github"
SECTION_PROJECTS = "projects"
SECTION_CODING = "coding"
SECTION_CERTIFICATES = "certificates"
SECTION_EXPERIENCE = "experience"

BASIC_POINTS = 35
GITHUB_POINTS = 15
PROJECTS_POINTS = 20
CODING_POINTS = 10
CERTIFICATES_POINTS = 10
EXPERIENCE_POINTS = 10

MAX_STRENGTH = (
    BASIC_POINTS + GITHUB_POINTS + PROJECTS_POINTS + CODING_POINTS + CERTIFICATES_POINTS + EXPERIENCE_POINTS
)

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

#: The first project is worth double the others. It is the one that makes the
#: evidence pipeline able to run at all; projects two and three add breadth to
#: a profile that already works.
_POINTS_FIRST_PROJECT = 10
_POINTS_PER_EXTRA_PROJECT = 5
_COUNTED_EXTRA_PROJECTS = (PROJECTS_POINTS - _POINTS_FIRST_PROJECT) // _POINTS_PER_EXTRA_PROJECT  # 2

_POINTS_PER_CODING_PROFILE = 5
_COUNTED_CODING_PROFILES = CODING_POINTS // _POINTS_PER_CODING_PROFILE  # 2
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
    # Mean verification confidence across verified claims, 0-100. Unlike
    # strength, this *falls* when a claim is rejected — that is the point.
    evidence_score: int
    # Aggregate across completed interviews, or None if there are none. None
    # and 0.0 are different facts and must not be conflated: the gate reads
    # presence, the match score reads value.
    interview_score: float | None
    # Basic, GitHub and projects are all complete. This is *eligibility* — the student
    # has done everything asked of them — and is deliberately not the same as
    # `is_discoverable`. See the module docstring for why collapsing the
    # stages deadlocks the pipeline.
    meets_section_requirements: bool
    # Eligible *and* embedded. The window between this and `is_discoverable`
    # is where verification and the interview happen; the UI reports it as
    # progress, not as something the student has failed to do.
    is_indexed: bool
    # Eligible, embedded, **and** interviewed. Only these profiles enter the
    # match computation (`matching/service.py::_prefiltered_candidate_ids`).
    is_discoverable: bool
    # Whether a completed interview exists at all. Surfaced separately from
    # `interview_score` so the UI can distinguish "not interviewed yet" from
    # "interviewed and scored poorly" — the first is an action the student can
    # take, the second is not.
    has_completed_interview: bool
    sections: tuple[SectionScore, ...]
    blocking: tuple[str, ...]
    # Not derived from section data — read straight off the profile row and
    # carried here because every caller that needs it (the onboarding gate) is
    # already fetching completeness, and a second round trip to learn whether
    # to show one screen would be the only request on that path.
    onboarding_choice: OnboardingChoice | None
    # Whether the student pressed "Submit Profile" on the final review step.
    # **This, not `meets_section_requirements`, is the dashboard gate.** The
    # two are deliberately both present: this one is an explicit act and never
    # moves on its own, while `meets_section_requirements` is derived and can
    # flip whenever a worker rewrites a row — which is precisely why gating on
    # it let students in and out of the dashboard without doing anything.
    is_onboarding_submitted: bool


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
    # Total scores of the candidate's COMPLETED interviews, 0-100 each. Empty
    # means no completed interview, which is what gates discoverability.
    # Passed in for the same purity reason as `has_embedding`.
    completed_interview_scores: tuple[float, ...] = ()


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


def _score_github(snapshot: ProfileSnapshot) -> SectionScore:
    """The mandatory half of what used to be `technical`.

    All 15 points ride on the account existing, not on it being verified —
    `profile_strength` measures what is filled everywhere else and must not
    become the one number that falls when a worker rejects a claim. The
    verification state travels separately, in `verification`.
    """
    has_github = snapshot.github_account is not None

    return SectionScore(
        key=SECTION_GITHUB,
        is_mandatory=True,
        points_earned=GITHUB_POINTS if has_github else 0,
        points_possible=GITHUB_POINTS,
        filled_count=int(has_github),
        required_count=1,
        missing=() if has_github else ("your GitHub account",),
        verification=_rollup_verification(
            [snapshot.github_account.verification_status] if snapshot.github_account else []
        ),
    )


def _score_projects(snapshot: ProfileSnapshot) -> SectionScore:
    """Mandatory, and the only optional-shaped section that became a gate.

    One project is the requirement; `required_count` is 1 rather than the
    three-project ceiling so the UI reports "1 of 1" for a student who linked
    one repository and is done, instead of showing them two-thirds of a bar
    they are under no obligation to fill.
    """
    count = len(snapshot.projects)
    extra = min(max(count - 1, 0), _COUNTED_EXTRA_PROJECTS)
    points = (_POINTS_FIRST_PROJECT + extra * _POINTS_PER_EXTRA_PROJECT) if count else 0

    return SectionScore(
        key=SECTION_PROJECTS,
        is_mandatory=True,
        points_earned=points,
        points_possible=PROJECTS_POINTS,
        filled_count=count,
        required_count=1,
        missing=() if count else ("at least one project",),
        verification=_rollup_verification([project.verification_status for project in snapshot.projects]),
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


def _compute_evidence_score(snapshot: ProfileSnapshot) -> int:
    """Mean `verification_score` across claims that reached a *verified* state.

    Only `VERIFIED` and `FLAGGED` rows count, and only those carrying a score:

    * `UNVERIFIED`/`PENDING` are excluded rather than scored 0. Nothing has
      been checked yet, and averaging in a zero would make a candidate mid-
      verification look worse than one whose claims were actively rejected —
      the opposite of the truth.
    * `REJECTED` **is** excluded too, but for the opposite reason: a rejected
      claim contributes no evidence, and including its near-zero score would
      let a candidate dilute a single bad claim by adding more claims. Instead
      it simply stops counting, so the mean reflects evidence that survived.

    A candidate with no scored claims gets 0 — not "unknown". They have no
    verified evidence, which is a fact about them, not missing data.
    """
    scores: list[float] = []

    def collect(rows) -> None:
        for row in rows:
            status = getattr(row, "verification_status", None)
            score = getattr(row, "verification_score", None)
            if status in (VerificationStatus.VERIFIED, VerificationStatus.FLAGGED) and score is not None:
                scores.append(float(score))

    if snapshot.github_account is not None:
        collect([snapshot.github_account])
    collect(snapshot.coding_profiles)
    collect(snapshot.projects)
    collect(snapshot.certificates)
    collect(snapshot.experiences)

    if not scores:
        return 0
    return int(round(max(0.0, min(100.0, sum(scores) / len(scores)))))


def _compute_interview_score(snapshot: ProfileSnapshot) -> float | None:
    """The candidate's aggregate across completed interviews, or None.

    `max`, not mean: a candidate who sat one weak interview and one strong one
    has demonstrated the stronger performance, and averaging would punish them
    for attempting a second repository. Attempts are never overwritten
    (`domains/interview/models.py`), so the history behind this number remains
    fully inspectable on the evidence card.
    """
    if not snapshot.completed_interview_scores:
        return None
    return round(max(snapshot.completed_interview_scores), 2)


def compute_completeness(snapshot: ProfileSnapshot) -> ProfileCompleteness:
    """Derive strength, evidence, interview state, discoverability, and
    per-section state from stored rows."""
    basic = _score_basic(snapshot.profile)
    github = _score_github(snapshot)
    projects = _score_projects(snapshot)
    coding = _score_optional(
        key=SECTION_CODING,
        count=len(snapshot.coding_profiles),
        points_per_item=_POINTS_PER_CODING_PROFILE,
        counted_items=_COUNTED_CODING_PROFILES,
        points_possible=CODING_POINTS,
        statuses=[account.verification_status for account in snapshot.coding_profiles],
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

    # Declared in flow order — basic, GitHub, projects, then the three optional
    # sections — so a client rendering `sections` in order gets the order the
    # student walked through them in.
    sections = (basic, github, projects, coding, certificates, experience)
    strength = sum(section.points_earned for section in sections)
    blocking = tuple(item for section in sections if section.is_mandatory for item in section.missing)

    meets_section_requirements = basic.is_complete and github.is_complete and projects.is_complete
    is_indexed = meets_section_requirements and snapshot.has_embedding
    has_completed_interview = bool(snapshot.completed_interview_scores)

    return ProfileCompleteness(
        # Clamped defensively: the weights above already sum to 100, and this
        # keeps a future weight change from ever persisting an out-of-range value.
        profile_strength=max(0, min(strength, MAX_STRENGTH)),
        evidence_score=_compute_evidence_score(snapshot),
        interview_score=_compute_interview_score(snapshot),
        meets_section_requirements=meets_section_requirements,
        is_indexed=is_indexed,
        # The full gate: complete, embedded, and interviewed. A candidate who
        # cannot produce a verified repository still reaches this via the
        # profile interview — see the module docstring on the escape hatch.
        is_discoverable=is_indexed and has_completed_interview,
        has_completed_interview=has_completed_interview,
        sections=sections,
        blocking=blocking,
        onboarding_choice=snapshot.profile.onboarding_choice,
        is_onboarding_submitted=snapshot.profile.onboarding_submitted_at is not None,
    )


def apply_completeness(profile: CandidateProfile, completeness: ProfileCompleteness) -> None:
    """Write the derived values onto the profile row. The only place they are set."""
    profile.profile_strength = completeness.profile_strength
    profile.evidence_score = completeness.evidence_score
    profile.interview_score = completeness.interview_score
    profile.is_discoverable = completeness.is_discoverable
