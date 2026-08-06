"""Per-field confidence — the reason this pipeline is deterministic at all.

THE ARGUMENT FOR REPLACING AN LLM WITH REGEX AND HEURISTICS

The product requirement is a review screen where every extracted field
carries a green ("high confidence") or amber ("needs review") badge, so a
student's attention goes to the three fields that are probably wrong rather
than to all forty. That requirement is what forces this module to exist,
and it is not satisfiable with an LLM alone:

* A model asked to self-report confidence produces a number correlated with
  its own fluency, not with correctness. It is most confident exactly where
  it hallucinates most fluently — a plausible-looking degree title read off
  a course name scores high.
* Log-probabilities are not exposed by structured-output modes on either
  provider in use, and would measure token likelihood rather than field
  correctness even if they were.
* Re-running the model to check itself doubles cost and correlates its own
  errors, so agreement means very little.

A deterministic pass, by contrast, knows *how* it found each value, and
"how" is a genuine evidence signal. An email matched by an unambiguous
regex is not the same kind of claim as an institution guessed from a line's
position under a heading, and this module is the place that difference is
made explicit and carried to the UI.

CONFIDENCE IS ABOUT PROVENANCE, NOT PROBABILITY

`Provenance` is deliberately an ordered enum of *methods*, not a float the
extractors invent. An extractor's job is to say how it found something; the
mapping from method to number lives here, once, so the review screen's
banding cannot drift between field types and so re-tuning a band is a
one-line change rather than an audit of nine extractors.

WHY `MODEL` SITS BELOW `STRUCTURAL`

The LLM only ever runs on fields the deterministic pass could not resolve
(`pipeline.py::extract_resume_hybrid`). Those are by definition the harder
cases — unusual layouts, prose-formatted experience, non-English section
headings. A value produced there is worth more than a positional guess and
less than a value corroborated by document structure, which is exactly
where `MODEL` is ordered. It is also the one provenance that is *always*
surfaced to the student as needing review regardless of its score, because
it is the only one that could have been invented rather than misread.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class Provenance(str, enum.Enum):
    """How a value was found. Ordered most to least trustworthy."""

    #: Matched a pattern that admits no other reading — an RFC-shaped email,
    #: a `github.com/<user>` URL, a four-digit year on a line labelled
    #: "Graduation". There is no plausible alternative interpretation.
    EXPLICIT = "explicit"

    #: Derived from document structure: the value sat under a recognised
    #: section heading, in a list whose siblings parsed the same way. The
    #: structure corroborates the reading.
    STRUCTURAL = "structural"

    #: Matched a known format without structural corroboration — a date range
    #: on an unlabelled line, a capitalised phrase that looks like a company.
    #: Probably right, cheaply wrong.
    PATTERN = "pattern"

    #: Came from the LLM fallback pass. Always surfaced for review; see the
    #: module docstring.
    MODEL = "model"

    #: A positional or shape heuristic with no corroboration — "the first
    #: non-contact line of the document is usually the headline". Useful
    #: enough to pre-fill, never good enough to trust.
    INFERRED = "inferred"


#: Provenance → base score. Tuned so that the `REVIEW_THRESHOLD` below falls
#: between STRUCTURAL and MODEL, which is the product decision this whole
#: module encodes: structure-corroborated readings are green, everything a
#: model or a heuristic produced is amber.
_BASE_SCORE: dict[Provenance, float] = {
    Provenance.EXPLICIT: 1.0,
    Provenance.STRUCTURAL: 0.86,
    Provenance.PATTERN: 0.7,
    Provenance.MODEL: 0.62,
    Provenance.INFERRED: 0.45,
}

#: At or above this, the review screen shows green; below it, amber.
#: 0.8 sits deliberately between STRUCTURAL (0.86) and PATTERN (0.7) — so an
#: unlabelled pattern match is something we ask the student to glance at, and
#: a structurally-corroborated one is not.
REVIEW_THRESHOLD = 0.8

#: Multiplier applied once per corroborating signal, capped by `_MAX_BOOST`.
#: Corroboration is real evidence — an institution name that also appears in
#: a known-institutions list, or a date range whose two ends are consistent —
#: but it must never promote an `INFERRED` guess into the green band on its
#: own, which is what the cap enforces (0.45 * 1.30 = 0.585, still amber).
_CORROBORATION_BOOST = 1.10
_MAX_BOOST = 1.30


@dataclass(frozen=True)
class Scored(Generic[T]):
    """One extracted value plus how it was found.

    Generic over the value type so an extractor returning `Scored[int]` for a
    graduation year and `Scored[str]` for an institution both flow through the
    same assembly code without casts.
    """

    value: T
    provenance: Provenance
    #: Human-readable note on *what* corroborated this, surfaced in the review
    #: screen's tooltip. "Found under an 'Education' heading" tells a student
    #: something actionable; a bare 0.86 does not.
    evidence: str = ""
    #: Independent signals that agreed with this reading.
    corroborations: int = 0

    @property
    def score(self) -> float:
        base = _BASE_SCORE[self.provenance]
        boost = min(_MAX_BOOST, _CORROBORATION_BOOST**self.corroborations)
        return round(min(1.0, base * boost), 4)

    @property
    def needs_review(self) -> bool:
        """`MODEL` is always reviewable regardless of score.

        A model value is the only provenance that could have been *invented*
        rather than misread, and the whole confirmation screen exists to stop
        an invention reaching a live profile. Letting corroboration boost a
        model value into green would reopen exactly that hole.
        """
        if self.provenance is Provenance.MODEL:
            return True
        return self.score < REVIEW_THRESHOLD

    @property
    def band(self) -> str:
        """The two-value band the UI renders. Not three: a third middle band
        would make the student triage the triage."""
        return "review" if self.needs_review else "high"

    def wire(self) -> dict[str, Any]:
        """The shape the review screen consumes."""
        return {
            "value": self.value,
            "confidence": self.score,
            "band": self.band,
            "provenance": self.provenance.value,
            "evidence": self.evidence,
        }


@dataclass
class FieldMap:
    """Accumulates `Scored` values for one entity, keyed by field name.

    Deliberately not a dict subclass: assembly code needs `set_if_better`,
    and inheriting `dict` would leave `__setitem__` as a way to bypass it.
    Several extractors legitimately produce the same field — a GitHub
    username can come from a labelled line, a bare URL, or the LLM — and
    "first writer wins" would make extractor ordering silently load-bearing.
    """

    fields: dict[str, Scored[Any]] = field(default_factory=dict)

    def set_if_better(self, name: str, candidate: Scored[Any] | None) -> None:
        """Keep the higher-scoring reading of a field.

        Ties go to the incumbent, which makes the result independent of
        extractor registration order for equal-confidence readings.
        """
        if candidate is None or candidate.value in (None, "", []):
            return
        existing = self.fields.get(name)
        if existing is None or candidate.score > existing.score:
            self.fields[name] = candidate

    def corroborate(self, name: str, evidence: str) -> None:
        """Record that an independent signal agreed with an existing reading.

        A no-op when the field is absent: corroboration is evidence *for* a
        value, so there is nothing to strengthen if nothing was read.
        """
        existing = self.fields.get(name)
        if existing is None:
            return
        self.fields[name] = Scored(
            value=existing.value,
            provenance=existing.provenance,
            evidence=f"{existing.evidence}; {evidence}" if existing.evidence else evidence,
            corroborations=existing.corroborations + 1,
        )

    def value(self, name: str, default: Any = None) -> Any:
        found = self.fields.get(name)
        return found.value if found is not None else default

    def missing(self, names: tuple[str, ...]) -> tuple[str, ...]:
        """Which of `names` have no value at all.

        Drives the LLM fallback's field list — the model is asked only about
        what the deterministic pass could not resolve, which is what keeps
        the fallback cheap and its output narrow enough to review.
        """
        return tuple(name for name in names if name not in self.fields)

    def low_confidence(self, names: tuple[str, ...]) -> tuple[str, ...]:
        """Which of `names` were read but land in the review band."""
        return tuple(
            name for name in names if name in self.fields and self.fields[name].needs_review
        )

    def wire(self) -> dict[str, Any]:
        return {name: scored.wire() for name, scored in self.fields.items()}


def aggregate_confidence(maps: list[FieldMap]) -> float:
    """Mean field confidence across a set of entities, 0-1.

    Used for the section-level badge on the review screen and for the
    `pipeline.py` decision on whether the LLM fallback is worth running at
    all. Unweighted on purpose: weighting by field importance would need an
    importance table that nothing else in the product has, and the number is
    a triage hint rather than an input to any score the student is judged on.

    An empty set scores 0.0, not 1.0. "Nothing was extracted" is the worst
    outcome this function can describe, and returning a perfect score for it
    would send the review screen's section badge green on an empty section.
    """
    scores = [scored.score for fmap in maps for scored in fmap.fields.values()]
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 4)
