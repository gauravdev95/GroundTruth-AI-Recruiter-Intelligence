"""The configuration gate in `domains/ai/llm.py`.

GroundTruth calls exactly one LLM provider. These tests pin the two properties
that follow from that and are easy to regress: every model-backed capability
refuses to build without `GOOGLE_API_KEY`, and every one of them is built
against Gemini rather than something that merely satisfies the protocol.

The refusal half is the one worth asserting directly. `LLMNotConfigured` is on
the workers' *non-retryable* branch — a capability that failed to raise it here
would instead fail somewhere inside the SDK, get classified as a transient
provider fault, and burn the whole Celery retry ladder waiting for an API key to
appear.

`get_llm_settings` is `lru_cache`d, so every test clears it after overriding the
environment — otherwise the first test to build settings would fix them for the
whole module.
"""

from __future__ import annotations

import pytest

from src.config.config import LLMSettings, get_llm_settings
from src.domains.ai.exceptions import LLMNotConfigured
from src.domains.ai.llm import (
    LLM_PROVIDER,
    _interview_provider,
    _job_requirement_extractor,
    _resume_extractor,
    get_interview_answer_evaluator,
    get_interview_question_generator,
    get_job_requirement_extractor,
    get_resume_extractor,
    require_llm_configured,
)

#: The public factories, paired with the adapter class each must return.
#: Parametrising over the list rather than writing four near-identical tests is
#: what makes a fifth capability's factory fail loudly if it skips the gate.
CAPABILITIES = [
    ("resume extraction", get_resume_extractor, "GeminiResumeExtractor"),
    ("question generation", get_interview_question_generator, "GeminiInterviewProvider"),
    ("answer evaluation", get_interview_answer_evaluator, "GeminiInterviewProvider"),
    ("job extraction", get_job_requirement_extractor, "GeminiJobRequirementExtractor"),
]


@pytest.fixture
def llm_settings(monkeypatch):
    """Build `LLMSettings` from explicit keyword overrides, bypassing .env.

    `_env_file=None` matters: without it pydantic-settings would still read the
    developer's real `apps/backend/.env`, so a machine with a `GOOGLE_API_KEY`
    set would quietly pass the "no key configured" tests.

    Each adapter reads `get_llm_settings` through its *own* module namespace, so
    the override is applied there too — patching only `llm.py` would pass the
    gate and then build the adapter against the developer's real key.
    """

    def _apply(**overrides):
        settings = LLMSettings(_env_file=None, **overrides)
        for module in (
            "src.domains.ai.llm",
            "src.domains.ai.providers.gemini_client",
            "src.domains.ai.providers.gemini_extractor",
            "src.domains.ai.providers.gemini_interview",
            "src.domains.ai.providers.gemini_job_extractor",
        ):
            monkeypatch.setattr(f"{module}.get_llm_settings", lambda: settings)
        return settings

    yield _apply
    get_llm_settings.cache_clear()
    # The adapters hold pooled HTTP clients, so an instance built under one
    # test's fake key would leak into the next.
    _resume_extractor.cache_clear()
    _interview_provider.cache_clear()
    _job_requirement_extractor.cache_clear()


# ==========================================================================
# The configuration gate
# ==========================================================================


def test_configured_deployment_resolves_to_google(llm_settings):
    llm_settings(google_api_key="g")
    assert require_llm_configured() == LLM_PROVIDER == "google"


def test_raises_without_a_key(llm_settings):
    """The message names the variable to set, because this is the error an
    operator sees when a resume upload or a job publish fails."""
    llm_settings()
    with pytest.raises(LLMNotConfigured, match="GOOGLE_API_KEY"):
        require_llm_configured()


@pytest.mark.parametrize(
    "capability,factory",
    [(name, factory) for name, factory, _ in CAPABILITIES],
    ids=[name for name, _, _ in CAPABILITIES],
)
def test_every_capability_refuses_to_build_without_a_key(llm_settings, capability, factory):
    llm_settings()
    with pytest.raises(LLMNotConfigured):
        factory()


@pytest.mark.parametrize(
    "capability,factory",
    [(name, factory) for name, factory, _ in CAPABILITIES],
    ids=[name for name, _, _ in CAPABILITIES],
)
def test_the_gate_is_not_cached_with_the_adapter(llm_settings, capability, factory):
    """A configured process that loses its key must start failing again.

    The adapters are `lru_cache`d for their pooled HTTP clients; the gate is
    deliberately outside that cache. Without the split, one successful call
    would hand out a working adapter forever — which is exactly what would
    happen in a worker that built its client before an operator rotated a key
    to an empty value.
    """
    llm_settings(google_api_key="g")
    factory()

    llm_settings()
    with pytest.raises(LLMNotConfigured):
        factory()


# ==========================================================================
# What actually gets built
# ==========================================================================


@pytest.mark.parametrize(
    "capability,factory,expected",
    CAPABILITIES,
    ids=[name for name, _, _ in CAPABILITIES],
)
def test_every_capability_is_backed_by_gemini(llm_settings, capability, factory, expected):
    """Asserted by class name rather than `isinstance` against the protocol:
    the protocols are `runtime_checkable`, so a structural match would pass for
    any object with the right method and prove nothing about which vendor ran.
    """
    llm_settings(google_api_key="g")
    assert type(factory()).__name__ == expected


def test_both_interview_capabilities_share_one_instance(llm_settings):
    """One pooled client for the pair, not two.

    They are halves of one interview — the evaluator judges answers against the
    same stored evidence the generator wrote the questions from — so a second
    client would be pure overhead.
    """
    llm_settings(google_api_key="g")
    assert get_interview_question_generator() is get_interview_answer_evaluator()


# ==========================================================================
# Model selection
# ==========================================================================


def test_model_defaults_to_gemini(llm_settings):
    settings = llm_settings(google_api_key="g")
    assert settings.llm_model == "gemini-3.6-flash"


def test_model_is_overridable(llm_settings):
    """The one knob that matters operationally: pinning a different Gemini id
    (a Pro model for accuracy, a pinned snapshot for reproducibility) without a
    code change."""
    settings = llm_settings(google_api_key="g", llm_model="gemini-3.6-pro")
    assert settings.llm_model == "gemini-3.6-pro"


def test_is_configured_tracks_the_key(llm_settings):
    assert llm_settings(google_api_key="g").is_configured is True
    assert llm_settings().is_configured is False
