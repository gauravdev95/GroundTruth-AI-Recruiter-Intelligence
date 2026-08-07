"""The nodes of the live interview graph.

Every node is a pure function of `InterviewState` returning a partial state: no
node opens a database session, and no node sends anything down a socket. That
is what lets the whole conversation be tested by feeding states through the
graph with stubbed agents, and it is why persistence lives in
`domains/interview/service.py` instead — one place that writes, at one point in
the cycle, rather than five nodes each half-committing a turn.

The agent factories are imported at module scope so tests can monkeypatch
`nodes.get_live_interviewer` / `nodes.get_claim_verifier`, matching how
`jobs/tasks/*.py` are stubbed elsewhere in the suite.
"""

from __future__ import annotations

import structlog

from src.domains.ai.interview_schema import (
    MAX_FOLLOW_UPS_PER_QUESTION,
    WARMUP_INSTRUCTION,
    WRAPUP_INSTRUCTION,
)
from src.config.config import get_interview_settings
from src.domains.ai.llm import get_claim_verifier, get_live_interviewer
from src.domains.interview.graph.state import InterviewState, TurnDecision

logger = structlog.get_logger(__name__)

#: Below this many characters, an answer is treated as too thin to have
#: answered anything — the Interviewer is told to draw them out rather than
#: accept it. A blunt instrument on purpose: the alternative is a second model
#: call to judge sufficiency, on the one code path where a human is waiting.
_THIN_ANSWER_CHARS = 80

#: Hedging that, combined with short answers, reads as nerves rather than
#: ignorance. Used only to soften the Interviewer's phrasing — never scored,
#: never stored on the report. See `CandidateComfort` in `models.py`.
_HEDGE_MARKERS = (
    "i think",
    "i'm not sure",
    "im not sure",
    "not really sure",
    "maybe",
    "i guess",
    "sorry",
    "i don't remember",
    "i dont remember",
)


def _current_question(state: InterviewState) -> dict | None:
    questions = state.get("pre_generated_questions") or []
    index = state.get("current_question_index", 0)
    if 0 <= index < len(questions):
        return questions[index]
    return None


def _emit(turn, *, question_index: int | None) -> dict:
    return {
        "text": turn.interviewer_text,
        "action": turn.action,
        "internal_notes": turn.internal_notes,
        "question_index": question_index,
    }


def _read_comfort(state: InterviewState) -> str:
    """A cheap running read on how the candidate is holding up.

    Deliberately a heuristic and not a model call: it only changes how warmly
    the Interviewer phrases the next sentence, and spending a round-trip — plus
    a second opinion about a candidate's emotional state — on a delivery hint
    would be the wrong trade twice over.
    """
    answer = (state.get("latest_answer") or "").strip().lower()
    if not answer:
        return state.get("candidate_comfort", "neutral")

    hedges = sum(marker in answer for marker in _HEDGE_MARKERS)
    if len(answer) < _THIN_ANSWER_CHARS and hedges:
        return "nervous"
    if len(answer) > 400 and not hedges:
        return "confident"
    return "neutral"


def load_context(state: InterviewState) -> dict:
    """Derive the per-cycle values every downstream node reads.

    A node rather than caller-side arithmetic because `time_remaining_sec` is
    what `decide` routes on and what the Interviewer is told: computing it once,
    here, keeps the whole cycle reasoning about the same clock even though a
    cycle can span several seconds of model latency.
    """
    elapsed = state.get("time_elapsed_sec", 0.0)
    limit = state.get("time_limit_sec", 0.0)
    return {
        "time_remaining_sec": max(0, int(limit - elapsed)),
        "wrapup_threshold_sec": get_interview_settings().interview_wrapup_threshold_seconds,
        "new_flags": [],
        "emitted": None,
    }


def entry_route(state: InterviewState) -> str:
    """Which kind of cycle this is.

    The opening cycle has nothing to verify — there is no answer yet — so it
    goes straight to the Interviewer. Everything after it starts with the
    Verifier.
    """
    return "warmup" if state.get("stage") == "warmup" else "verify_answer"


def warmup(state: InterviewState) -> dict:
    """The opener. Not scored, and the only turn with no question behind it."""
    turn = get_live_interviewer().next_turn(
        repository_context=state.get("repo_analysis", {}),
        transcript=state.get("transcript", []),
        current_question=None,
        verification=None,
        time_remaining_seconds=state.get("time_remaining_sec", 0),
        candidate_name=state.get("candidate_name"),
        directive=WARMUP_INSTRUCTION,
    )
    return {
        # `main` immediately: the warmup answer is a real answer to be verified
        # like any other, it is simply not one of the generated questions.
        "stage": "main",
        "emitted": _emit(turn, question_index=None),
    }


def verify_answer(state: InterviewState) -> dict:
    """Run the Verifier over what the candidate just said.

    Sequential with the Interviewer rather than parallel with it, which is a
    deliberate departure from the design sketch: the Interviewer is *given*
    the verification result for the answer it is responding to, so running the
    two concurrently would mean either the Interviewer never sees the flags for
    the turn it is answering, or it sees the previous turn's. One extra
    round-trip buys the thing the feature is for — an interviewer that can say
    "I noticed X, how does that fit?" about what was just said.
    """
    answer = state.get("latest_answer") or ""
    question = _current_question(state)

    report = get_claim_verifier().verify_claims(
        candidate_answer=answer,
        question=question.get("prompt") if question else None,
        repository_context=state.get("repo_analysis", {}),
        previous_flags=state.get("verification_flags", []),
    )
    new_flags = [claim.model_dump() for claim in report.claims_checked]

    return {
        "new_flags": new_flags,
        "verification_flags": [*state.get("verification_flags", []), *new_flags],
        "follow_up_recommendation": report.follow_up_recommendation,
        "follow_up_suggestion": report.follow_up_suggestion,
        "candidate_comfort": _read_comfort(state),
    }


def decide(state: InterviewState) -> dict:
    """Choose this cycle's route, and record why.

    Ordering matters and is not arbitrary:

    1. The clock wins over everything. A wrapup that starts too late is a
       conversation that ends mid-sentence.
    2. Running out of questions ends the interview even with time to spare —
       padding with unplanned questions would mean asking something ungrounded,
       which is the one thing this interview may not do.
    3. Only then is the follow-up budget consulted.
    """
    stage = state.get("stage", "main")
    remaining = state.get("time_remaining_sec", 0)
    questions = state.get("pre_generated_questions") or []
    index = state.get("current_question_index", 0)
    follow_ups = state.get("follow_up_count", 0)
    recommendation = state.get("follow_up_recommendation", "sufficient")

    decision: TurnDecision
    if stage == "wrapup" or remaining <= state.get("wrapup_threshold_sec", 90):
        decision = "wrapup"
    elif index >= len(questions):
        decision = "wrapup"
    elif recommendation == "probe_deeper" and follow_ups < MAX_FOLLOW_UPS_PER_QUESTION:
        decision = "follow_up"
    else:
        decision = "next_question"

    return {"decision": decision}


def route(state: InterviewState) -> str:
    """The conditional edge. Reads `decide`'s recorded decision rather than
    re-deriving it, so what the graph did and what the state says it did cannot
    drift apart."""
    return state.get("decision", "next_question")


def ask_followup(state: InterviewState) -> dict:
    question = _current_question(state)
    suggestion = state.get("follow_up_suggestion")
    thin = len((state.get("latest_answer") or "").strip()) < _THIN_ANSWER_CHARS

    directive = (
        "Acknowledge what they just said, then follow up on it. Stay on the "
        "current question — do not move to a new one."
    )
    if thin:
        directive += (
            " Their answer was very short, so draw them out: ask them to walk "
            "you through what actually happens, concretely."
        )
    if suggestion:
        directive += f" Worth probing: {suggestion}"
    if state.get("candidate_comfort") == "nervous":
        directive += (
            " They sound unsure, so keep it easy and encouraging — make the "
            "question smaller rather than harder."
        )
    directive += " Use action=ASK_FOLLOWUP."

    turn = get_live_interviewer().next_turn(
        repository_context=state.get("repo_analysis", {}),
        transcript=state.get("transcript", []),
        current_question=question,
        verification=_verification_payload(state),
        time_remaining_seconds=state.get("time_remaining_sec", 0),
        candidate_name=state.get("candidate_name"),
        directive=directive,
    )
    return {
        "follow_up_count": state.get("follow_up_count", 0) + 1,
        "emitted": _emit(turn, question_index=state.get("current_question_index", 0)),
    }


def bridge_next(state: InterviewState) -> dict:
    """Advance to the next question, bridging from the answer just given.

    The pointer moves *before* the model call so the Interviewer is handed the
    question it is about to ask rather than the one it just finished — the
    single most common way a conversational interviewer ends up asking the same
    thing twice.
    """
    next_index = state.get("current_question_index", 0) + 1 if _has_asked(state) else 0
    questions = state.get("pre_generated_questions") or []
    question = questions[next_index] if 0 <= next_index < len(questions) else None

    if question is None:
        # Nothing left to ask. Falling through to a "next question" the graph
        # does not have would produce an invented one.
        return {**wrapup(state), "current_question_index": next_index}

    directive = (
        "Acknowledge their answer first, then bridge naturally into the next "
        "question and ask it in your own words. Use action=BRIDGE_NEXT."
        if _has_asked(state)
        else "Ask the current question in your own words. Use action=ASK_QUESTION."
    )
    if state.get("candidate_comfort") == "nervous":
        directive += " Keep the tone easy — they sound a little tense."

    turn = get_live_interviewer().next_turn(
        repository_context=state.get("repo_analysis", {}),
        transcript=state.get("transcript", []),
        current_question=question,
        verification=_verification_payload(state),
        time_remaining_seconds=state.get("time_remaining_sec", 0),
        candidate_name=state.get("candidate_name"),
        directive=directive,
    )
    return {
        "current_question_index": next_index,
        "follow_up_count": 0,
        "emitted": _emit(turn, question_index=next_index),
    }


def wrapup(state: InterviewState) -> dict:
    turn = get_live_interviewer().next_turn(
        repository_context=state.get("repo_analysis", {}),
        transcript=state.get("transcript", []),
        current_question=None,
        verification=None,
        time_remaining_seconds=state.get("time_remaining_sec", 0),
        candidate_name=state.get("candidate_name"),
        directive=WRAPUP_INSTRUCTION,
    )
    return {
        "stage": "done",
        "emitted": _emit(turn, question_index=None),
    }


def _has_asked(state: InterviewState) -> bool:
    """Has any generated question been asked yet?

    Distinguishes "the warmup just finished, ask question one" from "question
    one is done, move to question two" — both arrive at `bridge_next`, and only
    the second should advance the pointer.
    """
    return any(
        turn.get("role") == "interviewer" and turn.get("question_index") is not None
        for turn in state.get("transcript", [])
    )


def _verification_payload(state: InterviewState) -> dict | None:
    """What the Interviewer is shown about this answer's claims.

    Only the flags raised *this* cycle, and only the ones worth a question: the
    prompt already says to raise at most one, and handing over the whole
    session's history would make that instruction harder to follow, not easier.
    """
    flags = [flag for flag in state.get("new_flags", []) if flag.get("status") != "supported"]
    if not flags and not state.get("follow_up_suggestion"):
        return None
    return {
        "flags": flags,
        "recommendation": state.get("follow_up_recommendation", "sufficient"),
        "suggestion": state.get("follow_up_suggestion"),
    }
