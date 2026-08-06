"""Regex library — the `EXPLICIT` provenance tier.

Everything in this module matches a format that admits essentially one
reading: an email is an email, `github.com/torvalds` names a GitHub user.
That unambiguity is what earns `Provenance.EXPLICIT`, and it is why these
patterns are deliberately conservative. A looser phone regex would match
more phone numbers *and* would start matching dates, ID numbers and
score ranges — which would not merely be wrong, it would be wrong while
claiming the highest confidence tier the product has.

WHEN IN DOUBT, MATCH LESS. A field the deterministic pass leaves empty gets
picked up by the LLM fallback and shown to the student as needing review.
A field it fills wrongly at EXPLICIT confidence is shown as green and
sails through the confirmation screen unread. The costs are not symmetric.
"""

from __future__ import annotations

import re
from datetime import date

# --------------------------------------------------------------------------
# Contact
# --------------------------------------------------------------------------

#: Intentionally not RFC 5322. The full grammar admits quoted local parts and
#: comments that no resume contains, and permitting them here would match
#: fragments of prose containing an @ sign. This covers the addresses that
#: actually appear on resumes and rejects the rest.
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

#: Requires either a + country prefix or at least 10 digits, and allows the
#: separator styles resumes use. The 10-digit floor is what keeps years,
#: percentages and "top 5%" out; without it this is the single most
#: over-matching pattern in the file.
PHONE_RE = re.compile(
    r"(?:(?<=^)|(?<=[\s:|(]))"          # start, or after whitespace/label/paren
    r"(\+\d{1,3}[\s.\-]?)?"              # optional country code
    r"(?:\(\d{2,4}\)[\s.\-]?)?"          # optional parenthesised area code
    r"\d{3,5}[\s.\-]?\d{3,5}(?:[\s.\-]?\d{2,5})?"
    r"(?=$|[\s,;|)])"
)

#: Minimum digits for a `PHONE_RE` hit to be accepted. Checked after matching
#: rather than in the pattern because counting digits across optional
#: separator groups inside one regex makes it unreadable and no faster.
PHONE_MIN_DIGITS = 10

URL_RE = re.compile(r"\bhttps?://[^\s<>\"')\]]+|(?<![@\w])www\.[^\s<>\"')\]]+", re.IGNORECASE)

# --------------------------------------------------------------------------
# Developer profile handles
# --------------------------------------------------------------------------
#
# Each pattern captures the handle only. `(?:www\.)?` rather than requiring a
# scheme, because resumes write these bare far more often than not.
#
# The trailing `(?![\w-])` on each is what stops `github.com/user/repo` from
# yielding the handle "user" *and* the repo path — the repo case is handled by
# REPO_URL_RE below, which must win.

GITHUB_USER_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)(?![\w/-])",
    re.IGNORECASE,
)

#: A GitHub URL with an owner *and* a repository. Checked before
#: `GITHUB_USER_RE` at every call site: a project's repo link is not a
#: statement about which account is the student's, and treating it as one
#: attaches the wrong username to profiles that link a fork or an org repo.
REPO_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9][\w-]*)/([\w.\-]+?)(?:\.git)?(?![\w.\-])",
    re.IGNORECASE,
)

LEETCODE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?leetcode\.com/(?:u/)?([A-Za-z0-9_\-]{2,40})(?![\w-])", re.IGNORECASE
)
CODEFORCES_RE = re.compile(
    r"(?:https?://)?(?:www\.)?codeforces\.com/profile/([A-Za-z0-9_\-.]{2,40})(?![\w-])",
    re.IGNORECASE,
)
HACKERRANK_RE = re.compile(
    r"(?:https?://)?(?:www\.)?hackerrank\.com/(?:profile/)?([A-Za-z0-9_\-]{2,40})(?![\w-])",
    re.IGNORECASE,
)
LINKEDIN_RE = re.compile(
    r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/([A-Za-z0-9\-%]{2,100})(?![\w-])",
    re.IGNORECASE,
)

#: GitHub reserves these paths; a URL hitting one names a site feature, not a
#: user. Without this list, "github.com/features" yields the handle "features".
GITHUB_RESERVED = frozenset(
    {
        "about", "apps", "blog", "collections", "contact", "customer-stories",
        "enterprise", "events", "explore", "features", "issues", "login", "marketplace",
        "new", "notifications", "orgs", "pricing", "pulls", "search", "security",
        "settings", "site", "sponsors", "topics", "trending", "watching",
    }
)

# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

#: Plausible bounds for any date on a student resume. A "graduation year" of
#: 1974 or 2098 is an extraction error — almost always a matched ID number,
#: a page footer, or a score — and admitting it would put an absurd value in
#: front of the student at high confidence.
MIN_YEAR = 1990
MAX_YEAR = date.today().year + 8

_MONTH_ALTERNATION = "|".join(sorted(_MONTHS, key=len, reverse=True))

MONTH_YEAR_RE = re.compile(rf"\b({_MONTH_ALTERNATION})\.?\s*[,\-]?\s*(\d{{4}})\b", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19[9]\d|20[0-9]\d)\b")

#: Separators used between the two ends of a range. Includes the word "to"
#: and the several dash glyphs PDF extraction produces.
_RANGE_SEP = r"(?:\s*(?:-|–|—|to|until|through)\s*)"

#: "Present"/"Current"/"Now" as a range end. Its presence is what marks a role
#: as ongoing, which `entries.py` maps to a null end date rather than to
#: today's date — recording today would make the row wrong tomorrow.
PRESENT_RE = re.compile(r"\b(present|current|currently|now|ongoing|till date|to date)\b", re.IGNORECASE)

DATE_RANGE_RE = re.compile(
    rf"({MONTH_YEAR_RE.pattern}|\b\d{{4}}\b){_RANGE_SEP}({MONTH_YEAR_RE.pattern}|\b\d{{4}}\b|{PRESENT_RE.pattern})",
    re.IGNORECASE,
)


def parse_month_year(text: str) -> date | None:
    """First month-year or bare year in `text`, as the first of that period.

    Returns the first of the month (or of January for a bare year) because
    the extraction schema wants ISO dates and a resume never states a day.
    Choosing the first is stated in the schema's own prompt rules, so the
    deterministic path and the LLM path agree on the convention rather than
    producing two different approximations of the same input.
    """
    match = MONTH_YEAR_RE.search(text)
    if match:
        month = _MONTHS[match.group(1).lower()]
        year = int(match.group(2))
        if MIN_YEAR <= year <= MAX_YEAR:
            return date(year, month, 1)
        return None

    year_match = YEAR_RE.search(text)
    if year_match:
        year = int(year_match.group(1))
        if MIN_YEAR <= year <= MAX_YEAR:
            return date(year, 1, 1)
    return None


def parse_year(text: str) -> int | None:
    """The most plausible four-digit year in `text`.

    Takes the *last* in-range year, not the first. On a graduation line the
    year that matters is the end of the range ("2021 - 2025" graduates in
    2025), and taking the first would systematically record every student's
    enrolment year as their graduation year.
    """
    candidates = [int(value) for value in YEAR_RE.findall(text)]
    valid = [year for year in candidates if MIN_YEAR <= year <= MAX_YEAR]
    return valid[-1] if valid else None


def parse_date_range(text: str) -> tuple[date | None, date | None, bool]:
    """`(start, end, is_current)` from a date range.

    `is_current` is returned separately rather than encoded as `end is None`,
    because those are different facts: "ongoing" and "the end date could not
    be read" must not collapse into one value the student cannot distinguish
    on the review screen.
    """
    match = DATE_RANGE_RE.search(text)
    if not match:
        single = parse_month_year(text)
        return single, None, bool(PRESENT_RE.search(text))

    whole = match.group(0)
    # Split on the separator to avoid the two ends' groups interleaving, which
    # they do because both alternatives contain their own capture groups.
    parts = re.split(_RANGE_SEP, whole, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        return parse_month_year(whole), None, bool(PRESENT_RE.search(whole))

    left, right = parts
    if PRESENT_RE.search(right):
        return parse_month_year(left), None, True
    return parse_month_year(left), parse_month_year(right), False


# --------------------------------------------------------------------------
# Degrees
# --------------------------------------------------------------------------

#: Canonical degree forms, mapped from the abbreviations and spellings that
#: appear in practice. The value is what gets stored; the keys are matched
#: case-insensitively against a whitespace-normalised line.
#:
#: Dotted abbreviations ("B.Tech") are handled by stripping periods before
#: lookup rather than by listing both forms, which would double this table
#: and guarantee the two halves drift.
DEGREE_FORMS: dict[str, str] = {
    "btech": "B.Tech",
    "bachelor of technology": "B.Tech",
    "be": "B.E.",
    "bachelor of engineering": "B.E.",
    "bsc": "B.Sc",
    "bachelor of science": "B.Sc",
    "bca": "BCA",
    "bachelor of computer applications": "BCA",
    "bcom": "B.Com",
    "ba": "B.A.",
    "mtech": "M.Tech",
    "master of technology": "M.Tech",
    "msc": "M.Sc",
    "master of science": "M.Sc",
    "mca": "MCA",
    "master of computer applications": "MCA",
    "mba": "MBA",
    "me": "M.E.",
    "phd": "PhD",
    "doctor of philosophy": "PhD",
    "diploma": "Diploma",
}

#: Words that mark a line as naming an institution. Checked as whole words so
#: "Institute" matches but "Institution" in prose does not carry the line.
INSTITUTION_MARKERS = frozenset(
    {
        "university", "college", "institute", "institution", "school",
        "academy", "polytechnic", "iit", "nit", "iiit", "bits", "vit", "srm",
    }
)

#: Words that mark a line as naming an employer. Used only as a weak
#: corroboration signal — plenty of companies have none of these in their
#: name, so their absence proves nothing and never lowers a score.
COMPANY_MARKERS = frozenset(
    {
        "inc", "llc", "ltd", "limited", "pvt", "private", "corp", "corporation",
        "technologies", "technology", "labs", "systems", "solutions", "software",
        "services", "consulting", "gmbh", "plc", "co",
    }
)

#: Employment-type vocabulary → the schema's enum values.
EMPLOYMENT_TYPES: dict[str, str] = {
    "intern": "internship",
    "internship": "internship",
    "trainee": "internship",
    "freelance": "freelance",
    "contract": "freelance",
    "consultant": "freelance",
    "part-time": "part_time",
    "part time": "part_time",
    "full-time": "full_time",
    "full time": "full_time",
    "permanent": "full_time",
}

#: Certificate issuers whose names are distinctive enough to match directly,
#: mapped to their correct display casing.
#:
#: A dict rather than a set for two reasons, both of which were live bugs:
#:
#: 1. **Casing.** Deriving the display name with `.title()` produced "Aws",
#:    "Ibm" and "Nptel". These are acronyms; a student's certificate list is
#:    something they show recruiters, and mangling the issuer's own name is
#:    the kind of detail that makes a generated profile look generated.
#: 2. **Determinism.** Iterating a set to find the first match gave
#:    Python-hash-dependent results whenever an entry contained two known
#:    issuers — "… | Amazon Web Services |" contains both `aws` and
#:    `amazon web services`, and which one won varied between processes.
#:    `ISSUER_KEYS_BY_LENGTH` below fixes the order, longest first, so the
#:    most specific match always wins.
KNOWN_ISSUERS: dict[str, str] = {
    "amazon web services": "Amazon Web Services",
    "linkedin learning": "LinkedIn Learning",
    "great learning": "Great Learning",
    "google cloud": "Google Cloud",
    "simplilearn": "Simplilearn",
    "pluralsight": "Pluralsight",
    "codecademy": "Codecademy",
    "coursera": "Coursera",
    "hackerrank": "HackerRank",
    "datacamp": "DataCamp",
    "microsoft": "Microsoft",
    "udacity": "Udacity",
    "kaggle": "Kaggle",
    "google": "Google",
    "oracle": "Oracle",
    "udemy": "Udemy",
    "cisco": "Cisco",
    "nptel": "NPTEL",
    "meta": "Meta",
    "edx": "edX",
    "aws": "AWS",
    "ibm": "IBM",
}

#: Match order: longest key first, so "amazon web services" is tested before
#: "aws" and the more specific issuer wins deterministically.
ISSUER_KEYS_BY_LENGTH: tuple[str, ...] = tuple(
    sorted(KNOWN_ISSUERS, key=len, reverse=True)
)


def clean_digits(text: str) -> str:
    return re.sub(r"\D", "", text)
