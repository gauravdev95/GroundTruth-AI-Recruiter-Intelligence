"""Google Gemini adapter for interview question generation and answer evaluation.

Implements both `InterviewQuestionGenerator` and `InterviewAnswerEvaluator`
(`domains/ai/llm.py`) in one class over one shared client
(`providers/gemini_client.py`). One class rather than two because the two
capabilities are halves of the same conversation — the evaluator has to judge
an answer against the very evidence the generator wrote the question from, so
splitting them would mean two clients holding the same context for one
interview.

The prompts and the rubric live in `interview_schema.py`, not here: the rubric
weights are operator-configurable and the dimension names are baked into the
stored scores, so the prompt and the schema have to move together.

`repository_context` (a plain `dict`) is always sent as clearly-delimited
`<repository_analysis>` data, and an answer transcript as `<answer>` data —
never concatenated into the system prompt or treated as instructions. Both
system prompts additionally tell the model to ignore any instruction-shaped
text found inside that data. This is the same data-not-instructions posture the
rest of the codebase takes with untrusted resume text, applied to two more
untrusted inputs: repository content (indirectly, via the stored analysis) and
candidate-authored free text.

Structured output works the way it does in `gemini_extractor.py`: the schema
Gemini is handed is a loosened conversion, and the response is validated
locally against the original Pydantic model. See `gemini_client.py`.
"""

from __future__ import annotations

import json

import pydantic
import structlog
from google.genai import types

from src.config.config import get_llm_settings
from src.domains.ai.exceptions import LLMMalformedOutput
from src.domains.ai.interview_schema import (
    INTERVIEW_EVALUATION_SYSTEM_PROMPT,
    INTERVIEW_GENERATION_SYSTEM_PROMPT,
    RUBRIC_DIMENSIONS,
    AnswerEvaluation,
    GeneratedQuestionSet,
)
from src.domains.ai.providers.gemini_client import (
    build_client,
    guard_response,
    to_gemini_schema,
    translate_api_errors,
)

logger = structlog.get_logger(__name__)

# A stored analysis far past the first ceiling is not adding grounding, and
# anything past the second is not an answer given under an interview timer.
MAX_CONTEXT_CHARS = 40_000
MAX_ANSWER_CHARS = 8_000

# Zero for both capabilities, and for two different reasons.
#
# Evaluation: the same answer must score the same. A sampled rubric score would
# make an interview result partly a dice roll, and `interview_score` feeds a
# candidate's match ranking.
#
# Generation: a candidate can start a new interview after a failed one, so a
# sampled question set turns a retry into a reroll for easier questions. Fixing
# the temperature makes the question set a property of the repository rather
# than of how many attempts someone was willing to burn.
_TEMPERATURE = 0.0


class GeminiInterviewProvider:
    """Implements `InterviewQuestionGenerator` and `InterviewAnswerEvaluator`."""

    def __init__(self) -> None:
        settings = get_llm_settings()
        self._settings = settings
        self._model = settings.llm_model
        self._client = build_client(settings)

    def generate_questions(self, *, repository_context: dict) -> GeneratedQuestionSet:
        context_json = json.dumps(repository_context, default=str)[:MAX_CONTEXT_CHARS]

        with translate_api_errors(noun="interview"):
            response = self._client.models.generate_content(
                model=self._model,
                contents=(
                    "Write interview questions grounded in this repository analysis.\n\n"
                    "<repository_analysis>\n" + context_json + "\n</repository_analysis>"
                ),
                config=types.GenerateContentConfig(
                    system_instruction=INTERVIEW_GENERATION_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=to_gemini_schema(GeneratedQuestionSet),
                    max_output_tokens=self._settings.llm_max_tokens,
                    temperature=_TEMPERATURE,
                ),
            )

        finish_reason = guard_response(
            response,
            refused_message="The interview service declined to complete question generation",
            truncated_message="The question generation response was too long to complete.",
        )
        return self._parsed(
            response, GeneratedQuestionSet, what="question generation", finish_reason=finish_reason
        )

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

        with translate_api_errors(noun="interview"):
            response = self._client.models.generate_content(
                model=self._model,
                contents=(
                    "<question>\n" + question + "\n</question>\n\n"
                    "<answer>\n" + answer + "\n</answer>\n\n"
                    "<repository_analysis>\n" + context_json + "\n</repository_analysis>"
                ),
                config=types.GenerateContentConfig(
                    system_instruction=INTERVIEW_EVALUATION_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=to_gemini_schema(AnswerEvaluation),
                    max_output_tokens=self._settings.llm_max_tokens,
                    temperature=_TEMPERATURE,
                ),
            )

        finish_reason = guard_response(
            response,
            refused_message="The interview service declined to complete answer evaluation",
            truncated_message="The answer evaluation response was too long to complete.",
        )
        evaluation = self._parsed(
            response, AnswerEvaluation, what="answer evaluation", finish_reason=finish_reason
        )

        # Pydantic can constrain the list's length but not "one of each literal
        # value", so the completeness check lives here. The scorer weights every
        # dimension in `rubric_weights`, so a response missing one would produce
        # an interview score silently short of its own scale rather than an error.
        found = {score.dimension for score in evaluation.scores}
        if found != set(RUBRIC_DIMENSIONS):
            raise LLMMalformedOutput(
                f"Evaluation covered dimensions {sorted(found)}, expected exactly {sorted(RUBRIC_DIMENSIONS)}"
            )
        return evaluation

    def _parsed(self, response, model, *, what: str, finish_reason: str):
        """Validate against the *original* model, so `extra="forbid"` and every
        field constraint still apply even though the provider was handed a
        loosened schema."""
        raw = response.text
        if not raw:
            logger.error("llm_output_empty", what=what, finish_reason=finish_reason)
            raise LLMMalformedOutput(f"The interview service returned an empty {what} response")

        try:
            return model.model_validate(json.loads(raw))
        except (json.JSONDecodeError, pydantic.ValidationError) as exc:
            logger.error(
                "llm_output_unparseable",
                what=what,
                finish_reason=finish_reason,
                error_count=exc.error_count() if isinstance(exc, pydantic.ValidationError) else None,
            )
            raise LLMMalformedOutput(
                f"The interview service returned an unreadable {what} response"
            ) from exc
