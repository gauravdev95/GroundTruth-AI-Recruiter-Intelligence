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
from src.domains.ai.interview_schema import AnswerEvaluation, GeneratedQuestionSet
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
class InterviewAnswerEvaluator(Protocol):
    """Scores one answer against the rubric, checking it against the same
    stored evidence the question was grounded in.

    The dimension *names* are fixed (`domains/ai/interview_schema.py`'s
    `RUBRIC_DIMENSIONS`, baked into the provider's structured-output schema);
    their *weights* are configurable (`InterviewSettings.rubric_weights`)."""

    def evaluate_answer(
        self, *, question: str, answer_transcript: str, repository_context: dict
    ) -> AnswerEvaluation:  # pragma: no cover - protocol
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


def get_interview_answer_evaluator() -> InterviewAnswerEvaluator:
    """The same cached instance `get_interview_question_generator` returns.

    `GeminiInterviewProvider` implements both interview protocols, so both
    capabilities share one pooled HTTP client. Two accessors rather than one
    because the callers are unrelated — questions are generated once when an
    interview starts, answers are evaluated once per submission.
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
