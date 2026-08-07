"""The state one turn of a live interview is computed from.

**Postgres owns this state; the graph borrows it.** The graph is compiled once
and invoked with a fully-populated `InterviewState` built from the `interviews`
row and its turns, and its result is written straight back. There is no
LangGraph checkpointer, deliberately: a checkpointer would make the graph a
second store of session state alongside the tables that already hold the
transcript, the flags and the question pointer, and the two would disagree the
first time a candidate's socket dropped mid-turn. With the database as the only
store, a reconnect rebuilds the state from rows that were committed, and a turn
that failed halfway simply did not happen.

The cost of that choice is that the graph cannot suspend inside itself waiting
for the candidate to speak — "listen" is not a node here, it is the gap between
two invocations. Each invocation is therefore one *cycle*: given whatever the
candidate just said (or nothing, for the opening), produce the interviewer's
next utterance and the bookkeeping that goes with it.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

#: What `decide` concluded should happen next. Stored on the state rather than
#: returned, so a transcript's routing is inspectable after the fact.
TurnDecision = Literal["follow_up", "next_question", "wrapup"]


class InterviewState(TypedDict, total=False):
    """One cycle's inputs and outputs.

    `total=False` because the graph fills most of it in: the caller supplies
    the loaded session, the nodes supply everything derived from this turn.
    """

    # -- identity ----------------------------------------------------------
    candidate_id: str
    session_id: str
    candidate_name: str | None

    # -- grounding, loaded once per cycle ----------------------------------
    repo_analysis: dict[str, Any]
    pre_generated_questions: list[dict[str, Any]]

    # -- the conversation so far -------------------------------------------
    transcript: list[dict[str, Any]]
    current_question_index: int
    follow_up_count: int

    # -- this cycle's input -------------------------------------------------
    #: What the candidate just said. `None` opens the interview.
    latest_answer: str | None

    # -- verification --------------------------------------------------------
    #: Everything flagged in the session so far, passed to the Verifier so it
    #: does not re-flag a claim the candidate keeps repeating.
    verification_flags: list[dict[str, Any]]
    #: Flagged during *this* cycle. The caller persists these; keeping them
    #: separate is what stops a retried cycle writing the same flag twice.
    new_flags: list[dict[str, Any]]
    follow_up_recommendation: Literal["probe_deeper", "sufficient", "move_on"]
    follow_up_suggestion: str | None

    # -- flow control --------------------------------------------------------
    stage: Literal["warmup", "main", "wrapup", "done"]
    time_elapsed_sec: float
    time_limit_sec: float
    time_remaining_sec: int
    #: How little time may remain before the graph heads for the close.
    #: Resolved from config once per cycle in `load_context` rather than read
    #: inside `decide`, so one cycle cannot route on two different thresholds.
    wrapup_threshold_sec: int
    candidate_comfort: Literal["confident", "neutral", "nervous"]
    decision: TurnDecision

    # -- this cycle's output --------------------------------------------------
    #: The interviewer's utterance: `text`, `action`, `internal_notes`,
    #: `question_index`. The caller turns this into an `InterviewTurn` row and
    #: sends the text down the socket.
    emitted: dict[str, Any] | None
