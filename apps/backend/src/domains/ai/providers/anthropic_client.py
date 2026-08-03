"""Shared Anthropic SDK client construction.

Extracted out of `anthropic_extractor.py` so `anthropic_interview.py` (the
question-generation/answer-evaluation adapters) builds its client the same
way instead of duplicating the timeout/retry configuration — this is the
"reuse the existing LLM service module, don't create a second integration
path" seam holding for a second capability. Still the only two modules in the
codebase that import the `anthropic` SDK.
"""

from __future__ import annotations

import anthropic

from src.config.config import LLMSettings, get_llm_settings


def build_client(settings: LLMSettings | None = None) -> anthropic.Anthropic:
    settings = settings or get_llm_settings()
    return anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        # Per-request wall clock. Callers' own Celery time limits are larger,
        # so a slow provider surfaces as a typed timeout error, not a killed task.
        timeout=settings.llm_timeout_seconds,
        # SDK-level retries for connection errors, 408/409/429 and 5xx. The
        # Celery task retries the whole job on top of this.
        max_retries=settings.llm_max_retries,
    )
