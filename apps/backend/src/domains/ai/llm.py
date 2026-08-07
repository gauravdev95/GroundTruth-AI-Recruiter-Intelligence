"""The single seam between GroundTruth and the LLM.

Everything above this module — the workers, the resume domain, the API —
depends only on the protocols declared here and on the typed errors in
`exceptions.py`. No provider SDK is imported anywhere else in the codebase, so
the blast radius of changing vendors is this file plus the adapters under
`providers/`.

**GroundTruth calls exactly one LLM provider: Google Gemini.** There is no
provider-selection setting, no preference order, and no fallback. That is a
deliberate narrowing of an earlier design that resolved a provider per
capability at call time: the fallback could route a capability to a vendor the
operator had not named, which meant an extraction, an interview score, or a set
of job requirements could be produced by a model different from the one the
logs and the stored provenance implied. For output that is stored, ranked on,
and shown to a recruiter as evidence, "which model actually answered" is not an
operational detail worth guessing at.

Embedding is the one capability here that is not an API call at all — it runs a
local sentence-transformers model in this process (`get_embedder` below), so it
needs no key and is unaffected by whether Gemini is configured.

The protocols are deliberately narrow: each takes its inputs and returns a
validated Pydantic model. Prompt construction, schema enforcement, and error
translation are the adapter's job, because they are expressed in the provider's
own vocabulary and leaking that choice upward would defeat the seam.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from src.config.config import get_llm_settings
from src.domains.ai.exceptions import LLMNotConfigured
from src.domains.ai.extraction_schema import ResumeExtraction
from src.domains.ai.interview_schema import (
    GeneratedQuestionSet,
    InterviewerTurn,
    Scorecard,
    VerificationReport,
)
from src.domains.ai.job_extraction_schema import JobRequirementExtraction

if TYPE_CHECKING:  # pragma: no cover - the adapter is imported lazily at runtime
    from src.domains.ai.providers.gemini_interview import GeminiInterviewProvider

#: The provider name recorded as provenance on anything a model produced.
#: Stored on extraction drafts (`jobs/tasks/resume.py`) alongside the model id,
#: so a row always says what produced it — the deterministic parser or Gemini.
LLM_PROVIDER = "google"


@runtime_checkable
class ResumeExtractor(Protocol):
    """Turns resume text into validated structured data.

    Implementations must raise the typed errors from `domains.ai.exceptions`
    rather than provider-specific exceptions — the worker's retry policy
    branches on them, so a leaked SDK exception would be retried as a generic
    failure regardless of whether retrying could help.
    """

    def extract_resume(self, text: str) -> ResumeExtraction:  # pragma: no cover - protocol
        ...


@runtime_checkable
class InterviewQuestionGenerator(Protocol):
    """Turns a candidate's stored verified evidence into 5-7 grounded
    interview questions.

    `repository_context` carries either shape, distinguished by its own
    `grounding` key: one repository's analysis (`repository`), or the union of
    everything verified about the candidate (`profile`). The parameter keeps
    its original name so the adapter and every caller share one signature —
    see `domains/interview/service.py::build_interview_context`.
    """

    def generate_questions(
        self, *, repository_context: dict
    ) -> GeneratedQuestionSet:  # pragma: no cover - protocol
        ...


@runtime_checkable
class LiveInterviewer(Protocol):
    """Produces the interviewer's next utterance in a live interview.

    Called once per interviewer turn, from inside the request handling one
    candidate message — so this is the only LLM capability in the codebase on a
    latency budget a human is sitting through. Everything it needs is passed in
    per call rather than held between them: the session's authoritative state
    lives in Postgres, and an adapter holding conversation state would make a
    reconnect resume a conversation the server had forgotten.

    `directive`, when set, is a fixed instruction for this turn (open the
    interview, close it) that overrides the ordinary ask/probe/bridge decision.
    """

    def next_turn(
        self,
        *,
        repository_context: dict,
        transcript: list[dict],
        current_question: dict | None,
        verification: dict | None,
        time_remaining_seconds: int,
        candidate_name: str | None = None,
        directive: str | None = None,
    ) -> InterviewerTurn:  # pragma: no cover - protocol
        ...


@runtime_checkable
class ClaimVerifier(Protocol):
    """Checks the claims in one candidate answer against the stored analysis.

    Runs after every candidate turn and never speaks to the candidate. Its
    output steers the Interviewer's next turn and accumulates as the evidence
    the Scorer weighs at the end.
    """

    def verify_claims(
        self,
        *,
        candidate_answer: str,
        question: str | None,
        repository_context: dict,
        previous_flags: list[dict],
    ) -> VerificationReport:  # pragma: no cover - protocol
        ...


@runtime_checkable
class InterviewScorer(Protocol):
    """Scores a finished interview from its whole transcript.

    Replaces the per-answer evaluator the typed interview used: in a live
    conversation an answer is not a self-contained unit — a candidate may
    correct themselves three turns later, or answer question two while
    answering question one — so scoring per answer would systematically
    misread exactly the conversations this design exists to allow.

    The dimension *names* are fixed (`domains/ai/interview_schema.py`'s
    `RUBRIC_DIMENSIONS`, baked into the provider's structured-output schema);
    their *weights* are configurable (`InterviewSettings.rubric_weights`) and
    are applied by the caller, not by the model.
    """

    def score_interview(
        self,
        *,
        transcript: list[dict],
        verification_flags: list[dict],
        repository_context: dict,
        questions: list[dict],
    ) -> Scorecard:  # pragma: no cover - protocol
        ...


@runtime_checkable
class JobRequirementExtractor(Protocol):
    """Mines a job posting's free-text description for structured hiring
    requirements. See `domains/ai/job_extraction_schema.py`."""

    def extract_requirements(
        self, *, title: str, description: str
    ) -> JobRequirementExtraction:  # pragma: no cover - protocol
        ...


@runtime_checkable
class Embedder(Protocol):
    """Turns text into a fixed-dimension vector for the matching engine.

    The one capability here that is not an API call: it runs a local
    sentence-transformers model in this process, so it needs no key. See
    `domains/matching/embeddings.py` for the only caller.
    """

    def embed(self, text: str) -> list[float]:  # pragma: no cover - protocol
        ...


def require_llm_configured() -> str:
    """Assert Gemini is usable, and return the provider name for provenance.

    Every factory below calls this before building an adapter, so a missing key
    fails at the seam with one message naming the variable to set, rather than
    inside the SDK on the first request.

    Returns the provider name rather than `None` because callers that record
    provenance need both halves — `jobs/tasks/resume.py` writes this and
    `llm_model` onto the draft it produces, and provenance that was never
    checked against the configuration would claim an extraction the process
    could not have made.

    `LLMNotConfigured` is on the workers' non-retryable branch: no amount of
    retrying adds an API key.
    """
    if not get_llm_settings().is_configured:
        raise LLMNotConfigured(
            "No LLM API key is configured. Set GOOGLE_API_KEY in .env — "
            "GroundTruth runs on Google Gemini and has no other provider."
        )
    return LLM_PROVIDER


# The factories below are all the same shape: check configuration on every
# call, build the adapter at most once. The `lru_cache` is on the builder and
# not on the public function on purpose — the adapters hold pooled HTTP clients
# that are worth reusing, but caching the configuration check with them would
# make an unconfigured deployment raise once and then hand out a broken adapter.


@lru_cache
def _resume_extractor() -> ResumeExtractor:
    from src.domains.ai.providers.gemini_extractor import GeminiResumeExtractor

    return GeminiResumeExtractor()


@lru_cache
def _interview_provider() -> "GeminiInterviewProvider":
    # Typed as the concrete class rather than as one of the two interview
    # protocols, because it satisfies both and the accessors below narrow it.
    from src.domains.ai.providers.gemini_interview import GeminiInterviewProvider

    return GeminiInterviewProvider()


@lru_cache
def _job_requirement_extractor() -> JobRequirementExtractor:
    from src.domains.ai.providers.gemini_job_extractor import GeminiJobRequirementExtractor

    return GeminiJobRequirementExtractor()


def get_resume_extractor() -> ResumeExtractor:
    """The extractor used for resumes the deterministic parser could not read.

    Note that this is the *fallback* path, not the default one:
    `jobs/tasks/resume.py` parses every upload deterministically first and only
    escalates documents that come back thin. Most uploads never reach here.
    """
    require_llm_configured()
    return _resume_extractor()


def get_interview_question_generator() -> InterviewQuestionGenerator:
    """One capability on the shared Gemini client (`providers/gemini_client.py`),
    not a second integration path."""
    require_llm_configured()
    return _interview_provider()


def get_live_interviewer() -> LiveInterviewer:
    """The agent that speaks. Called once per interviewer turn."""
    require_llm_configured()
    return _interview_provider()


def get_claim_verifier() -> ClaimVerifier:
    """The silent agent. Called once per candidate turn."""
    require_llm_configured()
    return _interview_provider()


def get_interview_scorer() -> InterviewScorer:
    """The agent that scores. Called once, after the interview ends.

    All four interview accessors return the same cached instance:
    `GeminiInterviewProvider` implements every interview protocol, so one
    pooled HTTP client serves the whole interview. Four accessors rather than
    one because the callers are unrelated — questions are generated when the
    session is created, the Interviewer and Verifier run inside the live
    socket, and the Scorer runs in a Celery worker afterwards.
    """
    require_llm_configured()
    return _interview_provider()


def get_job_requirement_extractor() -> JobRequirementExtractor:
    """Mines a recruiter's job description for structured requirements.

    Load-bearing for the recruiter flow rather than optional: publishing a job
    goes through the confirmation screen, and the screen has nothing to confirm
    until this has run (`jobs/tasks/matching.py::extract_job_requirements_task`).
    """
    require_llm_configured()
    return _job_requirement_extractor()


@lru_cache
def get_embedder() -> Embedder:
    """Build the local embedding adapter.

    No `require_llm_configured` call, unlike everything above: the model runs
    in-process, so there is no configuration that can make embedding
    unavailable. The `lru_cache` also matters more here than it does elsewhere
    — it is what keeps a single copy of the model's weights per process instead
    of one per call.
    """
    from src.domains.ai.providers.local_embedder import LocalEmbedder

    return LocalEmbedder()
