"""Google Gemini adapter for resume extraction.

The only module in the codebase that imports the `google-genai` SDK, mirroring
`anthropic_extractor.py`'s role for Anthropic. Everything above depends solely
on the `ResumeExtractor` protocol in `domains/ai/llm.py`.

Schema enforcement is a two-step, and the split is the interesting part.
`ResumeExtraction` cannot be handed to Gemini directly: it sets
`extra="forbid"`, which Pydantic emits as `additionalProperties: false`, and
Gemini's schema dialect rejects that key outright (400 INVALID_ARGUMENT). It
also rejects the `$ref`/`$defs` indirection Pydantic uses for nested models.

So `to_gemini_schema` converts the model into the subset Gemini accepts —
inlining `$defs`, collapsing `T | None` into `nullable`, dropping unsupported
keywords — and the response is then validated locally with the *original*
model. The provider gets an open schema; we still close it. That is strictly
stronger than trusting either side alone: `extra="forbid"` is enforced here
even though the provider was never told about it.

Every provider exception is translated into the typed errors from
`domains/ai/exceptions.py`, because the worker's retry policy branches on
whether a failure is transient or deterministic (`jobs/tasks/resume.py`). A
leaked SDK exception would be retried blindly against a failure that cannot
improve.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import pydantic
import structlog
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from src.config.config import get_llm_settings
from src.domains.ai.exceptions import (
    LLMMalformedOutput,
    LLMOutputTruncated,
    LLMProviderError,
    LLMRefused,
    LLMTimeout,
)
from src.domains.ai.extraction_schema import (
    EXTRACTION_SYSTEM_PROMPT,
    MAX_ITEMS,
    MAX_TECHNOLOGIES,
    ResumeExtraction,
)

logger = structlog.get_logger(__name__)

# The JSON Schema keywords Gemini's structured-output mode understands.
# Anything else — `additionalProperties`, `maxLength`, `title`, `default`,
# `$schema` — is either rejected or silently ignored, so it is dropped rather
# than sent and hoped for.
#
# `maxItems`/`minItems` are deliberately absent despite being individually
# supported. Gemini rejects the *combination* of a bounded array whose item
# objects contain another bounded array — `projects[maxItems:20]` each holding
# `technologies[maxItems:15]` — with a bare 400 INVALID_ARGUMENT naming no
# field. Either bound alone is accepted; both together are not. Since these are
# advisory hints to the model and the real ceiling is `max_length` on the
# Pydantic model (enforced by `_clamp_lists` plus validation below), dropping
# them costs nothing and removes a whole class of dialect breakage.
_SUPPORTED_KEYWORDS = frozenset(
    {
        "type",
        "format",
        "description",
        "nullable",
        "enum",
        "items",
        "properties",
        "required",
        "anyOf",
        "propertyOrdering",
    }
)

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

    return payload


def _inline(node: Any, defs: dict[str, Any]) -> Any:
    """Resolve `$ref` and reduce a Pydantic JSON schema to Gemini's subset.

    Recursive rather than iterative because the schema is a small fixed tree
    (six models, one level of nesting) and depth is bounded by the model
    definitions, not by input.
    """
    if isinstance(node, list):
        return [_inline(item, defs) for item in node]
    if not isinstance(node, dict):
        return node

    if "$ref" in node:
        # "#/$defs/ExtractedProject" -> defs["ExtractedProject"]
        return _inline(defs[node["$ref"].rsplit("/", 1)[-1]], defs)

    # Pydantic renders `str | None` as `anyOf: [{type: string}, {type: null}]`.
    # Gemini expresses the same thing as `nullable` on the type itself, and
    # rejects a null-typed branch.
    if "anyOf" in node:
        branches = [_inline(b, defs) for b in node["anyOf"]]
        concrete = [b for b in branches if b.get("type") != "null"]
        if len(concrete) == 1 and len(concrete) < len(branches):
            resolved = dict(concrete[0])
            resolved["nullable"] = True
            if "description" in node:
                resolved.setdefault("description", node["description"])
            return resolved

    cleaned: dict[str, Any] = {}
    for key, value in node.items():
        if key not in _SUPPORTED_KEYWORDS:
            continue

        if key == "properties":
            # The keys here are *field names*, not schema keywords. Filtering
            # them against `_SUPPORTED_KEYWORDS` like the rest would strip every
            # field and leave an empty object — which the model dutifully
            # returns as `{}`.
            cleaned[key] = {name: _inline(sub, defs) for name, sub in value.items()}
        elif key in {"items", "anyOf"}:
            cleaned[key] = _inline(value, defs)
        else:
            cleaned[key] = value

    return cleaned


@lru_cache
def to_gemini_schema(model: type[pydantic.BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic model into a Gemini-acceptable response schema.

    Cached: the conversion is pure and the result is reused on every extraction.
    """
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})
    return _inline(schema, defs)

# Same ceiling as the Anthropic adapter: a resume far past this is a document
# dump, and truncating keeps one pathological upload from consuming a context
# window.
MAX_INPUT_CHARS = 120_000

# Finish reasons that mean the model stopped because of the *content*, not the
# schema or the token budget. Re-prompting produces the same refusal, so these
# are deterministic failures.
_REFUSAL_REASONS = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"}


class GeminiResumeExtractor:
    """Implements `ResumeExtractor` against the Gemini API."""

    def __init__(self) -> None:
        settings = get_llm_settings()
        self._settings = settings
        self._model = settings.resume_extraction_model
        self._client = genai.Client(
            api_key=settings.google_api_key,
            http_options=types.HttpOptions(
                # Per-request wall clock, in milliseconds. The worker's own time
                # limit is deliberately larger so a slow provider surfaces as a
                # typed timeout rather than a killed task.
                timeout=int(settings.llm_timeout_seconds * 1000),
            ),
        )

    def extract_resume(self, text: str) -> ResumeExtraction:
        cleaned = text.strip()
        if not cleaned:
            raise LLMMalformedOutput("The document contained no readable text")

        if len(cleaned) > MAX_INPUT_CHARS:
            logger.warning("resume_text_truncated", original_chars=len(cleaned))
            cleaned = cleaned[:MAX_INPUT_CHARS]

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=(
                    "Extract the structured data from this resume.\n\n"
                    "<resume>\n" + cleaned + "\n</resume>"
                ),
                config=types.GenerateContentConfig(
                    system_instruction=EXTRACTION_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    # The converted schema, not the model — see the module
                    # docstring. The model itself validates the response below.
                    response_schema=to_gemini_schema(ResumeExtraction),
                    max_output_tokens=self._settings.llm_max_tokens,
                    # Deterministic transcription, not creative writing: the
                    # prompt forbids inventing values, and sampling temperature
                    # is exactly the knob that would undermine that.
                    temperature=0.0,
                ),
            )
        except genai_errors.ClientError as exc:
            # 429 is transient; other 4xx is a request defect on our side and
            # will not improve on retry.
            if exc.code == 429:
                raise LLMProviderError("The extraction service is rate limited") from exc
            raise LLMMalformedOutput(
                f"The extraction request was rejected ({exc.code})"
            ) from exc
        except genai_errors.ServerError as exc:
            raise LLMProviderError(f"The extraction service failed ({exc.code})") from exc
        except genai_errors.APIError as exc:
            raise LLMProviderError("The extraction service returned an error") from exc
        except (TimeoutError, ConnectionError) as exc:
            # The SDK surfaces transport faults as plain builtins rather than
            # its own types, so these are caught explicitly instead of falling
            # into the generic handler below as deterministic failures.
            raise LLMTimeout("The extraction service timed out") from exc

        # Inspect why generation stopped before touching content: a blocked or
        # truncated response can still carry partial output that would parse
        # but be wrong.
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            logger.warning("llm_refused", block_reason=str(response.prompt_feedback.block_reason))
            raise LLMRefused("The extraction service declined to process this document")

        candidate = (response.candidates or [None])[0]
        finish_reason = str(getattr(candidate, "finish_reason", "") or "")

        if any(reason in finish_reason for reason in _REFUSAL_REASONS):
            logger.warning("llm_refused", finish_reason=finish_reason)
            raise LLMRefused("The extraction service declined to process this document")

        if "MAX_TOKENS" in finish_reason:
            raise LLMOutputTruncated(
                "The document was too long to extract in full. Try a shorter resume."
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
