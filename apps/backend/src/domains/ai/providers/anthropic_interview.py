"""Anthropic adapter for interview question generation and answer evaluation.

Implements both `InterviewQuestionGenerator` and `InterviewAnswerEvaluator`
(`domains/ai/llm.py`) in one class over one shared client
(`providers/anthropic_client.py`) — the second capability on the same
provider seam `anthropic_extractor.py` established for resume extraction,
not a second LLM integration path (constraint on the task that added this
module).

`repository_context` (a plain `dict`) is always sent as clearly-delimited
`<repository_analysis>` data, and an answer transcript as `<answer>` data —
never concatenated into the system prompt or treated as instructions. Both
system prompts (`interview_schema.py`) additionally tell the model to ignore
any instruction-shaped text found inside that data. This is the same
data-not-instructions posture `resume/parsing.py` + `extraction_schema.py`
already take with untrusted resume text, applied to two more untrusted
inputs: repository content (indirectly, via the stored analysis) and
candidate-authored free text.
"""

from __future__ import annotations

import functools
import json

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
from src.domains.ai.interview_schema import (
    INTERVIEW_EVALUATION_SYSTEM_PROMPT,
    INTERVIEW_GENERATION_SYSTEM_PROMPT,
    RUBRIC_DIMENSIONS,
    AnswerEvaluation,
    GeneratedQuestionSet,
)
from src.domains.ai.providers.anthropic_client import build_client

logger = structlog.get_logger(__name__)

MAX_CONTEXT_CHARS = 40_000
MAX_ANSWER_CHARS = 8_000


def _handle_provider_errors(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except anthropic.APITimeoutError as exc:
            raise LLMTimeout("The interview service timed out") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMProviderError("Could not reach the interview service") from exc
        except anthropic.RateLimitError as exc:
            raise LLMProviderError("The interview service is rate limited") from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code < 500:
                raise LLMMalformedOutput(f"The interview request was rejected ({exc.status_code})") from exc
            raise LLMProviderError(f"The interview service failed ({exc.status_code})") from exc

    return wrapper


class AnthropicInterviewProvider:
    def __init__(self) -> None:
        settings = get_llm_settings()
        self._settings = settings
        self._client = build_client(settings)

    @_handle_provider_errors
    def generate_questions(self, *, repository_context: dict) -> GeneratedQuestionSet:
        context_json = json.dumps(repository_context, default=str)[:MAX_CONTEXT_CHARS]

        response = self._client.messages.parse(
            model=self._settings.llm_model,
            max_tokens=self._settings.llm_max_tokens,
            system=INTERVIEW_GENERATION_SYSTEM_PROMPT,
            output_config={"effort": self._settings.llm_effort},
            output_format=GeneratedQuestionSet,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Write interview questions grounded in this repository analysis.\n\n"
                        "<repository_analysis>\n" + context_json + "\n</repository_analysis>"
                    ),
                }
            ],
        )
        return self._parsed(response, what="question generation")

    @_handle_provider_errors
    def evaluate_answer(
        self, *, question: str, answer_transcript: str, repository_context: dict
    ) -> AnswerEvaluation:
        context_json = json.dumps(repository_context, default=str)[:MAX_CONTEXT_CHARS]
        answer = answer_transcript.strip()[:MAX_ANSWER_CHARS]
        if not answer:
            # An empty/whitespace-only answer is a valid submission (the
            # candidate ran out of time with nothing written) — score it
            # directly rather than sending an empty prompt to the model,
            # which has no useful signal to evaluate.
            return AnswerEvaluation(
                scores=[
                    {
                        "dimension": dimension,
                        "score": 0.0,
                        "rationale": "No answer was submitted before time expired.",
                    }
                    for dimension in RUBRIC_DIMENSIONS
                ]
            )

        response = self._client.messages.parse(
            model=self._settings.llm_model,
            max_tokens=self._settings.llm_max_tokens,
            system=INTERVIEW_EVALUATION_SYSTEM_PROMPT,
            output_config={"effort": self._settings.llm_effort},
            output_format=AnswerEvaluation,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "<question>\n" + question + "\n</question>\n\n"
                        "<answer>\n" + answer + "\n</answer>\n\n"
                        "<repository_analysis>\n" + context_json + "\n</repository_analysis>"
                    ),
                }
            ],
        )
        evaluation = self._parsed(response, what="answer evaluation")

        found = {score.dimension for score in evaluation.scores}
        if found != set(RUBRIC_DIMENSIONS):
            raise LLMMalformedOutput(
                f"Evaluation covered dimensions {sorted(found)}, expected exactly {sorted(RUBRIC_DIMENSIONS)}"
            )
        return evaluation

    def _parsed(self, response, *, what: str):
        if response.stop_reason == "refusal":
            logger.warning("llm_refused", what=what, stop_details=str(getattr(response, "stop_details", None)))
            raise LLMRefused(f"The interview service declined to complete {what}")
        if response.stop_reason == "max_tokens":
            raise LLMOutputTruncated(f"The {what} response was too long to complete.")
        parsed = response.parsed_output
        if parsed is None:
            logger.error("llm_output_unparseable", what=what, stop_reason=response.stop_reason)
            raise LLMMalformedOutput(f"The interview service returned an unreadable {what} response")
        return parsed
