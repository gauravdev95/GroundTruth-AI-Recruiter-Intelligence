"""Google Gemini adapter for job-requirement extraction.

The step that gates the whole recruiter flow: publishing a job goes through a
mandatory confirmation screen, and that screen has nothing to confirm until
this has run. When it raises, `extract_job_requirements_task` reverts the
posting to `draft` — so a failure here is not a degraded publish, it is no
publish at all.

Everything provider-specific is in `gemini_client.py`, shared with
`gemini_extractor.py` and `gemini_interview.py`: the SDK client, the schema
dialect conversion, the error translation, and the finish-reason guard. What
stays here is what is specific to reading a job posting — the input ceiling and
the two-tag prompt shape.

The prompt and the schema live in `job_extraction_schema.py` rather than here,
next to the model the response is validated against: what a recruiter is asked
to confirm and what the system will accept are one decision, and the confirmed
output is what every future candidate is ranked against.
"""

from __future__ import annotations

import json

import pydantic
import structlog
from google.genai import types

from src.config.config import get_llm_settings
from src.domains.ai.exceptions import LLMMalformedOutput
from src.domains.ai.job_extraction_schema import (
    JOB_EXTRACTION_SYSTEM_PROMPT,
    JobRequirementExtraction,
)
from src.domains.ai.providers.gemini_client import (
    build_client,
    guard_response,
    to_gemini_schema,
    translate_api_errors,
)

logger = structlog.get_logger(__name__)

#: The same ceiling `recruiter/schemas.py::MAX_DESCRIPTION` enforces at the API
#: boundary — so in practice this only fires for descriptions that entered
#: another way (a seed script, a migration). Truncating rather than refusing
#: keeps one pathological posting from failing a recruiter's publish.
MAX_DESCRIPTION_CHARS = 20_000


class GeminiJobRequirementExtractor:
    """Implements `JobRequirementExtractor` against the Gemini API."""

    def __init__(self) -> None:
        settings = get_llm_settings()
        self._settings = settings
        self._model = settings.llm_model
        self._client = build_client(settings)

    def extract_requirements(self, *, title: str, description: str) -> JobRequirementExtraction:
        cleaned = description.strip()
        if not cleaned:
            raise LLMMalformedOutput("The job description contained no readable text")
        if len(cleaned) > MAX_DESCRIPTION_CHARS:
            logger.warning("job_description_truncated", original_chars=len(cleaned))
            cleaned = cleaned[:MAX_DESCRIPTION_CHARS]

        with translate_api_errors(noun="extraction"):
            response = self._client.models.generate_content(
                model=self._model,
                # The tags are what keep a description containing the word
                # "title:" from being read as instructions — the prompt says the
                # content is data, and the delimiters are what make that
                # checkable. Same posture as every other untrusted input here.
                contents=(
                    f"<title>\n{title.strip()}\n</title>\n\n"
                    f"<description>\n{cleaned}\n</description>"
                ),
                config=types.GenerateContentConfig(
                    system_instruction=JOB_EXTRACTION_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    # The converted schema, not the Pydantic model — Gemini
                    # rejects `additionalProperties` and `$ref`. See
                    # `gemini_client.py`; the response is still validated
                    # against the original model below.
                    response_schema=to_gemini_schema(JobRequirementExtraction),
                    max_output_tokens=self._settings.llm_max_tokens,
                    # Zero, for the same reason resume extraction uses zero:
                    # the prompt's central rule is "never invent a skill the
                    # description does not support", and sampling temperature
                    # is precisely the knob that erodes it. A hallucinated
                    # must-have here is worse than on a resume — it becomes a
                    # requirement every candidate is scored against.
                    temperature=0.0,
                ),
            )

        finish_reason = guard_response(
            response,
            refused_message="The extraction service declined to process this job description",
            truncated_message="The job description was too long to extract in full.",
        )

        raw = response.text
        if not raw:
            logger.error("llm_output_empty", finish_reason=finish_reason)
            raise LLMMalformedOutput("The extraction service returned an empty response")

        try:
            # Validated against the *original* model, so `extra="forbid"` and
            # every `max_length` still apply even though the provider was
            # handed a loosened schema.
            parsed = JobRequirementExtraction.model_validate(json.loads(raw))
        except (json.JSONDecodeError, pydantic.ValidationError) as exc:
            logger.error(
                "llm_output_unparseable",
                finish_reason=finish_reason,
                error_count=exc.error_count() if isinstance(exc, pydantic.ValidationError) else None,
            )
            raise LLMMalformedOutput(
                "The extraction service returned an unreadable response"
            ) from exc

        usage = response.usage_metadata
        logger.info(
            "job_requirements_extracted",
            model=self._model,
            input_tokens=getattr(usage, "prompt_token_count", None),
            output_tokens=getattr(usage, "candidates_token_count", None),
        )
        return parsed
