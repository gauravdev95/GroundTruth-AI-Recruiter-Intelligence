"""Text normalisation and the line model every later stage reads.

`parsing.py` turns bytes into a string. This module turns that string into a
sequence of `Line` records carrying the shape signals the rest of the
pipeline reasons about — is this line a heading, a bullet, mostly
capitalised, mostly punctuation. Section detection and entry extraction both
need those signals, and computing them once here is what stops two stages
disagreeing about whether the same line is a heading.

WHY A LINE MODEL RATHER THAN RAW STRING SEARCH

A resume's meaning is carried almost entirely by layout, and layout survives
PDF extraction only as whitespace and line breaks. Discarding that structure
to run substring searches over one flat string throws away the strongest
signal available — and it is the signal that makes `Provenance.STRUCTURAL`
meaningful. Once lines are typed, "this value sat under an Education
heading" becomes a checkable claim rather than a guess.

WHAT NORMALISATION MUST NOT DO

It must not lowercase, strip accents, or collapse a name's internal spacing.
Every value here is eventually shown back to the student as *their* data;
a pipeline that silently rewrites "Anaïs O'Brien-Kumar" has corrupted the
thing it was asked to read. Case folding happens at comparison sites
(`taxonomy.py`), never in storage.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

#: Bullet glyphs that survive PDF extraction, plus the ASCII fallbacks that
#: word processors emit. `•` alone is not enough — Word rotates through
#: several by list level, and a resume using the hollow variant for its
#: second tier would have half its bullets unrecognised.
_BULLET_CHARS = "•·▪▫◦‣⁃∙○●–—*+"
_BULLET_RE = re.compile(rf"^\s*[{re.escape(_BULLET_CHARS)}]\s+")

#: Runs of the same glyph used as a horizontal rule. Common in plain-text and
#: LaTeX-derived resumes; carries no content but reliably marks a boundary.
_RULE_RE = re.compile(r"^\s*([-=_~*]{3,}|[─-╿]{3,})\s*$")

#: Zero-width and directional marks. PDF extraction inserts these freely and
#: they break every subsequent regex silently, because they are invisible in
#: logs and test output alike.
_INVISIBLE_RE = re.compile(r"[​-‏‪-‮⁠﻿]")

#: Ligatures that pypdf emits verbatim from embedded fonts. Left unhandled,
#: "Certification" arrives as "Certiﬁcation" and fails every heading
#: match. NFKC normalisation handles most, but not all fonts map cleanly, so
#: the common five are replaced explicitly first.
_LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}


def clean_text(raw: str) -> str:
    """Normalise a document's text without altering its content.

    Order matters: ligatures are replaced before NFKC because NFKC maps some
    of them to the same output anyway and doing it first keeps the behaviour
    identical across fonts that do and do not round-trip.
    """
    text = raw
    for ligature, replacement in _LIGATURES.items():
        text = text.replace(ligature, replacement)

    # NFKC folds full-width Latin, non-breaking spaces and compatibility forms
    # into their plain equivalents. It preserves accents and case.
    text = unicodedata.normalize("NFKC", text)
    text = _INVISIBLE_RE.sub("", text)

    # Normalise line endings before any line splitting, so a CRLF document
    # does not leave a trailing \r on every single line.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse runs of 3+ blank lines to exactly two. Two is meaningful — it
    # is the strongest available "new block" signal in extracted PDF text —
    # so it is preserved rather than collapsed to one.
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Trailing whitespace per line, without touching leading indentation:
    # indentation is a layout signal that `Line.indent` reads below.
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    return text.strip()


@dataclass(frozen=True)
class Line:
    """One line of the document, with its shape precomputed.

    `index` is the position in the *cleaned* document. Every downstream stage
    refers to lines by this index, so a `Scored` value can cite the line it
    came from and the review screen can quote it back to the student.
    """

    index: int
    text: str
    #: Leading whitespace, in characters. A proxy for visual indentation —
    #: imperfect from PDF extraction, but the only such signal available, and
    #: reliable enough to distinguish a bullet's continuation from a new item.
    indent: int
    is_blank: bool
    is_bullet: bool
    is_rule: bool

    @property
    def stripped(self) -> str:
        return self.text.strip()

    @property
    def content(self) -> str:
        """The line's text with any bullet glyph removed."""
        return _BULLET_RE.sub("", self.text).strip()

    @property
    def word_count(self) -> int:
        return len(self.stripped.split())

    @property
    def alpha_ratio(self) -> float:
        """Fraction of characters that are letters.

        Distinguishes prose from the punctuation-dense lines that PDF tables
        and contact rows produce. A low ratio on a short line usually means a
        separator or a phone number, neither of which is ever a heading.
        """
        stripped = self.stripped
        if not stripped:
            return 0.0
        return sum(character.isalpha() for character in stripped) / len(stripped)

    @property
    def upper_ratio(self) -> float:
        """Fraction of *cased* characters that are uppercase.

        Denominator is cased characters, not all characters, so digits and
        punctuation in "EDUCATION (2021-2025)" do not dilute the signal that
        the alphabetic part is fully capitalised.
        """
        cased = [character for character in self.stripped if character.isalpha()]
        if not cased:
            return 0.0
        return sum(character.isupper() for character in cased) / len(cased)

    @property
    def is_title_case(self) -> bool:
        """Every alphabetic word starts uppercase.

        Short-word exceptions ("of", "and", "in") are allowed lowercase, since
        "Bachelor of Technology" is title case by any human reading and
        rejecting it would lose most degree lines.
        """
        words = [word for word in self.content.split() if word and word[0].isalpha()]
        if not words:
            return False
        minor = {"of", "and", "in", "the", "for", "at", "on", "to", "a", "an", "with"}
        return all(word[0].isupper() or word.lower() in minor for word in words)


def to_lines(text: str) -> list[Line]:
    """Split cleaned text into the line model.

    Blank lines are kept rather than filtered. They are the document's
    strongest block separator, and `sections.py` and `entries.py` both use
    them to decide where one entry ends and the next begins — filtering them
    here would force both to re-derive the same information from indices.
    """
    lines: list[Line] = []
    for index, raw in enumerate(text.split("\n")):
        stripped = raw.strip()
        lines.append(
            Line(
                index=index,
                text=raw,
                indent=len(raw) - len(raw.lstrip()),
                is_blank=not stripped,
                is_bullet=bool(_BULLET_RE.match(raw)),
                is_rule=bool(_RULE_RE.match(raw)),
            )
        )
    return lines


def join_wrapped(lines: list[Line], start: int, end: int) -> str:
    """Join a half-open line range back into prose, undoing PDF line wrapping.

    A hyphen at end-of-line is treated as a hard wrap and the hyphen removed,
    which is right far more often than it is wrong: genuinely hyphenated
    compounds ("state-of-the-art") almost never break exactly at their own
    hyphen, whereas PDF text extraction produces end-of-line hyphens
    constantly. The failure mode is a rare "stateof the art", which the
    student sees and can fix on the review screen; the alternative failure
    mode is every wrapped word in every description silently mangled.
    """
    parts: list[str] = []
    for line in lines[start:end]:
        if line.is_blank:
            continue
        chunk = line.content
        if parts and parts[-1].endswith("-"):
            parts[-1] = parts[-1][:-1] + chunk
        else:
            parts.append(chunk)
    return " ".join(part.strip() for part in parts if part.strip()).strip()
