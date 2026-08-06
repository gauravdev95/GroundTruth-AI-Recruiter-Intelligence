"""Section segmentation — the stage that makes `STRUCTURAL` provenance real.

A resume is a sequence of labelled blocks. Finding those labels is what lets
every later extractor say "this value sat under an Education heading"
instead of "this value looked education-ish", and that difference is the
whole confidence model (`confidence.py`).

TWO SIGNALS, BOTH REQUIRED

A line is a heading when it (a) matches a known heading vocabulary and (b)
*looks* like a heading — short, no terminal punctuation, and either
capitalised, title case, or followed by a rule. Requiring both is what stops
"I led the education outreach programme" from splitting a resume in half.
Vocabulary alone is far too eager on prose-heavy resumes; shape alone
cannot tell a heading from a job title.

UNRECOGNISED HEADINGS ARE KEPT, NOT DISCARDED

A block under "Publications" or "Positions of Responsibility" is classified
`OTHER` rather than dropped. Two reasons: its lines must not leak into the
preceding section's entries, and the LLM fallback is given `OTHER` blocks
explicitly, because an unrecognised heading is exactly the case a
deterministic vocabulary cannot cover and a model can.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass

from src.domains.resume.extraction.normalize import Line


class SectionKind(str, enum.Enum):
    """The blocks this pipeline knows how to read.

    `HEADER` is the implicit block before the first heading — where the name,
    contact details and headline live on essentially every resume. It has no
    heading of its own, which is why it needs a name here at all.
    """

    HEADER = "header"
    SUMMARY = "summary"
    EDUCATION = "education"
    EXPERIENCE = "experience"
    PROJECTS = "projects"
    SKILLS = "skills"
    CERTIFICATES = "certificates"
    ACHIEVEMENTS = "achievements"
    OTHER = "other"


#: Heading vocabulary, longest-phrase-first within each kind.
#:
#: Matched against a case-folded, punctuation-stripped form of the line, so
#: "EDUCATION:", "Education", and "E D U C A T I O N" (letter-spaced headings
#: are common in designed resumes and survive extraction as spaced letters)
#: all reach the same key. Phrases are substrings rather than exact matches
#: because "Technical Skills" and "Skills & Tools" must both hit SKILLS.
#:
#: ORDER IS LOAD-BEARING. `_classify` returns the first kind with a matching
#: phrase, and several phrases are ambiguous across kinds — "project" appears
#: in both PROJECTS and some EXPERIENCE headings ("Project Experience").
#: EXPERIENCE is checked before PROJECTS so that heading lands on the section
#: whose entries carry employers, which is the more damaging one to get wrong.
_HEADINGS: tuple[tuple[SectionKind, tuple[str, ...]], ...] = (
    (
        SectionKind.EDUCATION,
        ("education", "academic background", "academics", "qualifications", "academic details"),
    ),
    (
        SectionKind.EXPERIENCE,
        (
            "work experience",
            "professional experience",
            "project experience",
            "employment history",
            "internship experience",
            "experience",
            "employment",
            "internships",
            "internship",
            "work history",
        ),
    ),
    (
        SectionKind.PROJECTS,
        ("personal projects", "academic projects", "selected projects", "projects", "portfolio"),
    ),
    (
        SectionKind.SKILLS,
        (
            "technical skills",
            "core competencies",
            "skills and tools",
            "skills & tools",
            "technologies",
            "tech stack",
            "skills",
            "competencies",
        ),
    ),
    (
        SectionKind.CERTIFICATES,
        (
            "certifications",
            "certificates",
            "certification",
            "licenses",
            "courses and certifications",
            "online courses",
        ),
    ),
    (
        SectionKind.ACHIEVEMENTS,
        ("achievements", "awards", "honors", "honours", "accomplishments", "extracurricular"),
    ),
    (
        SectionKind.SUMMARY,
        ("professional summary", "career objective", "summary", "objective", "profile", "about me"),
    ),
)

#: Above this many words, a line is prose regardless of what it contains.
#: Six accommodates "Positions of Responsibility and Achievements"; seven
#: started matching sentences in summary paragraphs during tuning.
_MAX_HEADING_WORDS = 6

#: Terminal punctuation that disqualifies a heading. A colon does NOT appear
#: here — "Education:" is one of the most common heading forms there is.
_SENTENCE_END_RE = re.compile(r"[.!?,;]\s*$")

#: Letter-spaced headings ("E D U C A T I O N") arrive from designed resumes
#: as single characters separated by spaces. Collapsed before vocabulary
#: matching, but only when *every* token is a single character — otherwise
#: "R Kumar" would collapse to "RKumar".
_LETTER_SPACED_RE = re.compile(r"^(?:\w\s){3,}\w$")


def _normalise_heading(text: str) -> str:
    """Case-folded, punctuation-stripped form used for vocabulary matching."""
    candidate = text.strip()
    if _LETTER_SPACED_RE.match(candidate):
        candidate = candidate.replace(" ", "")
    # Keep inner spaces and ampersands; drop everything else. `&` survives so
    # "Skills & Tools" matches its phrase without needing an expanded variant.
    candidate = re.sub(r"[^\w\s&]", " ", candidate)
    return re.sub(r"\s+", " ", candidate).strip().casefold()


def _classify(normalised: str) -> SectionKind | None:
    for kind, phrases in _HEADINGS:
        for phrase in phrases:
            if phrase in normalised:
                return kind
    return None


#: Characters that mark a line as carrying data rather than naming a section.
#: A heading is a label; a line containing a list separator, a URL, or a
#: qualifier colon mid-string is content. Checked only on unrecognised
#: candidates — a vocabulary match already outweighs this signal, and
#: "Skills: " legitimately ends with a colon.
_CONTENT_PUNCT_RE = re.compile(r"[,|/@]|:\s*\S")

#: Word ceiling for an unrecognised heading. Tighter than
#: `_MAX_HEADING_WORDS` because without vocabulary support the only thing
#: separating "Positions of Responsibility" from "Bachelor of Technology in
#: Computer Science" is length and isolation.
_MAX_UNKNOWN_HEADING_WORDS = 4


def _looks_like_heading(
    line: Line, following: Line | None, previous: Line | None, *, in_vocabulary: bool
) -> bool:
    """Shape test. Strictness depends on whether the vocabulary matched.

    THE ASYMMETRY IS THE WHOLE POINT, and it was learned the hard way: an
    earlier version applied one shape test regardless of vocabulary, and
    title-case *content* lines — "B.Tech in Computer Science and Engineering",
    "R.V. College of Engineering, Bengaluru" — passed it. Each one opened a
    spurious `OTHER` section immediately after the real heading, leaving the
    real section spanning zero lines and silently dropping every entry under
    it. A resume would parse with its Education and Skills sections simply
    absent.

    So: vocabulary support IS evidence, and the shape test only has to carry
    the whole load when there is none.

    * **Vocabulary matched** — a weak shape signal suffices. "Education",
      "EDUCATION" and "Education:" are all headings, and requiring capitals
      would drop every title-case resume.
    * **No vocabulary match** — the line must be visually isolated (preceded
      by a blank line), short, and free of the punctuation that marks a line
      as carrying data. An unrecognised heading is real ("Positions of
      Responsibility", "Publications") but inventing one is far more
      damaging than missing one: a missed heading merges a block into its
      neighbour, while a false one truncates the section above it to nothing.

    A following horizontal rule short-circuits both branches — a line
    immediately above a rule is a heading in every resume convention there
    is, and that layout is exactly where the line itself may be neither
    capitalised nor title case.
    """
    if line.is_blank or line.is_bullet or line.is_rule:
        return False
    if line.word_count == 0 or line.word_count > _MAX_HEADING_WORDS:
        return False
    if _SENTENCE_END_RE.search(line.stripped):
        return False
    # Mostly-punctuation lines are separators the rule regex did not catch.
    if line.alpha_ratio < 0.5:
        return False

    if following is not None and following.is_rule:
        return True

    if in_vocabulary:
        return line.upper_ratio > 0.85 or line.is_title_case or line.stripped.endswith(":")

    # Unrecognised from here. Isolation is the strongest available signal and
    # is required unconditionally: section headings sit under a blank line,
    # lines inside a block do not. This is also what keeps the document's
    # opening name line — title case, two words, index 0 — out of the
    # boundary list, which is what preserves the header block the contact
    # extractor reads.
    if previous is None or not previous.is_blank:
        return False
    if line.word_count > _MAX_UNKNOWN_HEADING_WORDS:
        return False
    if any(character.isdigit() for character in line.content):
        return False
    if _CONTENT_PUNCT_RE.search(line.content):
        return False

    return line.upper_ratio > 0.85 or line.is_title_case


@dataclass(frozen=True)
class Section:
    kind: SectionKind
    #: The heading line's text as written, or "" for the implicit header
    #: block. Carried so `Scored.evidence` can quote the real heading — a
    #: student who sees "Found under 'ACADEMIC BACKGROUND'" learns something
    #: that "Found under Education" hides.
    heading: str
    #: Half-open range of content line indices, heading itself excluded.
    start: int
    end: int

    def lines(self, all_lines: list[Line]) -> list[Line]:
        return [line for line in all_lines[self.start : self.end] if not line.is_rule]


def segment(lines: list[Line]) -> list[Section]:
    """Split the line model into sections.

    The implicit `HEADER` block is emitted only when it has content, so a
    resume that opens directly with a heading does not produce an empty one
    for the contact extractor to scan.
    """
    boundaries: list[tuple[int, SectionKind, str]] = []

    for index, line in enumerate(lines):
        # Classification runs first: the shape test's strictness depends on
        # whether the vocabulary matched, so the two cannot be evaluated in
        # the other order.
        normalised = _normalise_heading(line.content)
        if not normalised:
            continue
        kind = _classify(normalised)

        following = lines[index + 1] if index + 1 < len(lines) else None
        previous = lines[index - 1] if index > 0 else None
        if not _looks_like_heading(line, following, previous, in_vocabulary=kind is not None):
            continue

        # An unrecognised heading still ends the previous section. Treating it
        # as ordinary content is what causes a Publications block to be parsed
        # as more Experience entries.
        boundaries.append((index, kind or SectionKind.OTHER, line.content))

    sections: list[Section] = []

    first_heading = boundaries[0][0] if boundaries else len(lines)
    if any(not line.is_blank for line in lines[:first_heading]):
        sections.append(Section(SectionKind.HEADER, "", 0, first_heading))

    for position, (line_index, kind, heading) in enumerate(boundaries):
        start = line_index + 1
        end = boundaries[position + 1][0] if position + 1 < len(boundaries) else len(lines)
        # A heading immediately followed by another heading has no content.
        # Emitting it would give later stages an empty section to special-case.
        if start >= end:
            continue
        sections.append(Section(kind, heading, start, end))

    return sections


def find(sections: list[Section], kind: SectionKind) -> list[Section]:
    """Every section of one kind.

    A list rather than an optional single section: resumes routinely split
    "Internships" and "Work Experience" into two blocks that both mean
    EXPERIENCE, and collapsing them to the first would silently drop half the
    student's history.
    """
    return [section for section in sections if section.kind is kind]


#: A line that is nothing but a URL. In a flat list it is a continuation of
#: the entry above — a credential link under its certificate — never a new
#: entry of its own.
_BARE_URL_RE = re.compile(r"^\s*(?:https?://|www\.)\S+\s*$", re.IGNORECASE)


def blocks(lines: list[Line], section: Section, *, flat_split: bool = False) -> list[list[Line]]:
    """Split one section into entry-sized blocks.

    Three separators, in priority order:

    1. A blank line — the strongest and most common signal.
    2. A return to the section's minimum indentation after deeper lines,
       which is how indented sub-bullets under a role are kept attached to it.
    3. Nothing else. Bullet glyphs are deliberately NOT separators: a role
       with four bullet points is one entry, and treating each bullet as an
       entry is the single most common way naive resume parsers produce
       "four internships at the same company".

    `flat_split` handles the section that has none of those signals: a run of
    unindented, unbulleted, blank-line-free lines. Whether that is one entry
    or several is genuinely ambiguous from layout alone, and the answer
    differs by section kind rather than by anything observable in the text:

    * An **education** entry legitimately spans several flat lines — degree,
      then institution, then dates — so a flat run is ONE entry.
    * A **certificate** list is conventionally one entry per line, so a flat
      run is one entry PER LINE.

    Rather than guess, the caller states which convention its section
    follows. Bare-URL lines are attached to the entry above in either mode,
    since a credential link is never itself an entry.
    """
    section_lines = section.lines(lines)
    content = [line for line in section_lines if not line.is_blank]
    if not content:
        return []

    base_indent = min(line.indent for line in content)

    if flat_split and not any(
        line.is_bullet or line.indent > base_indent for line in content
    ):
        result: list[list[Line]] = []
        for line in content:
            if result and _BARE_URL_RE.match(line.text):
                result[-1].append(line)
            else:
                result.append([line])
        return result

    result: list[list[Line]] = []
    current: list[Line] = []

    for line in section_lines:
        if line.is_blank:
            if current:
                result.append(current)
                current = []
            continue

        # A non-bullet line back at base indentation starts a new entry, but
        # only if the current block already has content deeper than base —
        # otherwise a flat, unindented section becomes one entry per line.
        if (
            current
            and not line.is_bullet
            and line.indent <= base_indent
            and any(other.indent > base_indent or other.is_bullet for other in current)
        ):
            result.append(current)
            current = []

        current.append(line)

    if current:
        result.append(current)

    return result
