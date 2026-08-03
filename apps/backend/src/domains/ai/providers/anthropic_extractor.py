"""Anthropic adapter for resume extraction.

The only module in the codebase that imports the `anthropic` SDK. Everything
else depends on the `ResumeExtractor` protocol in `domains/ai/llm.py`.

Schema enforcement uses `client.messages.parse()` with a Pydantic
`output_format`: the SDK converts the model into a JSON schema, sends it as
`output_config.format`, and validates the response back into that type. That
gives a schema-shaped response from the provider *and* a second validation pass
locally, which is what turns "the model usually returns JSON" into a typed
guarantee.

Every provider exception is translated into the typed errors from
`domains/ai/exceptions.py`, because the worker's retry policy branches on
whether a failure is transient or deterministic — a leaked SDK exception would
be retried blindly.
"""

from __future__ import annotations

import anthropic
import structlog

from src.config.config import get_llm_settings
from src.domains.ai.exceptions import (
    LLMMalformedOutput,
    LLMOutputTruncated,
    LLMProviderError,
    LLMRefused,
    LLMTimeout,
)
from src.domains.ai.extraction_schema import EXTRACTION_SYSTEM_PROMPT, ResumeExtraction
from src.domains.ai.providers.anthropic_client import build_client

logger = structlog.get_logger(__name__)

# Guards the provider call rather than the model: a resume far past this is
# either not a resume or a document dump, and truncating keeps one pathological
# upload from consuming an entire context window.
MAX_INPUT_CHARS = 120_000


class AnthropicResumeExtractor:
    """Implements `ResumeExtractor` against the Anthropic Messages API."""

    def __init__(self) -> None:
        settings = get_llm_settings()
        self._settings = settings
        self._client = build_client(settings)

    def extract_resume(self, text: str) -> ResumeExtraction:
        cleaned = text.strip()
        if not cleaned:
            raise LLMMalformedOutput("The document contained no readable text")

        if len(cleaned) > MAX_INPUT_CHARS:
            logger.warning("resume_text_truncated", original_chars=len(cleaned))
            cleaned = cleaned[:MAX_INPUT_CHARS]

        try:
            response = self._client.messages.parse(
                model=self._settings.llm_model,
                max_tokens=self._settings.llm_max_tokens,
                system=EXTRACTION_SYSTEM_PROMPT,
                output_config={"effort": self._settings.llm_effort},
                output_format=ResumeExtraction,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Extract the structured data from this resume.\n\n"
                            "<resume>\n" + cleaned + "\n</resume>"
                        ),
                    }
                ],
            )
        # APITimeoutError subclasses APIConnectionError, so it must be caught first.
        except anthropic.APITimeoutError as exc:
            raise LLMTimeout("The extraction service timed out") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMProviderError("Could not reach the extraction service") from exc
        except anthropic.RateLimitError as exc:
            raise LLMProviderError("The extraction service is rate limited") from exc
        except anthropic.APIStatusError as exc:
            # 4xx other than 429 is a request defect on our side and will not
            # improve on retry; 5xx is transient.
            if exc.status_code < 500:
                raise LLMMalformedOutput(
                    f"The extraction request was rejected ({exc.status_code})"
                ) from exc
            raise LLMProviderError(f"The extraction service failed ({exc.status_code})") from exc

        # Check the stop reason before touching content: a refused or truncated
        # response can still carry partial output that would parse but be wrong.
        if response.stop_reason == "refusal":
            logger.warning("llm_refused", stop_details=str(getattr(response, "stop_details", None)))
            raise LLMRefused("The extraction service declined to process this document")

        if response.stop_reason == "max_tokens":
            raise LLMOutputTruncated(
                "The document was too long to extract in full. Try a shorter resume."
            )

        parsed = response.parsed_output
        if parsed is None:
            logger.error("llm_output_unparseable", stop_reason=response.stop_reason)
            raise LLMMalformedOutput("The extraction service returned an unreadable response")

        logger.info(
            "resume_extracted",
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        return parsed
