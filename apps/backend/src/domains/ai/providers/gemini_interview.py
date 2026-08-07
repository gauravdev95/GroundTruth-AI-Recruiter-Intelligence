"""Google Gemini adapter for the live code-grounded AI interview.

Implements all four interview protocols from `domains/ai/llm.py` —
`InterviewQuestionGenerator`, `LiveInterviewer`, `ClaimVerifier` and
`InterviewScorer` — in one class over one shared client
(`providers/gemini_client.py`). One class rather than four because they are
stages of the same conversation: the Verifier judges an answer against the very
evidence the generator wrote the question from, and the Scorer weighs both.
Splitting them would mean four clients holding the same context for one
interview.

The prompts and the rubric live in `interview_schema.py`, not here: the rubric
weights are operator-configurable and the dimension names are baked into the
stored scores, so the prompt and the schema have to move together.

`repository_context` (a plain `dict`) is always sent as clearly-delimited
`<repository_analysis>` data, the conversation as `<transcript>` data, and a
candidate's words as `<candidate_answer>` data — never concatenated into the
system prompt or treated as instructions. Every system prompt additionally
tells the model to ignore instruction-shaped text found inside that data. This
is the same data-not-instructions posture the rest of the codebase takes with
untrusted resume text, and it matters more here than it did for the one-shot
evaluator it replaces: in a live interview the candidate gets several turns to
try, and the Interviewer's reply is read straight back to them, so an injection
attempt is both iterable and visible.

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
    INTERVIEW_GENERATION_SYSTEM_PROMPT,
    INTERVIEWER_SYSTEM_PROMPT,
    RUBRIC_DIMENSIONS,
    SCORER_SYSTEM_PROMPT,
    VERIFIER_SYSTEM_PROMPT,
    GeneratedQuestionSet,
    InterviewerTurn,
    Scorecard,
    VerificationReport,
)
from src.domains.ai.providers.gemini_client import (
    build_client,
    guard_response,
    to_gemini_schema,
    translate_api_errors,
)

logger = structlog.get_logger(__name__)

# A stored analysis far past the first ceiling is not adding grounding.
MAX_CONTEXT_CHARS = 40_000
# One candidate utterance. Generous for speech, and still a bound.
MAX_ANSWER_CHARS = 8_000
# The rolling conversation window sent to the Interviewer and the Verifier.
# The Scorer gets its own, larger budget — it must see the whole interview to
# judge it, whereas a mid-interview turn only needs recent context plus the
# questions it is working through.
MAX_TRANSCRIPT_CHARS = 12_000
MAX_SCORING_TRANSCRIPT_CHARS = 60_000

# Zero everywhere the output is a judgement, for the reasons the typed
# interview already established:
#
# Scoring: the same interview must score the same. A sampled rubric score would
# make a result partly a dice roll, and it feeds a candidate's match ranking.
#
# Verification: whether the analysis supports a claim is a question about the
# data, not a matter of taste.
#
# Generation: a candidate can start a new interview after a failed one, so a
# sampled question set turns a retry into a reroll for easier questions.
_TEMPERATURE_DETERMINISTIC = 0.0

# ...and non-zero for the one agent that talks. This is the deliberate
# exception: an interviewer whose acknowledgement of the same answer is
# identical every time reads as a script, and "doesn't feel like a form" is the
# entire point of the live rewrite. Nothing scored is sampled — the Interviewer
# produces conversation, the Scorer produces the result, and they are different
# calls.
_TEMPERATURE_CONVERSATIONAL = 0.8


def _render_transcript(transcript: list[dict], *, budget: int) -> str:
    """Render turns as `role: text`, keeping the most recent within `budget`.

    Trims from the front, not the back: the last few turns are what the next
    utterance has to be coherent with, so an over-long interview loses its
    opening rather than the thing just said. The questions are passed
    separately and are never part of what gets trimmed, so dropping early turns
    cannot lose track of what still has to be asked.
    """
    rendered: list[str] = []
    used = 0
    for turn in reversed(transcript):
        line = f"{turn.get('role', 'unknown')}: {turn.get('text', '')}".strip()
        if used + len(line) > budget:
            break
        rendered.append(line)
        used += len(line) + 1
    return "\n".join(reversed(rendered))


def _block(tag: str, body: str) -> str:
    return f"<{tag}>\n{body}\n</{tag}>"


class GeminiInterviewProvider:
    """Implements every interview protocol in `domains/ai/llm.py`."""

    def __init__(self) -> None:
        settings = get_llm_settings()
        self._settings = settings
        self._model = settings.llm_model
        self._client = build_client(settings)

    # -- InterviewQuestionGenerator -----------------------------------------

    def generate_questions(self, *, repository_context: dict) -> GeneratedQuestionSet:
        context_json = json.dumps(repository_context, default=str)[:MAX_CONTEXT_CHARS]

        generated = self._generate(
            contents=(
                "Write interview questions grounded in this repository analysis.\n\n"
                + _block("repository_analysis", context_json)
            ),
            system_prompt=INTERVIEW_GENERATION_SYSTEM_PROMPT,
            schema=GeneratedQuestionSet,
            temperature=_TEMPERATURE_DETERMINISTIC,
            what="question generation",
        )
        return self._parsed(generated,GeneratedQuestionSet, what="question generation")

    # -- LiveInterviewer ----------------------------------------------------

    def next_turn(
        self,
        *,
        repository_context: dict,
        transcript: list[dict],
        current_question: dict | None,
        verification: dict | None,
        time_remaining_seconds: int,
        candidate_name: str | None = None,
        directive: str | None = None,
    ) -> InterviewerTurn:
        context_json = json.dumps(repository_context, default=str)[:MAX_CONTEXT_CHARS]

        parts = [
            _block("repository_analysis", context_json),
            _block("transcript", _render_transcript(transcript, budget=MAX_TRANSCRIPT_CHARS)),
        ]
        if candidate_name:
            parts.append(_block("candidate_first_name", candidate_name))
        if current_question is not None:
            parts.append(_block("current_question", json.dumps(current_question, default=str)))
        if verification is not None:
            # Sent as data the Interviewer may draw on, with the prompt's
            # instruction to raise at most one and never as an accusation. The
            # recommendation rides along inside it rather than as a separate
            # field, so the Interviewer sees the advice next to the evidence
            # that produced it.
            parts.append(_block("verification", json.dumps(verification, default=str)))
        parts.append(_block("time_remaining_seconds", str(max(0, time_remaining_seconds))))
        # Last, so a fixed instruction for this turn is the most recent thing
        # the model reads before answering.
        parts.append(
            _block("turn_instruction", directive)
            if directive
            else "Respond with your next turn in the interview."
        )

        generated = self._generate(
            contents="\n\n".join(parts),
            system_prompt=INTERVIEWER_SYSTEM_PROMPT,
            schema=InterviewerTurn,
            temperature=_TEMPERATURE_CONVERSATIONAL,
            what="interviewer turn",
        )
        return self._parsed(generated,InterviewerTurn, what="interviewer turn")

    # -- ClaimVerifier ------------------------------------------------------

    def verify_claims(
        self,
        *,
        candidate_answer: str,
        question: str | None,
        repository_context: dict,
        previous_flags: list[dict],
    ) -> VerificationReport:
        answer = candidate_answer.strip()[:MAX_ANSWER_CHARS]
        if not answer:
            # Silence, or a candidate who said nothing substantive. There is no
            # claim to check, and sending an empty answer to the model would
            # spend a call to be told so.
            return VerificationReport(follow_up_recommendation="probe_deeper")

        context_json = json.dumps(repository_context, default=str)[:MAX_CONTEXT_CHARS]
        parts = [
            _block("repository_analysis", context_json),
            _block("candidate_answer", answer),
        ]
        if question:
            parts.append(_block("question_asked", question))
        if previous_flags:
            # So the Verifier does not re-flag the same claim on every
            # subsequent turn — a candidate who mentions Redis four times
            # should not accumulate four identical flags for the Scorer to
            # mistake for four separate problems.
            parts.append(
                _block("already_flagged", json.dumps(previous_flags[-20:], default=str))
            )

        generated = self._generate(
            contents="\n\n".join(parts),
            system_prompt=VERIFIER_SYSTEM_PROMPT,
            schema=VerificationReport,
            temperature=_TEMPERATURE_DETERMINISTIC,
            what="claim verification",
        )
        return self._parsed(generated,VerificationReport, what="claim verification")

    # -- InterviewScorer ----------------------------------------------------

    def score_interview(
        self,
        *,
        transcript: list[dict],
        verification_flags: list[dict],
        repository_context: dict,
        questions: list[dict],
    ) -> Scorecard:
        context_json = json.dumps(repository_context, default=str)[:MAX_CONTEXT_CHARS]
        contents = "\n\n".join(
            [
                _block("repository_analysis", context_json),
                _block("questions", json.dumps(questions, default=str)),
                _block(
                    "transcript",
                    _render_transcript(transcript, budget=MAX_SCORING_TRANSCRIPT_CHARS),
                ),
                _block("verification_flags", json.dumps(verification_flags, default=str)),
                "Score this interview against the four rubric dimensions.",
            ]
        )

        generated = self._generate(
            contents=contents,
            system_prompt=SCORER_SYSTEM_PROMPT,
            schema=Scorecard,
            temperature=_TEMPERATURE_DETERMINISTIC,
            what="interview scoring",
        )
        scorecard = self._parsed(generated, Scorecard, what="interview scoring")

        # Pydantic can constrain the list's length but not "one of each literal
        # value", so the completeness check lives here. The caller weights every
        # dimension in `rubric_weights`, so a response missing one would produce
        # an interview score silently short of its own scale rather than an error.
        found = {dimension.dimension for dimension in scorecard.dimensions}
        if found != set(RUBRIC_DIMENSIONS):
            raise LLMMalformedOutput(
                f"Scoring covered dimensions {sorted(found)}, expected exactly {sorted(RUBRIC_DIMENSIONS)}"
            )
        return scorecard

    # -- shared -------------------------------------------------------------

    def _generate(
        self,
        *,
        contents: str,
        system_prompt: str,
        schema: type[pydantic.BaseModel],
        temperature: float,
        what: str,
    ):
        with translate_api_errors(noun="interview"):
            response = self._client.models.generate_content(
                model=self._model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=to_gemini_schema(schema),
                    max_output_tokens=self._settings.llm_max_tokens,
                    temperature=temperature,
                ),
            )

        finish_reason = guard_response(
            response,
            refused_message=f"The interview service declined to complete {what}",
            truncated_message=f"The {what} response was too long to complete.",
        )
        return response, finish_reason

    def _parsed(self, generated, model, *, what: str):
        """Validate against the *original* model, so `extra="forbid"` and every
        field constraint still apply even though the provider was handed a
        loosened schema."""
        response, finish_reason = generated
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
