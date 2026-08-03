"""Experience verification — "consolidated handling", per the task that added
this module.

There is no external source of truth for "worked at X as a Y" the way there
is a GitHub API for a repository or a Codeforces API for a handle. Rather
than fabricate a fake external verifier, this combines two weak *internal*
consistency signals the platform already has:

1. Is `company_name` a company already known to the platform
   (`companies.name`, case-insensitively)? A real, platform-known employer is
   mild positive evidence over an arbitrary free-text string.
2. Do the experience's claimed `technologies` overlap with the technologies
   the candidate has independently verified (via `verify_repository_task`,
   which writes into `candidate_skills`)? Claiming "Django" in an internship
   description is more credible from a candidate who also has a verified
   Django repository.

Because both signals are weak and internal, this can only ever reach
`FLAGGED` (visible, with the corroboration noted) or stay `UNVERIFIED` — it
never writes `VERIFIED`. See `Experience.verification_status`'s docstring.
"""

from __future__ import annotations

from dataclasses import dataclass

_COMPANY_KNOWN_WEIGHT = 0.5
_TECH_OVERLAP_WEIGHT = 0.5
FLAG_THRESHOLD = 0.25


@dataclass(frozen=True)
class ExperienceVerdict:
    status: str  # "flagged" | "unverified"
    score: float
    reason: str
    company_known: bool
    overlapping_technologies: list[str]


def score_experience(
    *,
    company_name: str,
    technologies: list[str],
    known_company_names: set[str],
    verified_technologies: set[str],
) -> ExperienceVerdict:
    company_known = company_name.strip().casefold() in {name.casefold() for name in known_company_names}

    claimed = {t.casefold(): t for t in technologies}
    overlap_keys = set(claimed) & {t.casefold() for t in verified_technologies}
    overlap_fraction = len(overlap_keys) / len(claimed) if claimed else 0.0

    score = (
        (_COMPANY_KNOWN_WEIGHT if company_known else 0.0)
        + _TECH_OVERLAP_WEIGHT * min(overlap_fraction, 1.0)
    )
    overlapping = [claimed[key] for key in overlap_keys]

    reasons = []
    if company_known:
        reasons.append(f"'{company_name}' matches a company already known to the platform.")
    if overlapping:
        reasons.append(
            f"{len(overlapping)} claimed technolog{'y' if len(overlapping) == 1 else 'ies'} "
            f"({', '.join(sorted(overlapping))}) overlap with the candidate's independently verified skills."
        )
    if not reasons:
        reasons.append(
            "No independent corroboration found — this is a self-reported claim with no "
            "external source of truth to check it against."
        )

    if score >= FLAG_THRESHOLD:
        return ExperienceVerdict(
            status="flagged",
            score=round(score * 100, 2),
            reason=" ".join(reasons),
            company_known=company_known,
            overlapping_technologies=overlapping,
        )
    return ExperienceVerdict(
        status="unverified",
        score=round(score * 100, 2),
        reason=" ".join(reasons),
        company_known=company_known,
        overlapping_technologies=overlapping,
    )
