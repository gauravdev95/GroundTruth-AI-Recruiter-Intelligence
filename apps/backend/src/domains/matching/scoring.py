"""The rank-fusion formula — one computation, read by both the recruiter's
matched-candidates list and the student's job feed (`domains/matching/service.py`).

    semantic_score      = 1 - cosine_distance(job_vector, candidate_vector)   # 0-1
    skill_evidence      = mean(candidate_skills.evidence_weight
                                for skills the job requires)                  # 0-1, 0 if none matched
    interview_score     = candidate.interview_score / 100                     # 0-1, 0 if no interview
    competency_score    = mean(evidence_weight for verified coding-profile
                                competencies the job requires)                # 0-1
    profile_strength_n  = candidate.profile_strength / 100                    # 0-1

    match_score = 100 * sum(weight[term] * term_value for each of the five)

Every weight and the threshold come from `MatchingSettings` (env
`MATCH_WEIGHT_*`, `MATCH_THRESHOLD`), validated at load time to sum to 1.0 —
see `config.py::_validate_weight_set` for why that check has to happen at
process start rather than here.

The formula is deliberately weighted toward semantic similarity because that is
what captures role fit; the three evidence terms establish that the fit is
*real*; profile strength is a mild completeness tiebreaker that should never
dominate. Nothing in this module reads a self-declared skill: every term traces
to either a vector, a verified claim, or a completed interview.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config.config import get_matching_settings

# Settings are read through these functions, never captured at module import:
# a module-level `MATCH_WEIGHTS = get_matching_settings().weights` would freeze
# the values into whichever process imported first, and `get_matching_settings`
# is `lru_cache`d, so a test overriding the settings could never take effect.


def get_match_weights() -> dict[str, float]:
    """The five rank-fusion weights. Guaranteed to sum to 1.0 — invalid sets
    raise at settings-load time, so no caller has to re-check."""
    return get_matching_settings().weights


def get_match_threshold() -> float:
    return get_matching_settings().match_threshold

#: How far the live `match_score` must move away from an application's frozen
#: `score_at_apply` before the recruiter board calls the difference *drift*
#: rather than noise. Same 0-100 scale as `match_score` itself, which is why
#: it lives here next to the formula rather than in `domains/pipeline/`.
#:
#: 5.0 points, because that is the smallest movement this system can honestly
#: claim means something:
#:
#: * `match_score` is stored `Numeric(5,2)` and rendered as a whole number
#:   everywhere a human sees it, so anything under a point is invisible and
#:   anything under a few points cannot change how two candidates compare on
#:   screen.
#: * A recompute re-runs the embedding call, and two embeddings of
#:   semantically-unchanged text are not bit-identical. The semantic term
#:   carries `MATCH_WEIGHTS["semantic"]` (0.5) of a 0-1 similarity, so
#:   sub-1%-similarity wobble alone moves the score by up to ~0.5 points with
#:   nothing about the candidate having changed. 5.0 sits an order of
#:   magnitude above that floor.
#: * Every drift a recruiter *should* act on clears it comfortably: a newly
#:   verified repository that satisfies one of four required skills moves the
#:   evidence term by 0.25 → 7.5 points; completing a profile section that
#:   raises `profile_strength` by 25 moves the strength term by 5.0 points.
#:
#: Deliberately symmetric — a score that fell 6 points and one that rose 6
#: points are equally worth surfacing, for opposite reasons.
MEANINGFUL_DRIFT_POINTS = 5.0

#: Hard cap on how many rows one recompute may write for one side of the pair.
#: A single constant for both directions: it bounds the *write*, and the two
#: directions are the same computation, so there is no reason for a job to
#: persist a different number of pairs than a candidate does.
#:
#: This is a write-side safety limit, not a display limit — it exists so a
#: recompute can never write one row per student in the system. Read paths
#: paginate over whatever is persisted; they no longer re-apply a `LIMIT` of
#: their own, which used to silently hide rows that had been written.
TOP_K = 200


def compute_evidence_score(
    *, required_skill_names: set[str], candidate_skill_weights: dict[str, float]
) -> float:
    """Mean `evidence_weight` (`candidate_skills`) across the job's required
    skills the candidate actually has evidence for. A required skill the
    candidate has no evidence for contributes 0, not "excluded from the
    average" — a candidate matching 1 of 5 must-haves should score lower
    than one matching 4 of 5, which excluding zeros would hide.
    """
    if not required_skill_names:
        return 0.0
    total = sum(candidate_skill_weights.get(name.casefold(), 0.0) for name in required_skill_names)
    return round(total / len(required_skill_names), 5)


def compute_competency_score(
    *, required_skill_names: set[str], competency_weights: dict[str, float]
) -> float:
    """Coding-profile competencies (`Data Structures & Algorithms`,
    `Problem Solving`) the job actually asks for.

    Scored only against *required* skills, like `compute_evidence_score`, and
    returns 0.0 when the job requires no competency at all — a backend role
    that never mentions algorithms should not rank a Codeforces specialist
    above a candidate whose evidence matches the actual requirements.
    """
    if not required_skill_names:
        return 0.0
    matched = [
        competency_weights[name.casefold()]
        for name in required_skill_names
        if name.casefold() in competency_weights
    ]
    if not matched:
        return 0.0
    # Mean over *matched* competencies, not over all required skills: unlike
    # `compute_evidence_score`, a job requiring five skills of which one is a
    # competency should not dilute that competency's weight by four skills it
    # was never meant to cover.
    return round(sum(matched) / len(matched), 5)


def compute_match_score(
    *,
    semantic_score: float,
    evidence_score: float,
    profile_strength: int,
    interview_score: float | None = None,
    competency_score: float = 0.0,
) -> float:
    """Rank fusion over the five configured terms, on a 0-100 scale.

    `interview_score` is the candidate's aggregate across completed interviews
    (0-100), or None when they have not completed one. None contributes 0
    rather than being excluded from the weighting: a candidate without an
    interview genuinely has less evidence than one with a poor interview, and
    renormalising the remaining weights would hide that by scoring them as
    though the term did not apply.

    `interview_score` and `competency_score` default so that a caller with only
    the original three terms still produces a valid score — the two read paths
    in `service.py` supply all five.
    """
    weights = get_match_weights()
    profile_strength_n = max(0.0, min(1.0, profile_strength / 100.0))
    interview_n = max(0.0, min(1.0, (interview_score or 0.0) / 100.0))

    return round(
        100
        * (
            weights["semantic"] * semantic_score
            + weights["skill_evidence"] * evidence_score
            + weights["interview"] * interview_n
            + weights["competency"] * max(0.0, min(1.0, competency_score))
            + weights["profile_strength"] * profile_strength_n
        ),
        2,
    )


@dataclass(frozen=True)
class SkillMatchReason:
    skill_name: str
    is_required: bool
    candidate_proficiency: str | None
    evidence_weight: float | None
    # A source trail into the concrete evidence — e.g. the verified project
    # or certificate that backs this skill — so a reason is always
    # traceable, never LLM-narrated after the fact (task constraint).
    evidence_sources: list[dict] = field(default_factory=list)
