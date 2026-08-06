"""Unit tests for the deterministic resume extraction pipeline.

Two groups, and the split matters:

* **Behaviour** — what the pipeline extracts from representative documents.
* **Regression** — the specific failures found while building it. Each one
  names the bug it locks down, because a test called
  `test_flat_certificate_list_splits_per_line` is only obviously worth
  keeping if the reader knows it once returned one entry for a five-item
  list.
"""

from __future__ import annotations

from src.domains.resume.extraction import needs_escalation, parse_resume, to_extraction
from src.domains.resume.extraction.confidence import (
    FieldMap,
    Provenance,
    Scored,
    aggregate_confidence,
)
from src.domains.resume.extraction.normalize import clean_text, to_lines
from src.domains.resume.extraction.sections import SectionKind, segment
from src.domains.resume.extraction.taxonomy import canonicalise, detect_skills

WELL_FORMED = """Priya Raghunathan
priya.raghunathan@example.com | +91 98765 43210 | Bengaluru, India
github.com/priyarag | linkedin.com/in/priyarag | leetcode.com/u/priya_r

SUMMARY
Final-year computer science student focused on distributed systems.

EDUCATION
B.Tech in Computer Science and Engineering
R.V. College of Engineering, Bengaluru
2021 - 2025 | CGPA 8.9/10

TECHNICAL SKILLS
Languages: Python, Go, TypeScript, C++, SQL
Infrastructure: Docker, Kubernetes, AWS, PostgreSQL, Redis

EXPERIENCE
Backend Engineering Intern | Razorpay Technologies Pvt Ltd | May 2024 - Aug 2024
  - Built an idempotency layer for the payments API
  - Stack: Go, PostgreSQL, Redis

Software Engineering Intern | Zerodha | Jun 2023 - Aug 2023
  - Implemented a WebSocket fan-out service in Python

PROJECTS
Raft Consensus Implementation | github.com/priyarag/raft-kv
  - A fault-tolerant distributed key-value store

CERTIFICATIONS
AWS Certified Solutions Architect - Associate | Amazon Web Services | Mar 2024
https://credly.com/badges/abc123
Machine Learning Specialization | Coursera | Nov 2023
"""


def _sections(text: str) -> set[SectionKind]:
    return {section.kind for section in segment(to_lines(clean_text(text)))}


# --------------------------------------------------------------------------
# Behaviour
# --------------------------------------------------------------------------


def test_all_sections_are_found():
    found = _sections(WELL_FORMED)
    for kind in (
        SectionKind.HEADER,
        SectionKind.SUMMARY,
        SectionKind.EDUCATION,
        SectionKind.SKILLS,
        SectionKind.EXPERIENCE,
        SectionKind.PROJECTS,
        SectionKind.CERTIFICATES,
    ):
        assert kind in found, f"{kind.value} was not detected"


def test_contact_details_are_explicit():
    draft = parse_resume(WELL_FORMED)
    contact = draft.contact

    assert contact.value("email") == "priya.raghunathan@example.com"
    assert contact.value("github_username") == "priyarag"
    assert contact.value("leetcode_handle") == "priya_r"
    # An email is unambiguous, so it must reach the top confidence tier —
    # this is what puts a green badge on it in the review screen.
    assert contact.fields["email"].provenance is Provenance.EXPLICIT
    assert not contact.fields["email"].needs_review


def test_education_reads_degree_institution_and_graduation_year():
    draft = parse_resume(WELL_FORMED)
    assert len(draft.education) == 1
    education = draft.education[0]

    assert education.value("degree") == "B.Tech"
    assert "R.V. College of Engineering" in education.value("institution")
    # The LAST year of "2021 - 2025", not the first — a student graduates at
    # the end of the range, and taking the first would record every
    # enrolment year as a graduation year.
    assert education.value("graduation_year") == 2025


def test_both_experience_entries_are_separate():
    draft = parse_resume(WELL_FORMED)
    assert len(draft.experience) == 2

    titles = {entry.value("title") for entry in draft.experience}
    assert titles == {"Backend Engineering Intern", "Software Engineering Intern"}

    companies = {entry.value("company_name") for entry in draft.experience}
    assert "Zerodha" in companies

    first = next(e for e in draft.experience if e.value("company_name") == "Zerodha")
    assert first.value("start_date") == "2023-06-01"
    assert first.value("end_date") == "2023-08-01"
    assert first.value("employment_type") == "internship"


def test_project_repo_url_is_normalised():
    draft = parse_resume(WELL_FORMED)
    assert len(draft.projects) == 1
    assert draft.projects[0].value("repo_url") == "https://github.com/priyarag/raft-kv"


def test_skills_are_canonicalised():
    draft = parse_resume(WELL_FORMED)
    names = {skill.canonical for skill in draft.skills}

    assert {"Python", "TypeScript", "Docker", "Kubernetes", "PostgreSQL"} <= names
    # "C++" must survive as itself rather than folding into "C".
    assert "C++" in names


def test_well_formed_resume_does_not_escalate():
    draft = parse_resume(WELL_FORMED)
    escalate, reason = needs_escalation(draft, _sections(WELL_FORMED))
    assert escalate is False, f"escalated unnecessarily: {reason}"


def test_unreadable_document_escalates_instead_of_raising():
    draft = parse_resume("Dear Sir or Madam,\n\nI am writing to apply.\n\nRegards.")
    escalate, _ = needs_escalation(draft, _sections("Dear Sir"))
    assert escalate is True


def test_to_extraction_produces_a_valid_schema_object():
    extraction = to_extraction(parse_resume(WELL_FORMED))
    assert extraction.contact.email == "priya.raghunathan@example.com"
    assert len(extraction.experience) == 2
    assert extraction.education[0].graduation_year == 2025


# --------------------------------------------------------------------------
# Confidence
# --------------------------------------------------------------------------


def test_provenance_orders_confidence():
    explicit = Scored("x", Provenance.EXPLICIT)
    structural = Scored("x", Provenance.STRUCTURAL)
    pattern = Scored("x", Provenance.PATTERN)
    inferred = Scored("x", Provenance.INFERRED)

    assert explicit.score > structural.score > pattern.score > inferred.score
    assert not structural.needs_review
    assert pattern.needs_review


def test_model_provenance_always_needs_review():
    """A model value can be an invention rather than a misreading, so it is
    never allowed into the green band — corroboration included."""
    scored = Scored("x", Provenance.MODEL, corroborations=5)
    assert scored.needs_review is True
    assert scored.band == "review"


def test_corroboration_cannot_promote_an_inferred_guess():
    scored = Scored("x", Provenance.INFERRED, corroborations=10)
    assert scored.needs_review is True


def test_set_if_better_keeps_the_stronger_reading():
    fmap = FieldMap()
    fmap.set_if_better("degree", Scored("B.E.", Provenance.INFERRED))
    fmap.set_if_better("degree", Scored("B.Tech", Provenance.STRUCTURAL))
    assert fmap.value("degree") == "B.Tech"

    # And does not regress when a weaker reading arrives afterwards.
    fmap.set_if_better("degree", Scored("B.Sc", Provenance.INFERRED))
    assert fmap.value("degree") == "B.Tech"


def test_empty_extraction_scores_zero_not_one():
    """An empty result is the worst outcome, not a perfect one — returning
    1.0 here would send the review screen's section badge green on a
    section where nothing was found."""
    assert aggregate_confidence([]) == 0.0
    assert aggregate_confidence([FieldMap()]) == 0.0


# --------------------------------------------------------------------------
# Regression
# --------------------------------------------------------------------------


def test_title_case_content_lines_do_not_become_headings():
    """REGRESSION: `_looks_like_heading` once accepted any title-case line.

    "B.Tech in Computer Science and Engineering" opened a spurious OTHER
    section immediately after the real EDUCATION heading, leaving EDUCATION
    spanning zero lines — so the section was silently dropped entirely and
    the resume parsed with no education at all.
    """
    found = _sections(WELL_FORMED)
    assert SectionKind.EDUCATION in found
    assert SectionKind.SKILLS in found

    draft = parse_resume(WELL_FORMED)
    assert draft.education, "education section was swallowed by a false heading"
    assert draft.skills, "skills section was swallowed by a false heading"


def test_document_opening_name_is_not_a_heading():
    """REGRESSION: the name line is title case and short, so it passed the
    old heading test — which consumed the header block and left the contact
    extractor with nothing to scan."""
    found = _sections(WELL_FORMED)
    assert SectionKind.HEADER in found

    draft = parse_resume(WELL_FORMED)
    assert draft.contact.value("email") is not None


def test_flat_certificate_list_splits_per_line():
    """REGRESSION: a certificates section with no blank lines, bullets or
    indentation collapsed into a single entry, so a student with five
    certificates saw one."""
    draft = parse_resume(WELL_FORMED)
    assert len(draft.certificates) == 2

    titles = {entry.value("title") for entry in draft.certificates}
    assert "Machine Learning Specialization" in titles


def test_issuer_match_is_deterministic_and_correctly_cased():
    """REGRESSION: issuers were matched by iterating a frozenset and cased
    with `.title()`.

    The entry below contains both "aws" and "amazon web services", so which
    one won varied with Python's hash seed between processes — and the
    winner was rendered "Aws".
    """
    draft = parse_resume(WELL_FORMED)
    aws_cert = next(
        entry for entry in draft.certificates if "Solutions Architect" in (entry.value("title") or "")
    )
    # Longest match wins, and it keeps the issuer's own casing.
    assert aws_cert.value("issuer") == "Amazon Web Services"


def test_bullets_do_not_split_one_role_into_many():
    """REGRESSION guard: treating each bullet as an entry is the classic
    naive-parser failure that turns one internship into four."""
    draft = parse_resume(WELL_FORMED)
    razorpay = [
        entry
        for entry in draft.experience
        if (entry.value("company_name") or "").startswith("Razorpay")
    ]
    assert len(razorpay) == 1


# --------------------------------------------------------------------------
# Taxonomy
# --------------------------------------------------------------------------


def test_short_language_names_need_a_skills_section():
    """"Go" and "C" are ordinary English tokens. Matching them in body prose
    puts fabricated languages on a verified profile."""
    prose = "Our go-to-market strategy required a C-level sign off."
    assert detect_skills(prose, in_skills_section=False) == []


def test_short_names_are_admitted_when_corroborated():
    listed = "Languages: C, C++, Java, Python"
    names = {skill.canonical for skill in detect_skills(listed, in_skills_section=True)}
    assert "C" in names
    assert "C++" in names
    assert "Java" in names


def test_canonicalise_merges_surface_forms():
    assert canonicalise("reactjs") == "React"
    assert canonicalise("React.js") == "React"
    assert canonicalise("NODEJS") == "Node.js"
    # An unknown skill keeps the student's own casing rather than being
    # lowercased into something that looks like a typo on their profile.
    assert canonicalise("Elixir") == "Elixir"


def test_longest_ngram_wins():
    names = {
        skill.canonical for skill in detect_skills("Amazon Web Services", in_skills_section=True)
    }
    assert names == {"AWS"}
