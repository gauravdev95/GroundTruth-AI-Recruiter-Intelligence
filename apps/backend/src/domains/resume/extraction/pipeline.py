"""The deterministic extraction pipeline, and the decision to escalate.

    bytes ──parsing.py──▶ text ──clean──▶ lines ──segment──▶ sections
                                                                │
                    ┌───────────────────────────────────────────┤
                    ▼                                           ▼
              extractors (entries.py)                  coverage assessment
                    │                                           │
                    └──────────────▶ ResumeDraft ◀──────────────┘
                                          │
                              coverage below floor?
                                          │
                                    yes ──┴── no ──▶ done, no LLM call
                                     │
                                     ▼
                          LLM fallback, narrowed to
                          the fields that are missing

WHAT CHANGED AND WHY

Extraction used to be one unconditional Gemini call per upload. It is now
deterministic-first, with the model reached only when the document defeats
the parser. Three reasons, in the order they actually matter:

1. **Per-field confidence becomes possible.** This is the product reason and
   it is the one that forced the rewrite. The review screen shows a green or
   amber badge per field so a student checks the four fields that are
   probably wrong instead of re-reading forty. A model cannot supply that
   honestly — see `confidence.py`'s opening argument. Provenance can.

2. **Latency.** The deterministic pass is single-digit milliseconds against
   roughly two to five seconds for a model round trip. On the resumes it
   fully covers, the student's "reading your resume" screen resolves before
   the progress animation finishes its first beat.

3. **Cost and blast radius.** A well-structured resume — the majority — now
   costs nothing to parse and cannot be affected by a provider outage,
   rate limit, or model deprecation. The LLM becomes a fallback for hard
   documents rather than a hard dependency of onboarding.

WHAT DID NOT CHANGE, DELIBERATELY

The output is still a `ResumeExtraction`, still written to
`resume_extraction_drafts`, still confirmed field-by-field by the student
before anything reaches a live profile. This is a change of *how* the draft
is produced, not of the guarantee that a draft is all it is. `confirm.py` is
untouched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from src.domains.ai.extraction_schema import (
    ExtractedCertificate,
    ExtractedContact,
    ExtractedEducation,
    ExtractedExperience,
    ExtractedProject,
    ResumeExtraction,
)
from src.domains.resume.extraction import entries
from src.domains.resume.extraction.confidence import FieldMap, aggregate_confidence
from src.domains.resume.extraction.normalize import clean_text, to_lines
from src.domains.resume.extraction.sections import SectionKind, segment
from src.domains.resume.extraction.taxonomy import DetectedSkill

logger = structlog.get_logger(__name__)

#: Sections whose presence means the document was understood as a resume at
#: all. A file with none of these parsed as text but is not a resume — a
#: cover letter, a transcript, a mis-uploaded assignment — and escalating it
#: to the model wastes a call on a document no extractor can help with.
_CORE_SECTIONS = (SectionKind.EDUCATION, SectionKind.EXPERIENCE, SectionKind.PROJECTS)

#: Below this mean field confidence, the LLM fallback runs. 0.55 sits below
#: PATTERN (0.7) and above INFERRED (0.45): a draft built mostly from
#: pattern matches stands on its own, one built mostly from positional
#: guesses does not.
_ESCALATION_FLOOR = 0.55

#: A draft with fewer than this many populated entries across all sections is
#: escalated regardless of confidence. High confidence on two fields is not
#: a good draft — it is a parser that found almost nothing and was sure
#: about it, which is precisely the failure the mean would hide.
_MIN_ENTRIES = 3


@dataclass
class ResumeDraft:
    """The deterministic pass's full output, before it becomes a schema object.

    Carries the `FieldMap`s rather than only the final values, because the
    review screen needs per-field confidence and the escalation decision
    needs to know *which* fields are weak, not just that the average is.
    """

    contact: FieldMap
    education: list[FieldMap] = field(default_factory=list)
    experience: list[FieldMap] = field(default_factory=list)
    projects: list[FieldMap] = field(default_factory=list)
    certificates: list[FieldMap] = field(default_factory=list)
    skills: list[DetectedSkill] = field(default_factory=list)
    #: Headings the segmenter found but could not classify. Handed to the
    #: fallback verbatim — an unrecognised heading is the exact case a fixed
    #: vocabulary cannot cover and a model can.
    unknown_headings: list[str] = field(default_factory=list)

    @property
    def entry_count(self) -> int:
        return (
            len(self.education) + len(self.experience) + len(self.projects) + len(self.certificates)
        )

    @property
    def confidence(self) -> float:
        return aggregate_confidence(
            [self.contact, *self.education, *self.experience, *self.projects, *self.certificates]
        )

    def wire(self) -> dict[str, Any]:
        """Per-field confidence for the review screen.

        Parallel in shape to `ResumeExtraction` so the client can index into
        it with the same paths it uses to render values — `contact.email` and
        `education[0].degree` address the same field in both structures.
        """
        return {
            "contact": self.contact.wire(),
            "education": [fmap.wire() for fmap in self.education],
            "experience": [fmap.wire() for fmap in self.experience],
            "projects": [fmap.wire() for fmap in self.projects],
            "certificates": [fmap.wire() for fmap in self.certificates],
            "skills": [
                {"value": skill.canonical, "surface": skill.surface, **skill.scored.wire()}
                for skill in self.skills
            ],
            "overall_confidence": self.confidence,
        }


def parse_resume(text: str) -> ResumeDraft:
    """Run the deterministic pass. Never raises on unreadable content.

    A resume this cannot read produces an empty draft, which
    `needs_escalation` then reports as needing the model. Raising here would
    turn "the parser found nothing" into a job failure, and the whole point
    of the fallback is that finding nothing is a recoverable state.
    """
    cleaned = clean_text(text)
    lines = to_lines(cleaned)
    sections = segment(lines)

    draft = ResumeDraft(
        contact=entries.extract_contact(lines, sections),
        education=entries.extract_education(lines, sections),
        experience=entries.extract_experience(lines, sections),
        projects=entries.extract_projects(lines, sections),
        certificates=entries.extract_certificates(lines, sections),
        skills=entries.extract_skills(lines, sections),
        unknown_headings=[
            section.heading for section in sections if section.kind is SectionKind.OTHER
        ],
    )

    logger.info(
        "resume_deterministic_pass",
        sections=[section.kind.value for section in sections],
        entries=draft.entry_count,
        skills=len(draft.skills),
        confidence=draft.confidence,
    )
    return draft


def needs_escalation(draft: ResumeDraft, sections_found: set[SectionKind]) -> tuple[bool, str]:
    """Whether to spend an LLM call, and the reason — logged either way.

    The reason string is returned rather than logged internally so the caller
    can attach it to the draft row. "Why did this resume cost a model call"
    is a question worth being able to answer per-upload when tuning the
    thresholds, and a bare boolean makes it unanswerable after the fact.
    """
    if not sections_found & set(_CORE_SECTIONS):
        return True, "no_core_sections"
    if draft.entry_count < _MIN_ENTRIES:
        return True, f"too_few_entries:{draft.entry_count}"
    if draft.confidence < _ESCALATION_FLOOR:
        return True, f"low_confidence:{draft.confidence}"
    return False, "deterministic_sufficient"


# --------------------------------------------------------------------------
# Assembly into the wire schema
# --------------------------------------------------------------------------


def _contact(fmap: FieldMap) -> ExtractedContact:
    return ExtractedContact(
        full_name=fmap.value("full_name"),
        email=fmap.value("email"),
        phone=fmap.value("phone"),
        headline=fmap.value("headline"),
        location=fmap.value("location"),
        github_username=fmap.value("github_username"),
        leetcode_handle=fmap.value("leetcode_handle"),
        codeforces_handle=fmap.value("codeforces_handle"),
        hackerrank_handle=fmap.value("hackerrank_handle"),
        links=fmap.value("links", []) or [],
    )


def to_extraction(draft: ResumeDraft) -> ResumeExtraction:
    """Collapse the confidence-annotated draft into the existing wire schema.

    Confidence is dropped here on purpose. `ResumeExtraction` is the contract
    `confirm.py` and the LLM providers already share, and widening it with
    per-field metadata would force every consumer to understand a shape only
    the review screen needs. The confidence view travels beside it, via
    `ResumeDraft.wire()`, on its own column.
    """
    return ResumeExtraction(
        contact=_contact(draft.contact),
        education=[
            ExtractedEducation(
                institution=fmap.value("institution"),
                degree=fmap.value("degree"),
                field_of_study=fmap.value("field_of_study"),
                graduation_year=fmap.value("graduation_year"),
                location=fmap.value("location"),
            )
            for fmap in draft.education
        ],
        skills=[skill.canonical for skill in draft.skills][:60],
        projects=[
            ExtractedProject(
                title=fmap.value("title"),
                description=fmap.value("description"),
                repo_url=fmap.value("repo_url"),
                technologies=fmap.value("technologies", []) or [],
            )
            for fmap in draft.projects
        ],
        experience=[
            ExtractedExperience(
                company_name=fmap.value("company_name"),
                title=fmap.value("title"),
                employment_type=fmap.value("employment_type"),
                start_date=fmap.value("start_date"),
                end_date=fmap.value("end_date"),
                description=fmap.value("description"),
                technologies=fmap.value("technologies", []) or [],
            )
            for fmap in draft.experience
        ],
        certificates=[
            ExtractedCertificate(
                title=fmap.value("title"),
                issuer=fmap.value("issuer"),
                issued_at=fmap.value("issued_at"),
                credential_url=fmap.value("credential_url"),
            )
            for fmap in draft.certificates
        ],
    )


def merge_model_result(
    draft: ResumeDraft, model_output: ResumeExtraction
) -> tuple[ResumeExtraction, ResumeDraft]:
    """Fill gaps in the deterministic draft from the model's reading.

    THE MERGE RULE, AND WHY IT IS ONE-DIRECTIONAL

    The model may only fill fields the deterministic pass left *empty*. It
    never overwrites a value that was matched, not even a low-confidence one.

    This looks conservative and is deliberately so: an `INFERRED` institution
    is a value read off the student's actual document at a known position,
    while a model value is a reconstruction that could be a fluent invention.
    When the two disagree, the student is the right arbitrator — and they
    only get to arbitrate if the document-derived reading survives to the
    review screen. Silently preferring the model would make the disagreement
    invisible, which is the failure mode this whole architecture exists to
    avoid.

    List sections behave differently from scalar fields: a section the
    deterministic pass found *no* entries for is taken from the model whole,
    because a partially-parsed list cannot be merged item-wise without
    inventing an identity for each item that neither side supplies.
    """
    merged_contact = FieldMap(fields=dict(draft.contact.fields))
    from src.domains.resume.extraction.confidence import Provenance, Scored

    for name, value in model_output.contact.model_dump().items():
        if value in (None, "", []):
            continue
        if name in merged_contact.fields:
            continue
        merged_contact.set_if_better(
            name,
            Scored(value, Provenance.MODEL, "Read by the language-model fallback"),
        )

    def _from_model(items: list[Any], field_names: tuple[str, ...]) -> list[FieldMap]:
        result: list[FieldMap] = []
        for item in items:
            fmap = FieldMap()
            for name in field_names:
                value = getattr(item, name, None)
                if value in (None, "", []):
                    continue
                fmap.set_if_better(
                    name, Scored(value, Provenance.MODEL, "Read by the language-model fallback")
                )
            if fmap.fields:
                result.append(fmap)
        return result

    merged = ResumeDraft(
        contact=merged_contact,
        education=draft.education
        or _from_model(
            model_output.education,
            ("institution", "degree", "field_of_study", "graduation_year", "location"),
        ),
        experience=draft.experience
        or _from_model(
            model_output.experience,
            (
                "company_name",
                "title",
                "employment_type",
                "start_date",
                "end_date",
                "description",
                "technologies",
            ),
        ),
        projects=draft.projects
        or _from_model(model_output.projects, ("title", "description", "repo_url", "technologies")),
        certificates=draft.certificates
        or _from_model(
            model_output.certificates, ("title", "issuer", "issued_at", "credential_url")
        ),
        skills=draft.skills,
        unknown_headings=draft.unknown_headings,
    )

    # Skills merge by canonical name rather than by replacement: the
    # deterministic pass and the model routinely find overlapping but not
    # identical sets, and taking either whole discards real findings.
    from src.domains.resume.extraction.taxonomy import canonicalise

    known = {skill.canonical for skill in merged.skills}
    for name in model_output.skills:
        canonical = canonicalise(name)
        if canonical in known:
            continue
        known.add(canonical)
        merged.skills.append(
            DetectedSkill(
                canonical=canonical,
                surface=name,
                scored=Scored(
                    canonical, Provenance.MODEL, "Read by the language-model fallback"
                ),
            )
        )

    return to_extraction(merged), merged
