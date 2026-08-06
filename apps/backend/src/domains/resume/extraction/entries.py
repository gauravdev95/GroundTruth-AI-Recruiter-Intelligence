"""Entry extractors — one per section kind.

Each function takes the line model plus the sections found in it and returns
`FieldMap`s carrying `Scored` values. None of them writes to the database,
none of them raises on a resume it cannot read: a section that yields
nothing yields an empty list, and `pipeline.py` decides whether that is
worth sending to the LLM fallback.

THE SHARED RULE ACROSS ALL OF THEM

An extractor may only claim `STRUCTURAL` provenance for a value it found
*inside the section that section kind names*. A company name found in an
Education block is `PATTERN` at best. This is what stops the confidence
score from becoming a restatement of how confident the regex author felt.

WHY EVERY EXTRACTOR IS TOLERANT OF MISSING FIELDS

The extraction schema makes every field optional on purpose
(`ai/extraction_schema.py`), because a partial draft is useful and a
required field pushes any extractor — model or regex — toward inventing a
value to satisfy it. These functions inherit that: they emit what they can
prove and leave the rest for the student or the fallback.
"""

from __future__ import annotations

import re

from src.domains.resume.extraction import patterns
from src.domains.resume.extraction.confidence import FieldMap, Provenance, Scored
from src.domains.resume.extraction.normalize import Line, join_wrapped
from src.domains.resume.extraction.sections import Section, SectionKind, blocks, find
from src.domains.resume.extraction.taxonomy import DetectedSkill, detect_skills

# --------------------------------------------------------------------------
# Contact — the header block
# --------------------------------------------------------------------------

#: Labels that precede a contact value. Their presence upgrades a match from
#: PATTERN to EXPLICIT for fields where the bare pattern is ambiguous.
_LABEL_RE = re.compile(
    r"\b(email|e-mail|mail|phone|mobile|contact|tel|linkedin|github|location|address)\b\s*[:\-|]",
    re.IGNORECASE,
)


def _first_person_name(lines: list[Line]) -> Scored[str] | None:
    """The document's opening line, when it looks like a person's name.

    Positional heuristic, so `INFERRED` — never better. It is pre-fill only:
    `confirm.py` already refuses to let a resume overwrite the account's
    verified `full_name`, so the worst case is a wrong value the student
    sees on the review screen and ignores.
    """
    for line in lines[:6]:
        if line.is_blank or line.is_bullet:
            continue
        content = line.content
        if patterns.EMAIL_RE.search(content) or patterns.URL_RE.search(content):
            continue
        words = content.split()
        if not (2 <= len(words) <= 5):
            continue
        if not line.is_title_case and line.upper_ratio < 0.85:
            continue
        if any(character.isdigit() for character in content):
            continue
        return Scored(
            value=content,
            provenance=Provenance.INFERRED,
            evidence="First line of the document",
        )
    return None


def extract_contact(lines: list[Line], sections: list[Section]) -> FieldMap:
    """Identity, contact details and developer handles.

    Scans the header block plus the first 25 lines. The overlap is deliberate:
    a resume whose contact row sits *below* a "Summary" heading has no header
    block at all, and restricting this to `SectionKind.HEADER` would find
    nothing on exactly those documents.
    """
    fmap = FieldMap()

    header_sections = find(sections, SectionKind.HEADER)
    scan: list[Line] = []
    for section in header_sections:
        scan.extend(section.lines(lines))
    scan.extend(line for line in lines[:25] if line not in scan)

    text = "\n".join(line.content for line in scan)

    email = patterns.EMAIL_RE.search(text)
    if email:
        fmap.set_if_better(
            "email",
            Scored(email.group(0), Provenance.EXPLICIT, "Matched an email address"),
        )

    for match in patterns.PHONE_RE.finditer(text):
        if len(patterns.clean_digits(match.group(0))) >= patterns.PHONE_MIN_DIGITS:
            fmap.set_if_better(
                "phone",
                Scored(match.group(0).strip(), Provenance.EXPLICIT, "Matched a phone number"),
            )
            break

    # Repo URLs are consumed first so a linked project repository cannot be
    # mistaken for the student's own account handle.
    repo_owners = {match.group(1).casefold() for match in patterns.REPO_URL_RE.finditer(text)}

    for match in patterns.GITHUB_USER_RE.finditer(text):
        handle = match.group(1)
        if handle.casefold() in patterns.GITHUB_RESERVED:
            continue
        # A bare profile URL outranks an owner inferred from a repo link.
        provenance = (
            Provenance.PATTERN if handle.casefold() in repo_owners else Provenance.EXPLICIT
        )
        fmap.set_if_better(
            "github_username",
            Scored(handle, provenance, "Matched a github.com profile link"),
        )
        break

    for field_name, pattern, label in (
        ("leetcode_handle", patterns.LEETCODE_RE, "LeetCode"),
        ("codeforces_handle", patterns.CODEFORCES_RE, "Codeforces"),
        ("hackerrank_handle", patterns.HACKERRANK_RE, "HackerRank"),
    ):
        match = pattern.search(text)
        if match:
            fmap.set_if_better(
                field_name,
                Scored(match.group(1), Provenance.EXPLICIT, f"Matched a {label} profile link"),
            )

    name = _first_person_name(scan)
    if name is not None:
        fmap.set_if_better("full_name", name)

    # Headline: the first substantial line of a Summary section, or failing
    # that a short non-contact line near the top. Summary-derived is
    # STRUCTURAL; the positional fallback is INFERRED.
    summary_sections = find(sections, SectionKind.SUMMARY)
    if summary_sections:
        summary_lines = summary_sections[0].lines(lines)
        prose = join_wrapped(summary_lines, 0, len(summary_lines))
        if prose:
            fmap.set_if_better(
                "headline",
                Scored(
                    prose[:200],
                    Provenance.STRUCTURAL,
                    f"Read from the '{summary_sections[0].heading}' section",
                ),
            )

    # Other links, excluding anything already captured as a handle.
    captured = {
        str(fmap.value(key, "")).casefold()
        for key in ("github_username", "leetcode_handle", "codeforces_handle", "hackerrank_handle")
    }
    links: list[str] = []
    for match in patterns.URL_RE.finditer(text):
        url = match.group(0).rstrip(".,;)")
        if any(handle and handle in url.casefold() for handle in captured):
            continue
        if url not in links:
            links.append(url)
    if links:
        fmap.set_if_better(
            "links",
            Scored(links[:10], Provenance.EXPLICIT, "URLs written in the document"),
        )

    return fmap


# --------------------------------------------------------------------------
# Education
# --------------------------------------------------------------------------


def _match_degree(text: str) -> tuple[str, str] | None:
    """`(canonical, matched_surface)` for the first degree form in `text`.

    Periods are stripped before lookup so "B.Tech" and "BTech" share one
    vocabulary entry. Longest-first so "bachelor of technology" is not
    shadowed by the "be" entry matching inside it.
    """
    folded = re.sub(r"[.\-]", "", text).casefold()
    for form in sorted(patterns.DEGREE_FORMS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(form)}\b", folded):
            return patterns.DEGREE_FORMS[form], form
    return None


def extract_education(lines: list[Line], sections: list[Section]) -> list[FieldMap]:
    entries: list[FieldMap] = []

    for section in find(sections, SectionKind.EDUCATION):
        for block in blocks(lines, section):
            text = join_wrapped(block, 0, len(block))
            if not text:
                continue

            fmap = FieldMap()
            evidence = f"Found under '{section.heading}'"

            degree = _match_degree(text)
            if degree is not None:
                canonical, _ = degree
                fmap.set_if_better(
                    "degree", Scored(canonical, Provenance.STRUCTURAL, evidence)
                )

            # Institution: the line carrying an institution marker, preferred
            # over the block's first line, because the first line is as often
            # the degree as the college.
            for line in block:
                lowered = line.content.casefold()
                if any(
                    re.search(rf"\b{marker}\b", lowered)
                    for marker in patterns.INSTITUTION_MARKERS
                ):
                    fmap.set_if_better(
                        "institution",
                        Scored(
                            line.content.strip(" ,|-"),
                            Provenance.STRUCTURAL,
                            f"{evidence}; line names an institution",
                        ),
                    )
                    break
            else:
                if block:
                    fmap.set_if_better(
                        "institution",
                        Scored(block[0].content.strip(" ,|-"), Provenance.INFERRED, evidence),
                    )

            year = patterns.parse_year(text)
            if year is not None:
                fmap.set_if_better(
                    "graduation_year",
                    Scored(year, Provenance.STRUCTURAL, f"{evidence}; latest year in the entry"),
                )

            # Field of study: text after the degree, before a comma or year.
            if degree is not None:
                _, surface = degree
                tail = re.split(rf"\b{re.escape(surface)}\b", text, maxsplit=1, flags=re.IGNORECASE)
                if len(tail) > 1:
                    candidate = re.split(r"[,|\d]", tail[1], maxsplit=1)[0]
                    candidate = candidate.strip(" .,-–—inof")
                    if 2 < len(candidate) < 80:
                        fmap.set_if_better(
                            "field_of_study",
                            Scored(candidate, Provenance.PATTERN, "Text following the degree"),
                        )

            if fmap.fields:
                entries.append(fmap)

    return entries


# --------------------------------------------------------------------------
# Experience
# --------------------------------------------------------------------------


def _employment_type(text: str) -> str | None:
    lowered = text.casefold()
    for surface, canonical in patterns.EMPLOYMENT_TYPES.items():
        if re.search(rf"\b{re.escape(surface)}\b", lowered):
            return canonical
    return None


def extract_experience(lines: list[Line], sections: list[Section]) -> list[FieldMap]:
    entries: list[FieldMap] = []

    for section in find(sections, SectionKind.EXPERIENCE):
        for block in blocks(lines, section):
            headline_lines = [line for line in block if not line.is_bullet]
            if not headline_lines:
                continue

            head = join_wrapped(headline_lines, 0, min(2, len(headline_lines)))
            whole = join_wrapped(block, 0, len(block))
            if not head:
                continue

            fmap = FieldMap()
            evidence = f"Found under '{section.heading}'"

            start, end, is_current = patterns.parse_date_range(head)
            if start is None:
                start, end, is_current = patterns.parse_date_range(whole)

            if start is not None:
                fmap.set_if_better(
                    "start_date",
                    Scored(start.isoformat(), Provenance.STRUCTURAL, f"{evidence}; date range"),
                )
            if end is not None:
                fmap.set_if_better(
                    "end_date",
                    Scored(end.isoformat(), Provenance.STRUCTURAL, f"{evidence}; date range"),
                )
            if is_current:
                fmap.set_if_better(
                    "is_current",
                    Scored(True, Provenance.EXPLICIT, "Entry states the role is ongoing"),
                )

            # Strip the date range out before splitting title from company —
            # left in, it becomes the "company" on every entry laid out as
            # "Role — Company — Jan 2024 - Present".
            without_dates = patterns.DATE_RANGE_RE.sub("", head).strip(" ,|–—-")
            parts = [
                part.strip()
                for part in re.split(r"\s*[|·•]\s*|\s+[–—]\s+|\s{2,}|,\s+", without_dates)
                if part.strip()
            ]

            if parts:
                fmap.set_if_better(
                    "title", Scored(parts[0], Provenance.STRUCTURAL, evidence)
                )
            if len(parts) > 1:
                company = parts[1]
                lowered = company.casefold()
                corroborated = any(
                    re.search(rf"\b{marker}\b", lowered) for marker in patterns.COMPANY_MARKERS
                )
                fmap.set_if_better(
                    "company_name",
                    Scored(
                        company,
                        Provenance.STRUCTURAL,
                        evidence,
                        corroborations=1 if corroborated else 0,
                    ),
                )

            employment = _employment_type(whole)
            if employment is not None:
                fmap.set_if_better(
                    "employment_type",
                    Scored(employment, Provenance.PATTERN, "Stated in the entry text"),
                )

            bullets = [line.content for line in block if line.is_bullet]
            description = " ".join(bullets) if bullets else whole
            if description:
                fmap.set_if_better(
                    "description",
                    Scored(description[:4000], Provenance.STRUCTURAL, evidence),
                )

            skills = detect_skills(whole, in_skills_section=False, evidence=evidence)
            if skills:
                fmap.set_if_better(
                    "technologies",
                    Scored(
                        [skill.canonical for skill in skills][:15],
                        Provenance.PATTERN,
                        "Recognised technology names in the entry",
                    ),
                )

            if fmap.fields:
                entries.append(fmap)

    return entries


# --------------------------------------------------------------------------
# Projects
# --------------------------------------------------------------------------


def extract_projects(lines: list[Line], sections: list[Section]) -> list[FieldMap]:
    entries: list[FieldMap] = []

    for section in find(sections, SectionKind.PROJECTS):
        for block in blocks(lines, section):
            whole = join_wrapped(block, 0, len(block))
            if not whole:
                continue

            fmap = FieldMap()
            evidence = f"Found under '{section.heading}'"

            title_line = next((line for line in block if not line.is_bullet), None)
            if title_line is not None:
                title = patterns.URL_RE.sub("", title_line.content).strip(" ,|–—-:")
                # Drop a trailing tech list — "Portfolio Site | React, Vite"
                # is one project named "Portfolio Site".
                title = re.split(r"\s*[|·•]\s*", title)[0].strip()
                if title:
                    fmap.set_if_better(
                        "title", Scored(title[:200], Provenance.STRUCTURAL, evidence)
                    )

            repo = patterns.REPO_URL_RE.search(whole)
            if repo is not None:
                owner, name = repo.group(1), repo.group(2)
                if owner.casefold() not in patterns.GITHUB_RESERVED:
                    fmap.set_if_better(
                        "repo_url",
                        Scored(
                            f"https://github.com/{owner}/{name}",
                            Provenance.EXPLICIT,
                            "Repository URL written in the entry",
                        ),
                    )

            bullets = [line.content for line in block if line.is_bullet]
            description = " ".join(bullets) if bullets else whole
            if description:
                fmap.set_if_better(
                    "description",
                    Scored(description[:4000], Provenance.STRUCTURAL, evidence),
                )

            skills = detect_skills(whole, in_skills_section=False, evidence=evidence)
            if skills:
                fmap.set_if_better(
                    "technologies",
                    Scored(
                        [skill.canonical for skill in skills][:15],
                        Provenance.PATTERN,
                        "Recognised technology names in the entry",
                    ),
                )

            if fmap.fields:
                entries.append(fmap)

    return entries


# --------------------------------------------------------------------------
# Certificates
# --------------------------------------------------------------------------


def extract_certificates(lines: list[Line], sections: list[Section]) -> list[FieldMap]:
    entries: list[FieldMap] = []

    for section in find(sections, SectionKind.CERTIFICATES):
        # One entry per line in a flat list — the certificate convention.
        # See `blocks`' docstring for why this differs from education.
        for block in blocks(lines, section, flat_split=True):
            whole = join_wrapped(block, 0, len(block))
            if not whole:
                continue

            fmap = FieldMap()
            evidence = f"Found under '{section.heading}'"

            url = patterns.URL_RE.search(whole)
            if url is not None:
                fmap.set_if_better(
                    "credential_url",
                    Scored(
                        url.group(0).rstrip(".,;)"),
                        Provenance.EXPLICIT,
                        "Credential URL written in the entry",
                    ),
                )

            without_url = patterns.URL_RE.sub("", whole).strip(" ,|–—-")
            parts = [
                part.strip()
                for part in re.split(r"\s*[|·•]\s*|\s+[–—]\s+|,\s+", without_url)
                if part.strip()
            ]

            if parts:
                title = patterns.DATE_RANGE_RE.sub("", parts[0]).strip(" ,|–—-")
                title = re.sub(r"\b(19|20)\d{2}\b", "", title).strip(" ,|–—-")
                if title:
                    fmap.set_if_better(
                        "title", Scored(title[:200], Provenance.STRUCTURAL, evidence)
                    )

            # Issuer: a known issuer name anywhere in the entry beats the
            # positional second segment, which is often a date or a score.
            lowered = whole.casefold()
            for key in patterns.ISSUER_KEYS_BY_LENGTH:
                if re.search(rf"\b{re.escape(key)}\b", lowered):
                    fmap.set_if_better(
                        "issuer",
                        Scored(
                            patterns.KNOWN_ISSUERS[key],
                            Provenance.EXPLICIT,
                            "Matched a known certificate issuer",
                        ),
                    )
                    break
            else:
                if len(parts) > 1:
                    fmap.set_if_better(
                        "issuer",
                        Scored(parts[1][:200], Provenance.PATTERN, "Second segment of the entry"),
                    )

            issued = patterns.parse_month_year(whole)
            if issued is not None:
                fmap.set_if_better(
                    "issued_at",
                    Scored(issued.isoformat(), Provenance.PATTERN, "Date written in the entry"),
                )

            if fmap.fields:
                entries.append(fmap)

    return entries


# --------------------------------------------------------------------------
# Skills
# --------------------------------------------------------------------------


def extract_skills(lines: list[Line], sections: list[Section]) -> list[DetectedSkill]:
    """Skills from the Skills section, then from everywhere else.

    Section hits are `STRUCTURAL` and body hits are `PATTERN`, and the
    section pass runs first so a skill appearing in both keeps the stronger
    provenance (`FieldMap.set_if_better` semantics, applied here by dict
    insertion order).
    """
    found: dict[str, DetectedSkill] = {}

    for section in find(sections, SectionKind.SKILLS):
        section_lines = section.lines(lines)
        text = join_wrapped(section_lines, 0, len(section_lines))
        for skill in detect_skills(
            text, in_skills_section=True, evidence=f"Listed under '{section.heading}'"
        ):
            found.setdefault(skill.canonical, skill)

    body = "\n".join(
        line.content
        for section in sections
        if section.kind in (SectionKind.PROJECTS, SectionKind.EXPERIENCE, SectionKind.SUMMARY)
        for line in section.lines(lines)
    )
    for skill in detect_skills(body, in_skills_section=False):
        found.setdefault(skill.canonical, skill)

    return list(found.values())
