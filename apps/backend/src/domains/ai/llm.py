"""The single seam between GroundTruth and any LLM provider.

Everything above this module — the worker, the resume domain, the API — depends
only on `ResumeExtractor` and the typed errors in `exceptions.py`. No provider
SDK is imported anywhere else in the codebase, so swapping providers means
adding a module under `providers/` and changing `DEFAULT_LLM_PROVIDER`.

The protocol is deliberately narrow: one method, taking text and returning a
validated `ResumeExtraction`. Prompt construction, schema enforcement, retries,
and timeout handling are the adapter's job, because each provider expresses
them differently (tool use, JSON mode, response formats) and leaking that
choice upward would defeat the seam.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol, runtime_checkable

from src.config.config import get_embedding_settings, get_llm_settings
from src.domains.ai.exceptions import LLMNotConfigured
from src.domains.ai.extraction_schema import ResumeExtraction
from src.domains.ai.interview_schema import AnswerEvaluation, GeneratedQuestionSet
from src.domains.ai.job_extraction_schema import JobRequirementExtraction


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
    """Turns a repository's stored verification analysis into 5-7 grounded
    interview questions. See `domains/interview/service.py` for how
    `repository_context` is assembled from `Project.verification_payload`."""

    def generate_questions(
        self, *, repository_context: dict
    ) -> GeneratedQuestionSet:  # pragma: no cover - protocol
        ...


@runtime_checkable
class InterviewAnswerEvaluator(Protocol):
    """Scores one answer against the fixed four-dimension rubric, checking it
    against the same stored repository analysis the question was grounded in."""

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
    The one deliberate exception to "every capability is Anthropic" —
    `text-embedding-3-small` has no Anthropic equivalent. See
    `domains/matching/embeddings.py` for the only caller."""

    def embed(self, text: str) -> list[float]:  # pragma: no cover - protocol
        ...


@lru_cache
def get_embedder() -> Embedder:
    settings = get_embedding_settings()
    if not settings.is_configured:
        raise LLMNotConfigured("No OpenAI API key configured for the embedding service")

    from src.domains.ai.providers.openai_embedder import OpenAIEmbedder

    return OpenAIEmbedder()


def _require_configured(*, supported: tuple[str, ...]) -> str:
    """Check a key exists for the selected provider and that we adapt it.

    Returns the provider name so callers can dispatch on it. Two separate
    failures deliberately share one error type: from the caller's point of view
    "no key" and "no adapter" are both "this capability is not available", and
    both are non-retryable.
    """
    settings = get_llm_settings()
    provider = settings.default_llm_provider

    if not settings.is_configured:
        raise LLMNotConfigured(f"No API key configured for LLM provider '{provider}'")
    if provider not in supported:
        raise LLMNotConfigured(
            f"Unsupported LLM provider '{provider}' for this capability "
            f"(supported: {', '.join(supported)}). Add an adapter under "
            "src/domains/ai/providers/ and register it here."
        )
    return provider


def _require_configured_anthropic() -> None:
    _require_configured(supported=("anthropic",))


@lru_cache
def get_resume_extractor() -> ResumeExtractor:
    """Build the configured provider's adapter.

    The one capability with more than one adapter today. Both satisfy the same
    protocol and raise the same typed errors, so the worker's retry policy is
    unchanged by which is selected — that is the whole point of the seam.

    Cached because adapters hold a pooled HTTP client; rebuilding per call
    would discard connection reuse on the hottest path in the worker.
    """
    provider = _require_configured(supported=("anthropic", "google"))

    if provider == "google":
        from src.domains.ai.providers.gemini_extractor import GeminiResumeExtractor

        return GeminiResumeExtractor()

    from src.domains.ai.providers.anthropic_extractor import AnthropicResumeExtractor

    return AnthropicResumeExtractor()


@lru_cache
def _anthropic_interview_provider() -> "AnthropicInterviewProvider":  # noqa: F821
    _require_configured_anthropic()
    from src.domains.ai.providers.anthropic_interview import AnthropicInterviewProvider

    return AnthropicInterviewProvider()


def get_interview_question_generator() -> InterviewQuestionGenerator:
    """Same provider seam as `get_resume_extractor` — a second capability on
    the same Anthropic client (`providers/anthropic_client.py`), not a second
    LLM integration path."""
    return _anthropic_interview_provider()


def get_interview_answer_evaluator() -> InterviewAnswerEvaluator:
    """`AnthropicInterviewProvider` implements both interview protocols, so
    this and `get_interview_question_generator` return the exact same cached
    instance (`_anthropic_interview_provider` is the single `lru_cache`) —
    one pooled client shared by both capabilities."""
    return _anthropic_interview_provider()


@lru_cache
def get_job_requirement_extractor() -> JobRequirementExtractor:
    """A fourth capability on the same seam, same reasoning as the interview
    provider — not a second integration path."""
    _require_configured_anthropic()
    from src.domains.ai.providers.anthropic_job_extractor import AnthropicJobRequirementExtractor

    return AnthropicJobRequirementExtractor()
