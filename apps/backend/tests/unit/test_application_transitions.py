"""Unit tests for the Kanban pipeline's state machine
(`domains/pipeline/models.py::ALLOWED_TRANSITIONS` forward, and
`ALLOWED_ROLLBACKS` backward) — no arbitrary jumps in either direction."""

from __future__ import annotations

import pytest

from src.domains.pipeline.models import (
    ALLOWED_ROLLBACKS,
    ALLOWED_TRANSITIONS,
    ROLLBACK_FALLBACK_FROM_REJECTED,
    ApplicationStatus,
)

ALL_STATUSES = list(ApplicationStatus)


def test_every_status_has_an_entry():
    assert set(ALLOWED_TRANSITIONS.keys()) == set(ALL_STATUSES)


def test_hired_and_rejected_are_terminal():
    assert ALLOWED_TRANSITIONS[ApplicationStatus.HIRED] == frozenset()
    assert ALLOWED_TRANSITIONS[ApplicationStatus.REJECTED] == frozenset()


def test_forward_path_is_linear():
    assert ALLOWED_TRANSITIONS[ApplicationStatus.APPLIED] >= {ApplicationStatus.SHORTLISTED}
    assert ALLOWED_TRANSITIONS[ApplicationStatus.SHORTLISTED] >= {ApplicationStatus.INTERVIEW_SCHEDULED}
    assert ALLOWED_TRANSITIONS[ApplicationStatus.INTERVIEW_SCHEDULED] >= {ApplicationStatus.HIRED}


def test_rejected_is_reachable_from_every_non_terminal_stage():
    for status in (ApplicationStatus.APPLIED, ApplicationStatus.SHORTLISTED, ApplicationStatus.INTERVIEW_SCHEDULED):
        assert ApplicationStatus.REJECTED in ALLOWED_TRANSITIONS[status]


@pytest.mark.parametrize(
    "frm,to",
    [
        (ApplicationStatus.APPLIED, ApplicationStatus.HIRED),
        (ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEW_SCHEDULED),
        (ApplicationStatus.SHORTLISTED, ApplicationStatus.HIRED),
        (ApplicationStatus.HIRED, ApplicationStatus.APPLIED),
        (ApplicationStatus.REJECTED, ApplicationStatus.SHORTLISTED),
        (ApplicationStatus.INTERVIEW_SCHEDULED, ApplicationStatus.APPLIED),
    ],
)
def test_arbitrary_jumps_are_not_allowed(frm, to):
    assert to not in ALLOWED_TRANSITIONS[frm]


def test_no_status_can_transition_to_itself():
    for status, targets in ALLOWED_TRANSITIONS.items():
        assert status not in targets


# --------------------------------------------------------------------------
# Rollback (`ALLOWED_ROLLBACKS`)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    [ApplicationStatus.APPLIED, ApplicationStatus.HIRED],
    ids=["entry-state", "terminal-hire"],
)
def test_applied_and_hired_have_no_static_rollback_target(status):
    """`APPLIED` is the entry state (withdrawing is the candidate's action);
    `HIRED` is the one status with an external counterpart, and letting it
    un-happen would make `recruiter_funnel`'s cumulative conversion
    arithmetic non-monotonic."""
    assert status not in ALLOWED_ROLLBACKS


def test_rollback_reverses_the_linear_forward_path_one_step():
    assert ALLOWED_ROLLBACKS[ApplicationStatus.SHORTLISTED] is ApplicationStatus.APPLIED
    assert ALLOWED_ROLLBACKS[ApplicationStatus.INTERVIEW_SCHEDULED] is ApplicationStatus.SHORTLISTED


def test_rejected_has_no_static_target_because_it_has_three_predecessors():
    """Its target is resolved from `audit_log` at rollback time
    (`service.resolve_rollback_target`) — a static entry here would have to
    guess which of `APPLIED`/`SHORTLISTED`/`INTERVIEW_SCHEDULED` it came
    from."""
    assert ApplicationStatus.REJECTED not in ALLOWED_ROLLBACKS
    assert sum(
        1 for targets in ALLOWED_TRANSITIONS.values() if ApplicationStatus.REJECTED in targets
    ) == 3


def test_every_rollback_target_is_a_real_predecessor_on_the_forward_path():
    """A rollback may only restore a stage the application could genuinely
    have come from — it must never invent a state the forward machine can't
    produce."""
    for status, target in ALLOWED_ROLLBACKS.items():
        assert status in ALLOWED_TRANSITIONS[target]


def test_rollback_is_acyclic():
    """Rolling back can never reach a status you can roll back *to* and then
    forward from in a loop: every target is strictly earlier on the linear
    path, so following the map always terminates at `APPLIED`."""
    for status in ALLOWED_ROLLBACKS:
        seen = {status}
        current = status
        while current in ALLOWED_ROLLBACKS:
            current = ALLOWED_ROLLBACKS[current]
            assert current not in seen
            seen.add(current)
        assert current is ApplicationStatus.APPLIED


def test_rejected_fallback_is_a_status_every_application_really_passed_through():
    assert ROLLBACK_FALLBACK_FROM_REJECTED is ApplicationStatus.APPLIED
