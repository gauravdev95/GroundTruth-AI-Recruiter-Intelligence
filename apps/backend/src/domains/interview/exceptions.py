"""Typed exceptions for the AI interview domain. See `docs/ERROR_CODES.md`."""

from __future__ import annotations

from src.core.exceptions import AppError


class RepositoryNotVerified(AppError):
    """This repository must be verified before an interview can be started."""

    status_code = 409
    code = "REPOSITORY_NOT_VERIFIED"


class InterviewAlreadyExists(AppError):
    """An interview for this repository already exists."""

    status_code = 409
    code = "INTERVIEW_ALREADY_EXISTS"


class InterviewNotReady(AppError):
    """Interview questions are still being generated."""

    status_code = 409
    code = "INTERVIEW_NOT_READY"


class InterviewFinished(AppError):
    """The conversation is over; no further turns are accepted."""

    status_code = 409
    code = "INTERVIEW_FINISHED"


class InterviewTurnInProgress(AppError):
    """A turn is already being processed for this interview.

    Raised when a second socket (or a second tab) tries to speak while the
    Interviewer is mid-response. The session row is locked for the duration of
    a turn, so this is the honest answer rather than a queue: two people typing
    into one interview is not a case worth serialising, it is a case worth
    refusing.
    """

    status_code = 409
    code = "INTERVIEW_TURN_IN_PROGRESS"


class InterviewNotComplete(AppError):
    """The interview hasn't finished evaluation yet."""

    status_code = 409
    code = "INTERVIEW_NOT_COMPLETE"
