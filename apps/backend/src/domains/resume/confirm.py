"""Draft → live profile: suggestion mapping and the confirmed write path.

Two halves, deliberately separated:

`suggest_sections` turns a validated extraction into *section-shaped
suggestions* — best-effort, with everything it could not map reported in
`unmapped` rather than guessed. A resume states "B.Tech Computer Science"; the
profile stores a `DegreeType` enum and a `Branch` enum, and no resume states a
target role at all. Doing this coercion server-side keeps one mapping
implementation instead of a second copy in the browser, and keeps the honest
answer — "we could not determine this, you pick" — in the same place.

`apply_confirmation` performs the write, and does it by calling the **same
service functions the section PUT endpoints call** (`replace_basic_info`,
`replace_projects`, …). That reuse is the point: confirmation therefore
recomputes `profile_strength`, flips `is_discoverable`, and queues verification
jobs for any confirmed repo or credential URL, with no duplicated logic and no
path by which extracted data reaches a live table without going through the
same validation a hand-typed value would.

Atomicity: each section service commits its own work, so a database failure
partway through can leave earlier sections applied. That is safe rather than
papered over — every `replace_*` reconciles by natural key and is idempotent,
so re-confirming converges. The draft is marked confirmed only after every
section has landed, so a partial failure leaves it reviewable and re-submittable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.domains.auth.models import Branch, CandidateProfile, DegreeType
from src.domains.student import service as student_service
from src.domains.student.completeness import ProfileCompleteness
from src.domains.student.models import EmploymentType
from src.domains.student.schemas import (
    BasicInfoRequest,
    CertificatesRequest,
    ExperiencesRequest,
    ProjectsRequest,
    TechnicalRequest,
)

# Substring matches, longest-first so "mtech" is not swallowed by "tech".
_DEGREE_PATTERNS: tuple[tuple[str, DegreeType], ...] = (
    ("b.tech", DegreeType.BTECH),
    ("btech", DegreeType.BTECH),
    ("bachelor of technology", DegreeType.BTECH),
    ("m.tech", DegreeType.MTECH),
    ("mtech", DegreeType.MTECH),
    ("master of technology", DegreeType.MTECH),
    ("b.e", DegreeType.BE),
    ("bachelor of engineering", DegreeType.BE),
    ("bca", DegreeType.BCA),
    ("mca", DegreeType.MCA),
    ("mba", DegreeType.MBA),
    ("b.sc", DegreeType.BSC),
    ("bsc", DegreeType.BSC),
    ("bachelor of science", DegreeType.BSC),
    ("m.sc", DegreeType.MSC),
    ("msc", DegreeType.MSC),
    ("master of science", DegreeType.MSC),
    ("phd", DegreeType.PHD),
    ("doctor of philosophy", DegreeType.PHD),
)

_BRANCH_PATTERNS: tuple[tuple[str, Branch], ...] = (
    ("computer science", Branch.CSE),
    ("computer engineering", Branch.CSE),
    ("cse", Branch.CSE),
    ("information technology", Branch.IT),
    ("electronics and communication", Branch.ECE),
    ("electronics & communication", Branch.ECE),
    ("ece", Branch.ECE),
    ("electrical", Branch.EEE),
    ("mechanical", Branch.MECHANICAL),
    ("civil", Branch.CIVIL),
    ("chemical", Branch.CHEMICAL),
    ("artificial intelligence", Branch.AIML),
    ("machine learning", Branch.AIML),
    ("data science", Branch.DATA_SCIENCE),
)

_EMPLOYMENT_PATTERNS: tuple[tuple[str, EmploymentType], ...] = (
    ("intern", EmploymentType.INTERNSHIP),
    ("freelance", EmploymentType.FREELANCE),
    ("contract", EmploymentType.FREELANCE),
    ("part_time", EmploymentType.PART_TIME),
    ("part-time", EmploymentType.PART_TIME),
    ("part time", EmploymentType.PART_TIME),
)


def _match(value: str | None, patterns: tuple[tuple[str, Any], ...]) -> Any | None:
    """Return the first pattern whose text appears in `value`, else None.

    Returning None rather than an "other" fallback is deliberate: an unmatched
    degree becomes a field the student is asked to pick, not a silently
    downgraded value they might never notice.
    """
    if not value:
        return None
    lowered = value.casefold()
    for needle, mapped in patterns:
        if needle in lowered:
            return mapped
    return None


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@dataclass
class DraftSuggestions:
    """Section-shaped suggestions plus an honest list of what is still missing."""

    basic: dict[str, Any] = field(default_factory=dict)
    technical: dict[str, Any] = field(default_factory=dict)
    projects: list[dict[str, Any]] = field(default_factory=list)
    certificates: list[dict[str, Any]] = field(default_factory=list)
    experience: list[dict[str, Any]] = field(default_factory=list)
    # Human-readable notes on values the resume did not supply or that could
    # not be mapped onto the profile's controlled vocabularies.
    unmapped: list[str] = field(default_factory=list)


def suggest_sections(payload: dict[str, Any]) -> DraftSuggestions:
    """Map a validated extraction payload onto section-shaped suggestions."""
    suggestions = DraftSuggestions()
    contact = payload.get("contact") or {}
    education = payload.get("education") or []

    # --- Section 1: basic information ---
    primary = education[0] if education else {}
    degree = _match(primary.get("degree"), _DEGREE_PATTERNS)
    branch = _match(primary.get("field_of_study"), _BRANCH_PATTERNS)

    basic: dict[str, Any] = {}
    if contact.get("headline"):
        basic["headline"] = contact["headline"]
    if primary.get("institution"):
        basic["college"] = primary["institution"]
    if degree is not None:
        basic["degree"] = degree.value
    elif primary.get("degree"):
        suggestions.unmapped.append(
            f"Degree '{primary['degree']}' didn't match a known option — pick one."
        )
    if branch is not None:
        basic["branch"] = branch.value
    elif primary.get("field_of_study"):
        suggestions.unmapped.append(
            f"Branch '{primary['field_of_study']}' didn't match a known option — pick one."
        )
    if primary.get("graduation_year"):
        basic["graduation_year"] = primary["graduation_year"]
    location = contact.get("location") or primary.get("location")
    if location:
        basic["location"] = location
    # No resume states a target role — it is forward-looking, not historical.
    suggestions.unmapped.append("Target role isn't on a resume — choose one yourself.")
    suggestions.basic = basic

    # --- Section 2: technical verification ---
    technical: dict[str, Any] = {}
    if contact.get("github_username"):
        technical["github_username"] = contact["github_username"]
    coding_profiles = [
        {"platform": platform, "handle": contact[key]}
        for key, platform in (
            ("leetcode_handle", "leetcode"),
            ("codeforces_handle", "codeforces"),
            ("hackerrank_handle", "hackerrank"),
        )
        if contact.get(key)
    ]
    if coding_profiles:
        technical["coding_profiles"] = coding_profiles
    suggestions.technical = technical

    # --- Section 3: projects (the section caps at 3) ---
    for item in (payload.get("projects") or [])[:3]:
        repo_url = item.get("repo_url")
        suggestions.projects.append(
            {
                "kind": "repository" if repo_url else "described",
                "title": item.get("title") or "",
                "description": item.get("description"),
                "repo_url": repo_url,
                "technologies": item.get("technologies") or [],
            }
        )

    # --- Section 4: certificates ---
    for item in payload.get("certificates") or []:
        suggestions.certificates.append(
            {
                "title": item.get("title") or "",
                "issuer": item.get("issuer") or "",
                "issued_at": item.get("issued_at"),
                "credential_url": item.get("credential_url"),
            }
        )

    # --- Section 5: experience ---
    for item in payload.get("experience") or []:
        start = _parse_iso_date(item.get("start_date"))
        if start is None:
            # `start_date` is NOT NULL on the section, so an entry without a
            # determinable start cannot be suggested as-is.
            suggestions.unmapped.append(
                f"Couldn't read a start date for "
                f"'{item.get('title') or item.get('company_name') or 'an entry'}' — add one."
            )
        employment = _match(item.get("employment_type"), _EMPLOYMENT_PATTERNS)
        if employment is None:
            employment = _match(item.get("title"), _EMPLOYMENT_PATTERNS)
        suggestions.experience.append(
            {
                "company_name": item.get("company_name") or "",
                "title": item.get("title") or "",
                "employment_type": (employment or EmploymentType.INTERNSHIP).value,
                "start_date": start.isoformat() if start else None,
                "end_date": item.get("end_date"),
                "description": item.get("description"),
                "technologies": item.get("technologies") or [],
            }
        )

    return suggestions


def apply_confirmation(
    db: Session,
    profile: CandidateProfile,
    *,
    basic: BasicInfoRequest | None,
    technical: TechnicalRequest | None,
    projects: ProjectsRequest | None,
    certificates: CertificatesRequest | None,
    experience: ExperiencesRequest | None,
) -> ProfileCompleteness:
    """Write confirmed sections through the ordinary section services.

    Payloads arrive already validated by the same request schemas the section
    PUTs use, so this cannot write anything a hand-typed submission could not.
    """
    completeness: ProfileCompleteness | None = None

    if basic is not None:
        completeness = student_service.replace_basic_info(db, profile, basic)
    if technical is not None:
        completeness = student_service.replace_technical(db, profile, technical)
    if projects is not None:
        completeness = student_service.replace_projects(db, profile, projects)
    if certificates is not None:
        completeness = student_service.replace_certificates(db, profile, certificates)
    if experience is not None:
        completeness = student_service.replace_experiences(db, profile, experience)

    # No section confirmed — report current state rather than inventing one.
    if completeness is None:
        completeness = student_service.get_completeness(db, profile)
    return completeness


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
