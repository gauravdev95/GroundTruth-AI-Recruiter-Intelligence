"""Shared Gemini SDK client construction, schema dialect, and error mapping.

Every capability's adapter — resume extraction, the two interview capabilities,
job-requirement extraction — builds its client, converts its schemas, and
translates its provider errors through this module rather than duplicating
three fiddly pieces of Gemini-specific handling four times. Adding a fifth
capability should mean a prompt and a Pydantic model, not another integration.

Together with the adapters that import it, this is the only place the
`google-genai` SDK is imported anywhere in the codebase; `domains/ai/llm.py`
documents why that boundary is kept.

The schema conversion is the load-bearing part. Pydantic models here set
`extra="forbid"`, which is emitted as `additionalProperties: false` — a key
Gemini's schema dialect rejects outright (400 INVALID_ARGUMENT), along with the
`$ref`/`$defs` indirection Pydantic uses for nested models. `to_gemini_schema`
converts a model into the subset Gemini accepts; callers then validate the
response against the *original* model. The provider gets an open schema; we
still close it, so `extra="forbid"` is enforced locally even though the
provider was never told about it.
"""

from __future__ import annotations

import contextlib
from functools import lru_cache
from typing import Any, Iterator

import pydantic
import structlog
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from src.config.config import LLMSettings, get_llm_settings
from src.domains.ai.exceptions import (
    LLMMalformedOutput,
    LLMOutputTruncated,
    LLMProviderError,
    LLMRefused,
    LLMTimeout,
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
# Pydantic model (enforced by validation in each adapter), dropping them costs
# nothing and removes a whole class of dialect breakage.
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

# Finish reasons that mean the model stopped because of the *content*, not the
# schema or the token budget. Re-prompting produces the same refusal, so these
# are deterministic failures.
_REFUSAL_REASONS = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"}


def build_client(settings: LLMSettings | None = None) -> genai.Client:
    """Build the Gemini client every adapter shares the configuration of.

    Each adapter holds its own instance so the connection pools stay per
    capability, but they are all built here so timeout and retry policy are set
    in exactly one place.
    """
    settings = settings or get_llm_settings()
    return genai.Client(
        api_key=settings.google_api_key,
        http_options=types.HttpOptions(
            # Per-request wall clock, in milliseconds. Callers' own Celery time
            # limits are deliberately larger so a slow provider surfaces as a
            # typed timeout rather than a killed task.
            timeout=int(settings.llm_timeout_seconds * 1000),
            retry_options=types.HttpRetryOptions(
                # `attempts` counts the original request, `llm_max_retries`
                # does not — so a configured 2 means one call plus two retries.
                # Defaulting to the SDK's own 5 would silently triple the worst
                # case a Celery task budgets for, since the job-level retry
                # ladder multiplies on top of this one.
                attempts=settings.llm_max_retries + 1,
            ),
        ),
    )


def _inline(node: Any, defs: dict[str, Any]) -> Any:
    """Resolve `$ref` and reduce a Pydantic JSON schema to Gemini's subset.

    Recursive rather than iterative because the schemas involved are small
    fixed trees and depth is bounded by the model definitions, not by input.
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

    Cached: the conversion is pure and the result is reused on every call.
    """
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})
    return _inline(schema, defs)


@contextlib.contextmanager
def translate_api_errors(*, noun: str) -> Iterator[None]:
    """Map `google-genai` exceptions onto the typed errors in `exceptions.py`.

    `noun` names the capability ("extraction", "interview") so the message a
    candidate eventually sees describes what actually failed.

    The distinction matters beyond wording: the workers' retry policies branch
    on whether a failure is transient or deterministic, so a leaked SDK
    exception would be retried blindly against a failure that cannot improve.
    """
    try:
        yield
    except genai_errors.ClientError as exc:
        # 429 is transient; other 4xx is a request defect on our side and will
        # not improve on retry.
        if exc.code == 429:
            raise LLMProviderError(f"The {noun} service is rate limited") from exc
        raise LLMMalformedOutput(f"The {noun} request was rejected ({exc.code})") from exc
    except genai_errors.ServerError as exc:
        raise LLMProviderError(f"The {noun} service failed ({exc.code})") from exc
    except genai_errors.APIError as exc:
        raise LLMProviderError(f"The {noun} service returned an error") from exc
    except (TimeoutError, ConnectionError) as exc:
        # The SDK surfaces transport faults as plain builtins rather than its
        # own types, so these are caught explicitly instead of falling into the
        # generic handler above as deterministic failures.
        raise LLMTimeout(f"The {noun} service timed out") from exc


def guard_response(response: Any, *, refused_message: str, truncated_message: str) -> str:
    """Reject blocked or truncated responses before their content is read.

    Returns the finish reason for logging. A blocked or truncated response can
    still carry partial output that would parse but be wrong, so this runs
    before any attempt to deserialize.
    """
    if response.prompt_feedback and response.prompt_feedback.block_reason:
        logger.warning("llm_refused", block_reason=str(response.prompt_feedback.block_reason))
        raise LLMRefused(refused_message)

    candidate = (response.candidates or [None])[0]
    finish_reason = str(getattr(candidate, "finish_reason", "") or "")

    if any(reason in finish_reason for reason in _REFUSAL_REASONS):
        logger.warning("llm_refused", finish_reason=finish_reason)
        raise LLMRefused(refused_message)

    if "MAX_TOKENS" in finish_reason:
        raise LLMOutputTruncated(truncated_message)

    return finish_reason
