"""Google Gemini adapter for resume extraction.

Reached only for documents the deterministic parser (`domains/resume/
extraction/`) could not read well enough — see `jobs/tasks/resume.py`, which
escalates rather than calling this on every upload. Everything above depends
solely on the `ResumeExtractor` protocol in `domains/ai/llm.py`.

The SDK client, the Gemini schema dialect conversion, and the provider-error
translation all live in `gemini_client.py`, shared with the other adapters. See
that module for why the schema has to be converted at all, and why the response
is nonetheless validated against the *original* Pydantic model.

What stays here is the part that is specific to reading a resume: the system
prompt, the input ceiling, and `_clamp_lists`.
"""

from __future__ import annotations

import json
from typing import Any

import pydantic
import structlog
from google.genai import types

from src.config.config import get_llm_settings
from src.domains.ai.exceptions import LLMMalformedOutput
from src.domains.ai.extraction_schema import (
    EXTRACTION_SYSTEM_PROMPT,
    MAX_ITEMS,
    MAX_LINKS,
    MAX_TECHNOLOGIES,
    ResumeExtraction,
)
from src.domains.ai.providers.gemini_client import (
    _SUPPORTED_KEYWORDS,  # noqa: F401  — re-exported for tests asserting the dialect
    build_client,
    guard_response,
    to_gemini_schema,
    translate_api_errors,
)

logger = structlog.get_logger(__name__)

# Mirrors the `max_length` bounds on `extraction_schema.ResumeExtraction`.
# Applied before validation so an over-generous model costs the student a few
# trimmed rows rather than a failed extraction — every entry is reviewed and
# individually accepted anyway, so the tail is the cheapest thing to lose.
_TOP_LEVEL_CAPS = {
    "education": MAX_ITEMS,
    "projects": MAX_ITEMS,
    "experience": MAX_ITEMS,
    "certificates": MAX_ITEMS,
    "skills": 60,
}
_NESTED_LIST_CAPS = {"technologies": MAX_TECHNOLOGIES}
# `contact` is an object rather than a list, so its own list field needs its
# own pass — the loop below walks entries *inside* the top-level lists.
_CONTACT_LIST_CAPS = {"links": MAX_LINKS}


def _clamp_lists(payload: Any) -> Any:
    """Trim over-long lists to the schema's declared limits.

    Not a substitute for validation — `ResumeExtraction.model_validate` still
    runs and still rejects anything genuinely malformed. This only removes the
    one failure mode that is purely about volume.
    """
    if not isinstance(payload, dict):
        return payload

    for key, cap in _TOP_LEVEL_CAPS.items():
        value = payload.get(key)
        if isinstance(value, list) and len(value) > cap:
            logger.warning("llm_output_clamped", field=key, returned=len(value), cap=cap)
            payload[key] = value[:cap]

    for entry in (e for k in _TOP_LEVEL_CAPS for e in payload.get(k, []) or []):
        if not isinstance(entry, dict):
            continue
        for key, cap in _NESTED_LIST_CAPS.items():
            value = entry.get(key)
            if isinstance(value, list) and len(value) > cap:
                logger.warning("llm_output_clamped", field=key, returned=len(value), cap=cap)
                entry[key] = value[:cap]

    contact = payload.get("contact")
    if isinstance(contact, dict):
        for key, cap in _CONTACT_LIST_CAPS.items():
            value = contact.get(key)
            if isinstance(value, list) and len(value) > cap:
                logger.warning("llm_output_clamped", field=key, returned=len(value), cap=cap)
                contact[key] = value[:cap]

    return payload


# A resume far past this is a document dump; truncating keeps one pathological
# upload from consuming a context window.
MAX_INPUT_CHARS = 120_000


class GeminiResumeExtractor:
    """Implements `ResumeExtractor` against the Gemini API."""

    def __init__(self) -> None:
        settings = get_llm_settings()
        self._settings = settings
        self._model = settings.llm_model
        self._client = build_client(settings)

    def extract_resume(self, text: str) -> ResumeExtraction:
        cleaned = text.strip()
        if not cleaned:
            raise LLMMalformedOutput("The document contained no readable text")

        if len(cleaned) > MAX_INPUT_CHARS:
            logger.warning("resume_text_truncated", original_chars=len(cleaned))
            cleaned = cleaned[:MAX_INPUT_CHARS]

        with translate_api_errors(noun="extraction"):
            response = self._client.models.generate_content(
                model=self._model,
                contents=(
                    "Extract the structured data from this resume.\n\n"
                    "<resume>\n" + cleaned + "\n</resume>"
                ),
                config=types.GenerateContentConfig(
                    system_instruction=EXTRACTION_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    # The converted schema, not the model — see
                    # `gemini_client.py`. The model itself validates the
                    # response below.
                    response_schema=to_gemini_schema(ResumeExtraction),
                    max_output_tokens=self._settings.llm_max_tokens,
                    # Deterministic transcription, not creative writing: the
                    # prompt forbids inventing values, and sampling temperature
                    # is exactly the knob that would undermine that.
                    temperature=0.0,
                ),
            )

        finish_reason = guard_response(
            response,
            refused_message="The extraction service declined to process this document",
            truncated_message="The document was too long to extract in full. Try a shorter resume.",
        )

        # Validated against the *original* model, so `extra="forbid"` and every
        # field constraint still apply even though the provider was handed a
        # loosened schema. This is the step that makes "the model usually
        # returns the right shape" into a typed guarantee.
        raw = response.text
        if not raw:
            logger.error("llm_output_empty", finish_reason=finish_reason)
            raise LLMMalformedOutput("The extraction service returned an empty response")

        try:
            parsed = ResumeExtraction.model_validate(_clamp_lists(json.loads(raw)))
        except (json.JSONDecodeError, pydantic.ValidationError) as exc:
            logger.error(
                "llm_output_unparseable",
                finish_reason=finish_reason,
                error_count=exc.error_count(),
            )
            raise LLMMalformedOutput(
                "The extraction service returned an unreadable response"
            ) from exc

        usage = response.usage_metadata
        logger.info(
            "resume_extracted",
            model=self._model,
            input_tokens=getattr(usage, "prompt_token_count", None),
            output_tokens=getattr(usage, "candidates_token_count", None),
        )
        return parsed
