"""The live interview turn engine.

    START
      -> load_context          derive the clock, clear per-cycle scratch
      -> (warmup | verify_answer)
           warmup              the opener; no answer exists yet
           verify_answer       Verifier checks the claims just made
      -> decide                clock, questions left, follow-up budget
      -> (ask_followup | bridge_next | wrapup)
      -> END                   one utterance, handed back to the caller

One invocation produces one interviewer utterance. "Listen" is not a node: it
is the gap between two invocations, for the reason set out in `state.py` —
Postgres owns the session, so the graph never has to hold a conversation open.

The graph is compiled once at import. Compilation is pure and the result is
immutable, so a single instance is shared by every concurrent interview; all
per-session data arrives in the state passed to `run_turn`.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.domains.interview.graph import nodes
from src.domains.interview.graph.state import InterviewState

__all__ = ["InterviewState", "run_turn"]


def _build():
    graph = StateGraph(InterviewState)

    graph.add_node("load_context", nodes.load_context)
    graph.add_node("warmup", nodes.warmup)
    graph.add_node("verify_answer", nodes.verify_answer)
    graph.add_node("decide", nodes.decide)
    graph.add_node("ask_followup", nodes.ask_followup)
    graph.add_node("bridge_next", nodes.bridge_next)
    graph.add_node("wrapup", nodes.wrapup)

    graph.add_edge(START, "load_context")
    graph.add_conditional_edges(
        "load_context",
        nodes.entry_route,
        {"warmup": "warmup", "verify_answer": "verify_answer"},
    )
    graph.add_edge("warmup", END)
    graph.add_edge("verify_answer", "decide")
    graph.add_conditional_edges(
        "decide",
        nodes.route,
        {
            "follow_up": "ask_followup",
            "next_question": "bridge_next",
            "wrapup": "wrapup",
        },
    )
    graph.add_edge("ask_followup", END)
    graph.add_edge("bridge_next", END)
    graph.add_edge("wrapup", END)

    return graph.compile()


#: Module-level and shared. See the note above on why this is safe.
_COMPILED = _build()


def run_turn(state: InterviewState) -> InterviewState:
    """Run one cycle and return the resulting state.

    Synchronous, and called from a thread by the socket handler rather than
    awaited: the agents underneath are the blocking `google-genai` client, and
    pretending otherwise would block the event loop for every other connected
    candidate for the length of a model call.
    """
    return _COMPILED.invoke(state)
