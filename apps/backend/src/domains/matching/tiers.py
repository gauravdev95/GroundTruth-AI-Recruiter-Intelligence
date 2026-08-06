"""The two-tier output contract sitting on top of the rank-fusion score.

`scoring.py` answers "how well does this pair fit?" with one number. This
module answers the two questions the product actually asks of that number:

* **Tier A — Discoverable.** The pair is real enough to occupy a slot on the
  recruiter's board. Threshold-only.
* **Tier B — Smart Apply Recommended.** The pair is strong enough to be worth
  interrupting a student for — a push notification and an email, and a
  "High Match — Apply" prompt on their dashboard.

**Nothing here is persisted, and that is the design.** Every input is already
a column on `match_results` (`match_score`, `match_reasons`), so a stored
`tier` column would be a denormalisation whose only possible behaviour is to
disagree with the score it was derived from. Tier B in particular is defined
relative to *the rest of the job's pool*, which means it moves whenever any
other candidate for that job is rescored — a stored value would be stale the
moment a second candidate re-verified a repository, and there is no trigger
that could keep it fresh without recomputing the whole pool anyway. Deriving
it at the two call sites that need it (the notification fan-out in
`jobs/tasks/matching.py`, the read paths in `domains/pipeline/service.py` and
`domains/recruiter/router.py`) costs one pass over a list that is already in
memory.

**Tier A/B is internal vocabulary.** It never reaches a recruiter — their
board says "Matched" and "Applied", which is what those columns mean to
them. The tier drives *which students get interrupted*, not what a recruiter
reads. Only the student-facing surface names Tier B, and it names it as
"High Match", never as "Tier B".

**The reasoning string is derived, never narrated.** `build_reasoning` reads
the same stored `match_reasons` payload the recruiter's skill chips render
from, and composes one sentence out of it with string formatting. No LLM
call, at compute time or read time — the same constraint
`domains/matching/service.py::_build_match_reasons` follows, for the same
reason: a sentence a model wrote about evidence is not itself evidence, and a
recruiter cannot audit it against anything.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

#: Tier A floor. A pair below this does not appear on the recruiter's board
#: at all.
#:
#: Note this is *not* the same knob as `MATCH_THRESHOLD`
#: (`scoring.get_match_threshold`), which decides whether a `match_results`
#: row is written in the first place. That one is a storage/compute bound and
#: is configurable per deployment; this one is a product statement about what
#: is worth a recruiter's attention. They are deliberately separate: lowering
#: the storage threshold to widen the recompute pool should not silently
#: change what a recruiter sees. Where the configured threshold is already
#: above 50, that threshold wins by simple consequence — the row is not there
#: to be tiered.
TIER_A_MIN_SCORE = 50.0

#: Tier B's absolute floor. Cleared *and* the percentile test — whichever is
#: higher — before a student is interrupted.
TIER_B_MIN_SCORE = 70.0

#: Tier B's relative floor: the top 15% of this job's scored pool.
#:
#: The absolute floor alone is wrong at both ends. A job whose whole pool
#: scores 72-95 would push a notification to everyone, which trains students
#: to ignore them; a niche job whose best genuine match scores 68 would
#: notify nobody, which is the case the feature exists for. Taking the
#: *higher* of the two means a strong pool raises the bar and a weak pool
#: never lowers it below 70.
TIER_B_TOP_PERCENTILE = 0.15


class MatchTier(str, enum.Enum):
    """Internal only — see the module docstring. Serialised on the wire for
    the *student's* feed (which renders Tier B as a "High Match — Apply"
    prompt); the recruiter payloads carry the reasoning string and the score,
    never this."""

    #: Tier A. On the recruiter's board, discoverable, no student interrupt.
    DISCOVERABLE = "discoverable"
    #: Tier B. Everything Tier A is, plus push + email + the apply prompt.
    SMART_APPLY_RECOMMENDED = "smart_apply_recommended"


def tier_b_cutoff(pool_scores: Iterable[float]) -> float:
    """The score a pair in *this* pool must reach to be Tier B.

    `max(TIER_B_MIN_SCORE, the pool's top-15% cutoff)`.

    The percentile uses nearest-rank on the descending list rather than a
    linear interpolation: the cutoff has to be an achievable score held by an
    actual candidate, because "top 15%" is a statement about a set of people,
    not about a continuous distribution. `ceil` rather than `round` so a pool
    of 7 yields 1 slot rather than 0 — a job with a handful of candidates
    should still be able to recommend its best one.

    An empty pool returns the absolute floor, which is the only honest answer:
    with nothing to rank against, the relative test has no opinion.
    """
    scores = sorted((float(s) for s in pool_scores), reverse=True)
    if not scores:
        return TIER_B_MIN_SCORE

    slots = max(1, math.ceil(len(scores) * TIER_B_TOP_PERCENTILE))
    # `slots - 1` indexes the last candidate still inside the top 15%, so its
    # own score is the cutoff — a pair tying it is in, which is what "top 15
    # percent" means when scores repeat.
    percentile_cutoff = scores[min(slots, len(scores)) - 1]
    return max(TIER_B_MIN_SCORE, percentile_cutoff)


def resolve_tier(score: float, *, cutoff_b: float) -> MatchTier | None:
    """`None` means "below Tier A" — not an error, just a pair that has a
    stored row (it cleared `MATCH_THRESHOLD`) but is not strong enough to
    occupy a slot on a recruiter's board.

    `cutoff_b` is passed in rather than recomputed per pair: it is a property
    of the pool, and computing it inside a loop over that same pool would be
    quadratic *and* would let two pairs in one batch disagree about where the
    bar was.
    """
    if score >= cutoff_b:
        return MatchTier.SMART_APPLY_RECOMMENDED
    if score >= TIER_A_MIN_SCORE:
        return MatchTier.DISCOVERABLE
    return None


@dataclass(frozen=True)
class TieredMatch:
    """One pair, with everything a UI needs and nothing it would have to
    re-derive. `tier` is dropped before this reaches a recruiter."""

    match_score: float
    tier: MatchTier | None
    reasoning: str


def _skill_names(reasons: Sequence[Any]) -> list[str]:
    """Reads either shape `match_reasons` comes in.

    The column is JSONB, so a row written before the current writer may hold
    plain dicts while `_build_match_reasons` produces dicts too — but the
    ORM's `SkillMatchReason` dataclass (`scoring.py`) is also passed here by
    the compute-time call site, which has objects rather than rows. Handling
    both is what lets the notification path and the read path share one
    formatter instead of formatting the same sentence twice.
    """
    names: list[str] = []
    for reason in reasons:
        if isinstance(reason, dict):
            has_skill = reason.get("candidate_has_skill", False)
            name = reason.get("skill_name")
        else:
            has_skill = getattr(reason, "candidate_has_skill", None)
            if has_skill is None:
                # `scoring.SkillMatchReason` records evidence by weight rather
                # than by a boolean.
                has_skill = getattr(reason, "evidence_weight", None) is not None
            name = getattr(reason, "skill_name", None)
        if has_skill and isinstance(name, str) and name:
            names.append(name)
    return names


#: How many skills the sentence names before it stops. Three is what fits on
#: a Kanban card at 12px without wrapping to a third line, and the count that
#: follows ("3 of 5 must-haves verified") carries the rest — a recruiter
#: scanning a column needs the shape of the match, not its full inventory.
MAX_NAMED_SKILLS = 3


def build_reasoning(match_reasons: dict | None) -> str:
    """One sentence, composed from stored evidence. Never LLM-narrated.

    Shape in: `{"required": [...], "desirable": [...]}` — the
    `match_results.match_reasons` column verbatim.

    Shape out, by case:

    * some must-haves verified →
      ``"Matches on Rust, PostgreSQL, distributed systems — 3 of 3 must-have
      skills verified"``
    * no must-have verified but desirables are →
      ``"Matches on Docker, Redis — no must-have skills verified"``, which is
      deliberately blunt. A card that says only what it *does* match, on a
      candidate matching none of the requirements, reads as an endorsement.
    * nothing verified → ``"Semantic match only — no skill evidence"``. Also
      blunt, and also on purpose: the pair still cleared the score threshold
      (the semantic term carries half the weight), so the honest description
      is which term earned it.
    * the job has no requirements at all → ``"Semantic match — this job lists
      no required skills"``. Distinct from the case above because the absence
      is the *job's*, not the candidate's, and blaming the candidate's
      evidence for a requirement nobody wrote is a lie the recruiter would
      have no way to spot.
    """
    reasons = match_reasons or {}
    required = list(reasons.get("required") or [])
    desirable = list(reasons.get("desirable") or [])

    if not required and not desirable:
        return "Semantic match — this job lists no required skills"

    matched_required = _skill_names(required)
    if matched_required:
        named = ", ".join(matched_required[:MAX_NAMED_SKILLS])
        return f"Matches on {named} — {len(matched_required)} of {len(required)} must-have skills verified"

    matched_desirable = _skill_names(desirable)
    if matched_desirable:
        named = ", ".join(matched_desirable[:MAX_NAMED_SKILLS])
        return f"Matches on {named} — no must-have skills verified"

    return "Semantic match only — no skill evidence"
