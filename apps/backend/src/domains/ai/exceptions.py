"""Typed failures from the LLM layer.

Each maps to an explicit handling decision in the worker, which is why they are
distinct types rather than one generic error:

- `LLMTimeout` / `LLMProviderError` are **transient** — the Celery task retries
  them with backoff.
- `LLMMalformedOutput` and `LLMRefused` are **deterministic** — retrying
  produces the same result while burning quota, so the job fails immediately.
"""

from __future__ import annotations

from src.core.exceptions import AppError


class LLMError(AppError):
    """Base class for LLM service failures."""

    status_code = 502
    code = "LLM_ERROR"


class LLMNotConfigured(LLMError):
    """`GOOGLE_API_KEY` is not set, so no model-backed capability can run.

    Never retryable, and deliberately separate from the transient errors below:
    no amount of backoff produces an API key, so a worker that treated this as a
    provider fault would spend its whole retry ladder on a config mistake.
    """

    status_code = 503
    code = "LLM_NOT_CONFIGURED"


class LLMTimeout(LLMError):
    """The provider did not respond within the configured timeout. Retryable."""

    code = "LLM_TIMEOUT"


class LLMProviderError(LLMError):
    """The provider returned an error (rate limit, 5xx, connection failure). Retryable."""

    code = "LLM_PROVIDER_ERROR"


class LLMMalformedOutput(LLMError):
    """The response did not validate against the requested schema.

    Not retryable: the same prompt and schema will produce the same shape of
    failure, so the job fails and the student is told extraction did not work.
    """

    status_code = 422
    code = "LLM_MALFORMED_OUTPUT"


class LLMRefused(LLMError):
    """The model declined the request.

    Surfaced separately from a malformed response because the cause is the
    content, not the schema — retrying or re-prompting will not help.
    """

    status_code = 422
    code = "LLM_REFUSED"


class LLMOutputTruncated(LLMError):
    """The response hit the output token ceiling before completing.

    Distinct from malformed output: the schema is fine, there simply wasn't
    room. Not retried automatically — a longer resume needs a higher
    `llm_max_tokens`, not another identical attempt.
    """

    status_code = 422
    code = "LLM_OUTPUT_TRUNCATED"
