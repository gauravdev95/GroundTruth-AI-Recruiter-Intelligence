"""Unit tests for the live interview turn engine
(`domains/interview/graph/`).

Both agents are stubbed. This is not a test of the LLM — it is a test of the
routing: who speaks first, when a follow-up is allowed, when the question
pointer advances, and what makes the conversation head for the exit. Those are
the rules a candidate's experience actually turns on, and every one of them is
a pure function of the state, which is exactly why the nodes were kept free of
database work.
"""

from __future__ import annotations

import pytest

from src.domains.ai.interview_schema import (
    MAX_FOLLOW_UPS_PER_QUESTION,
    ClaimCheck,
    InterviewerTurn,
    VerificationReport,
)
from src.domains.interview.graph import run_turn


class _StubInterviewer:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def next_turn(self, **kwargs) -> InterviewerTurn:
        self.calls.append(kwargs)
        directive = kwargs.get("directive") or ""
        # Echo back whichever action the directive asked for, so the assertions
        # below are about routing rather than about a stub's opinion.
        if "action=ASK_FOLLOWUP" in directive:
            action = "ASK_FOLLOWUP"
        elif "action=BRIDGE_NEXT" in directive:
            action = "BRIDGE_NEXT"
        elif "action=WRAPUP" in directive:
            action = "WRAPUP"
        else:
            action = "ASK_QUESTION"
        return InterviewerTurn(interviewer_text="So, walk me through it.", action=action, internal_notes="noted")


class _StubVerifier:
    def __init__(self, recommendation: str = "sufficient", claims: list[ClaimCheck] | None = None) -> None:
        self.recommendation = recommendation
        self.claims = claims or []
        self.calls = 0

    def verify_claims(self, **_kwargs) -> VerificationReport:
        self.calls += 1
        return VerificationReport(
            claims_checked=self.claims,
            follow_up_recommendation=self.recommendation,
            follow_up_suggestion="Ask about the retry policy" if self.recommendation == "probe_deeper" else None,
        )


QUESTIONS = [
    {"sequence": i, "prompt": f"Question {i}?", "grounded_in": {"description": f"file_{i}.py"},
     "expected_signals": ["names the module", "explains the tradeoff"]}
    for i in range(1, 4)
]


@pytest.fixture()
def agents(monkeypatch):
    """Install stub agents and hand both back for assertions."""

    def _install(recommendation: str = "sufficient", claims: list[ClaimCheck] | None = None):
        interviewer = _StubInterviewer()
        verifier = _StubVerifier(recommendation, claims)
        monkeypatch.setattr("src.domains.interview.graph.nodes.get_live_interviewer", lambda: interviewer)
        monkeypatch.setattr("src.domains.interview.graph.nodes.get_claim_verifier", lambda: verifier)
        return interviewer, verifier

    return _install


def _state(**overrides) -> dict:
    base = {
        "candidate_id": "c",
        "session_id": "s",
        "candidate_name": "Priya",
        "repo_analysis": {"title": "retry-service", "grounding": "repository"},
        "pre_generated_questions": QUESTIONS,
        "transcript": [],
        "current_question_index": 0,
        "follow_up_count": 0,
        "latest_answer": "We use exponential backoff because a fixed delay hammers a failing service.",
        "verification_flags": [],
        "stage": "main",
        "time_elapsed_sec": 60.0,
        "time_limit_sec": 600.0,
        "candidate_comfort": "neutral",
    }
    return {**base, **overrides}


def _asked(index: int) -> list[dict]:
    """A transcript in which questions up to `index` have been asked."""
    turns: list[dict] = [{"role": "interviewer", "text": "Hey, tell me about this project.", "question_index": None}]
    for i in range(index + 1):
        turns.append({"role": "interviewer", "text": f"Question {i}?", "question_index": i})
        turns.append({"role": "candidate", "text": "An answer.", "question_index": i})
    return turns


# --- who speaks first -------------------------------------------------------


def test_warmup_opens_without_running_the_verifier(agents):
    """Nothing has been said yet, so there is no claim to check. Running the
    Verifier on the opening turn would spend a model call on an empty string."""
    _, verifier = agents()

    result = run_turn(_state(stage="warmup", latest_answer=None))

    assert result["emitted"]["action"] == "ASK_QUESTION"
    assert result["emitted"]["question_index"] is None
    assert result["stage"] == "main"
    assert verifier.calls == 0


def test_first_real_question_does_not_skip_question_one(agents):
    """The warmup answer arrives with the pointer still at 0. Advancing on it
    would mean question one is never asked — the single most damaging
    off-by-one available in this flow."""
    agents()

    warmup_only = [
        {"role": "interviewer", "text": "Tell me about the project.", "question_index": None},
        {"role": "candidate", "text": "It retries failed webhooks.", "question_index": None},
    ]
    result = run_turn(_state(transcript=warmup_only))

    assert result["current_question_index"] == 0
    assert result["emitted"]["question_index"] == 0


# --- follow-ups -------------------------------------------------------------


def test_probe_deeper_asks_a_follow_up_and_holds_the_question(agents):
    interviewer, _ = agents(recommendation="probe_deeper")

    result = run_turn(_state(transcript=_asked(0)))

    assert result["emitted"]["action"] == "ASK_FOLLOWUP"
    assert result["follow_up_count"] == 1
    assert result["emitted"]["question_index"] == 0
    assert "Ask about the retry policy" in interviewer.calls[-1]["directive"]


def test_follow_up_budget_is_capped(agents):
    """Two follow-ups is the budget. A third would let one question eat an
    interview that has five more to get through."""
    agents(recommendation="probe_deeper")

    result = run_turn(
        _state(transcript=_asked(0), follow_up_count=MAX_FOLLOW_UPS_PER_QUESTION)
    )

    assert result["emitted"]["action"] == "BRIDGE_NEXT"
    assert result["current_question_index"] == 1
    assert result["follow_up_count"] == 0


def test_sufficient_answer_bridges_to_the_next_question(agents):
    agents(recommendation="sufficient")

    result = run_turn(_state(transcript=_asked(0)))

    assert result["emitted"]["action"] == "BRIDGE_NEXT"
    assert result["current_question_index"] == 1


# --- heading for the exit ---------------------------------------------------


def test_running_out_of_time_wraps_up_even_with_questions_left(agents):
    """The clock outranks the question list. A wrapup that starts too late is a
    conversation that ends mid-sentence."""
    agents(recommendation="probe_deeper")

    result = run_turn(
        _state(transcript=_asked(0), time_elapsed_sec=560.0, time_limit_sec=600.0)
    )

    assert result["emitted"]["action"] == "WRAPUP"
    assert result["stage"] == "done"


def test_running_out_of_questions_wraps_up_even_with_time_left(agents):
    """Padding with unplanned questions would mean asking something ungrounded,
    which is the one thing this interview may not do."""
    agents(recommendation="sufficient")

    result = run_turn(
        _state(
            transcript=_asked(len(QUESTIONS) - 1),
            current_question_index=len(QUESTIONS) - 1,
            time_elapsed_sec=10.0,
        )
    )

    assert result["emitted"]["action"] == "WRAPUP"
    assert result["stage"] == "done"


# --- what the interviewer is shown ------------------------------------------


def test_supported_claims_are_not_offered_to_the_interviewer(agents):
    """A verified claim is evidence for the Scorer, not a thing to raise
    mid-conversation. Handing it over invites "I checked, and you were right",
    which is not how a senior engineer talks."""
    interviewer, _ = agents(
        recommendation="sufficient",
        claims=[ClaimCheck(claim="uses Redis", evidence="cache.py imports redis", status="supported")],
    )

    run_turn(_state(transcript=_asked(0)))

    assert interviewer.calls[-1]["verification"] is None


def test_contradicted_claims_reach_the_interviewer(agents):
    interviewer, _ = agents(
        recommendation="probe_deeper",
        claims=[
            ClaimCheck(
                claim="rate limiting middleware",
                evidence="no rate limiting found in middleware/",
                status="contradicted",
                severity="notable",
            )
        ],
    )

    run_turn(_state(transcript=_asked(0)))

    verification = interviewer.calls[-1]["verification"]
    assert verification is not None
    assert verification["flags"][0]["claim"] == "rate limiting middleware"


def test_flags_accumulate_across_the_session(agents):
    """The caller persists `new_flags` only, but the Verifier is handed the
    running total so it does not re-flag a claim the candidate keeps
    repeating."""
    agents(claims=[ClaimCheck(claim="uses Redis", evidence="cache.py imports redis", status="supported")])

    existing = [{"claim": "earlier claim", "evidence": "somewhere", "status": "supported", "severity": "none"}]
    result = run_turn(_state(transcript=_asked(0), verification_flags=existing))

    assert len(result["new_flags"]) == 1
    assert len(result["verification_flags"]) == 2


# --- comfort ----------------------------------------------------------------


def test_a_short_hedged_answer_reads_as_nervous(agents):
    """A delivery hint, never a score. It only softens the next question's
    phrasing — see `CandidateComfort` in `models.py`."""
    agents(recommendation="probe_deeper")

    result = run_turn(_state(transcript=_asked(0), latest_answer="I think? sorry, not sure"))

    assert result["candidate_comfort"] == "nervous"
