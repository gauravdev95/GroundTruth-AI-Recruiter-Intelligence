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


class QuestionAlreadyAnswered(AppError):
    """This question already has a submitted answer."""

    status_code = 409
    code = "QUESTION_ALREADY_ANSWERED"


class InterviewNotComplete(AppError):
    """The interview hasn't finished evaluation yet."""

    status_code = 409
    code = "INTERVIEW_NOT_COMPLETE"
