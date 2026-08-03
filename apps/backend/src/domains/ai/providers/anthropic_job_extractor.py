"""Anthropic adapter for job-requirement extraction.

Third structured-extraction capability on the shared client
(`providers/anthropic_client.py`), same shape as
`anthropic_extractor.py` (resume) — schema-constrained `messages.parse()`,
typed error translation, nothing else in the codebase importing the
`anthropic` SDK.
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
from src.domains.ai.job_extraction_schema import JOB_EXTRACTION_SYSTEM_PROMPT, JobRequirementExtraction
from src.domains.ai.providers.anthropic_client import build_client

logger = structlog.get_logger(__name__)

MAX_DESCRIPTION_CHARS = 20_000


class AnthropicJobRequirementExtractor:
    def __init__(self) -> None:
        settings = get_llm_settings()
        self._settings = settings
        self._client = build_client(settings)

    def extract_requirements(self, *, title: str, description: str) -> JobRequirementExtraction:
        cleaned = description.strip()
        if not cleaned:
            raise LLMMalformedOutput("The job description contained no readable text")
        if len(cleaned) > MAX_DESCRIPTION_CHARS:
            logger.warning("job_description_truncated", original_chars=len(cleaned))
            cleaned = cleaned[:MAX_DESCRIPTION_CHARS]

        try:
            response = self._client.messages.parse(
                model=self._settings.llm_model,
                max_tokens=self._settings.llm_max_tokens,
                system=JOB_EXTRACTION_SYSTEM_PROMPT,
                output_config={"effort": self._settings.llm_effort},
                output_format=JobRequirementExtraction,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"<title>\n{title.strip()}\n</title>\n\n"
                            f"<description>\n{cleaned}\n</description>"
                        ),
                    }
                ],
            )
        except anthropic.APITimeoutError as exc:
            raise LLMTimeout("The extraction service timed out") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMProviderError("Could not reach the extraction service") from exc
        except anthropic.RateLimitError as exc:
            raise LLMProviderError("The extraction service is rate limited") from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code < 500:
                raise LLMMalformedOutput(
                    f"The extraction request was rejected ({exc.status_code})"
                ) from exc
            raise LLMProviderError(f"The extraction service failed ({exc.status_code})") from exc

        if response.stop_reason == "refusal":
            logger.warning("llm_refused", stop_details=str(getattr(response, "stop_details", None)))
            raise LLMRefused("The extraction service declined to process this job description")
        if response.stop_reason == "max_tokens":
            raise LLMOutputTruncated("The job description was too long to extract in full.")

        parsed = response.parsed_output
        if parsed is None:
            logger.error("llm_output_unparseable", stop_reason=response.stop_reason)
            raise LLMMalformedOutput("The extraction service returned an unreadable response")

        logger.info(
            "job_requirements_extracted",
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        return parsed
