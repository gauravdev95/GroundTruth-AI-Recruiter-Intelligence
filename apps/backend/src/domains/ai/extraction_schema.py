"""The strict JSON schema the LLM must produce for a parsed resume.

This is the contract, in both directions: it is handed to the provider as the
output schema *and* used to validate the response. A response that doesn't
validate raises `LLMMalformedOutput` rather than reaching the database.

Two deliberate properties:

1. **Every field is optional.** A resume that omits a graduation year must not
   fail extraction — a partial draft is useful, and the student reviews it
   before anything is written. Requiring fields would push the model toward
   inventing values to satisfy the schema.
2. **Nothing here maps 1:1 to a live column.** These are *claims read off a
   document*, not profile values. The mapping into section payloads happens in
   `domains/resume/confirm.py`, only after the student confirms — so a model
   that hallucinates a degree cannot silently reach `candidate_profiles`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

MAX_ITEMS = 20
MAX_TECHNOLOGIES = 15
MAX_LINKS = 10


class _ExtractionModel(BaseModel):
    """Base for extracted objects.

    `extra="forbid"` closes the schema, which is what makes a provider's strict
    / structured-output mode enforceable rather than advisory.
    """

    model_config = ConfigDict(extra="forbid")


class ExtractedEducation(_ExtractionModel):
    institution: str | None = Field(default=None, max_length=200)
    degree: str | None = Field(default=None, max_length=200, description="e.g. B.Tech, M.Sc")
    field_of_study: str | None = Field(default=None, max_length=200, description="Branch or major")
    graduation_year: int | None = Field(default=None, ge=1900, le=2100)
    location: str | None = Field(default=None, max_length=120)


class ExtractedProject(_ExtractionModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    repo_url: str | None = Field(default=None, max_length=500, description="Only if explicitly present")
    technologies: list[str] = Field(default_factory=list, max_length=MAX_TECHNOLOGIES)


class ExtractedExperience(_ExtractionModel):
    company_name: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    employment_type: str | None = Field(
        default=None,
        max_length=40,
        description="One of: internship, freelance, part_time, full_time. Verbatim if stated.",
    )
    start_date: str | None = Field(default=None, max_length=10, description="ISO YYYY-MM-DD if determinable")
    end_date: str | None = Field(default=None, max_length=10, description="ISO YYYY-MM-DD; null if current")
    description: str | None = Field(default=None, max_length=4000)
    technologies: list[str] = Field(default_factory=list, max_length=MAX_TECHNOLOGIES)


class ExtractedCertificate(_ExtractionModel):
    title: str | None = Field(default=None, max_length=200)
    issuer: str | None = Field(default=None, max_length=200)
    issued_at: str | None = Field(default=None, max_length=10, description="ISO YYYY-MM-DD if determinable")
    credential_url: str | None = Field(default=None, max_length=500)


class ExtractedContact(_ExtractionModel):
    """Identity and contact details as the *document* states them.

    Name, email, and phone are already held on the account (`User.full_name`,
    `User.email`, `CandidateProfile.phone_number`, captured at signup and
    email-verified). They are extracted anyway because the draft is a faithful
    reading of the document, and a resume that disagrees with the account is
    something the student should see. They are deliberately *not* mapped into
    profile suggestions by `domains/resume/confirm.py` — a self-reported
    document must not be able to overwrite a verified account value.
    """

    full_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320, description="Verbatim email address")
    phone: str | None = Field(
        default=None, max_length=40, description="Verbatim phone number, including country code if written"
    )
    headline: str | None = Field(default=None, max_length=200, description="Professional summary line")
    location: str | None = Field(default=None, max_length=120)
    github_username: str | None = Field(default=None, max_length=100)
    leetcode_handle: str | None = Field(default=None, max_length=100)
    codeforces_handle: str | None = Field(default=None, max_length=100)
    hackerrank_handle: str | None = Field(default=None, max_length=100)
    links: list[str] = Field(
        default_factory=list,
        max_length=MAX_LINKS,
        description=(
            "Any other URL stated verbatim — LinkedIn, portfolio, blog, publications. "
            "Exclude URLs already captured as a handle or on a project."
        ),
    )


class ResumeExtraction(_ExtractionModel):
    """The full structured result of reading one resume."""

    contact: ExtractedContact = Field(default_factory=ExtractedContact)
    education: list[ExtractedEducation] = Field(default_factory=list, max_length=MAX_ITEMS)
    skills: list[str] = Field(default_factory=list, max_length=60)
    projects: list[ExtractedProject] = Field(default_factory=list, max_length=MAX_ITEMS)
    experience: list[ExtractedExperience] = Field(default_factory=list, max_length=MAX_ITEMS)
    certificates: list[ExtractedCertificate] = Field(default_factory=list, max_length=MAX_ITEMS)


EXTRACTION_SYSTEM_PROMPT = """\
You extract structured data from a candidate's resume.

Rules:
- Transcribe only what the document states. Never infer, complete, or invent a \
value that is not written in the text.
- If a field is absent, omit it or return null. A partial result is correct; a \
guessed one is not.
- Do not normalize or "improve" values beyond the formats requested — no \
rewriting job titles, no expanding abbreviations, no inferring a degree from a \
course name.
- Dates: return ISO YYYY-MM-DD only when the document gives enough information. \
If only a year or month is stated, use the first day of that period. If the \
period is unclear, return null rather than approximating.
- URLs: include only URLs that appear verbatim in the document.
- Return every distinct entry you find, up to the schema's limits.

The output is shown to the candidate for review before anything is saved, so \
omissions are cheap and fabrications are expensive.\
"""
