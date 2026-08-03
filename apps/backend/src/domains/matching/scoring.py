"""The rank-fusion formula — one computation, read by both the recruiter's
matched-candidates list and the student's job feed (`domains/matching/service.py`).

    semantic_score      = 1 - cosine_distance(job_vector, candidate_vector)   # 0-1
    profile_strength_n  = candidate.profile_strength / 100                    # 0-1
    evidence_score      = mean(candidate_skills.evidence_weight
                                for skills the job requires)                  # 0-1, 0 if none matched

    match_score = 100 * (MATCH_WEIGHTS["semantic"] * semantic_score
                          + MATCH_WEIGHTS["evidence"] * evidence_score
                          + MATCH_WEIGHTS["profile_strength"] * profile_strength_n)

Weighted toward semantic similarity (title/description/skills-blob match)
because that is what actually captures role fit; evidence backs up *that
the candidate's claimed skills are real*, and profile strength is a mild
completeness tiebreaker — a thin profile should rank lower even at equal
semantic similarity, but should never dominate the score the way semantic
fit does.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: The rank-fusion weights, in one place. Previously three separate module
#: constants, which made "what is the formula" a question you answered by
#: grepping rather than by reading one value. Must sum to 1.0 —
#: `compute_match_score` produces a 0-100 score on that assumption.
MATCH_WEIGHTS: dict[str, float] = {
    "semantic": 0.50,
    "evidence": 0.30,
    "profile_strength": 0.20,
}

assert abs(sum(MATCH_WEIGHTS.values()) - 1.0) < 1e-9, "MATCH_WEIGHTS must sum to 1.0"

# Below this, a pair is not a match at all — absent from `match_results`,
# not merely low-ranked. 0-100 scale, same as `match_score`.
MATCH_THRESHOLD = 50.0

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


def compute_match_score(*, semantic_score: float, evidence_score: float, profile_strength: int) -> float:
    profile_strength_n = max(0.0, min(1.0, profile_strength / 100.0))
    return round(
        100
        * (
            MATCH_WEIGHTS["semantic"] * semantic_score
            + MATCH_WEIGHTS["evidence"] * evidence_score
            + MATCH_WEIGHTS["profile_strength"] * profile_strength_n
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
