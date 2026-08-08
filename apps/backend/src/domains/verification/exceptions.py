"""Typed failures from the verification layer.

Same split as `domains/ai/exceptions.py`, for the same reason:
`src/jobs/tasks/verification.py` retries transient failures with backoff and
fails deterministic ones immediately, and it branches on the exception type
to decide which. Every failure here — transient or deterministic — leaves the
claim at `UNVERIFIED`; only a completed check may write `VERIFIED`,
`REJECTED`, or `FLAGGED` (constraint §4 of the task this module implements).
"""

from __future__ import annotations

from src.core.exceptions import AppError


class VerificationError(AppError):
    """Base class for verification-check failures."""

    status_code = 502
    code = "VERIFICATION_ERROR"


class VerificationServiceUnavailable(VerificationError):
    """The third-party API timed out, refused the connection, or 5xx'd.

    Transient — the Celery task retries with backoff. On exhaustion the claim
    stays `UNVERIFIED`.
    """

    code = "VERIFICATION_SERVICE_UNAVAILABLE"


class VerificationRateLimited(VerificationServiceUnavailable):
    """The third-party API rate-limited this request. Transient."""

    code = "VERIFICATION_RATE_LIMITED"


class VerificationStatPending(VerificationServiceUnavailable):
    """GitHub answered 202: it is computing a statistic asynchronously.

    Transient like its parent — the retry ladder gives GitHub time to finish,
    which is usually enough. But *unlike* its parent it can also be permanent:
    GitHub never populates `/stats/commit_activity` for some repositories (low
    commit counts appear to be the trigger) and answers 202 indefinitely, so a
    caller that treats every 202 as "retry until it works" waits forever and
    then fails. Typed separately so a stage can retry it like any other
    transient fault and still degrade gracefully once retries are exhausted,
    rather than discarding a run over an optional signal.
    """

    code = "VERIFICATION_STAT_PENDING"


class ClaimNotFound(VerificationError):
    """The third-party identity/URL the student claimed does not exist.

    Deterministic: a GitHub username that 404s, a Codeforces handle
    `user.info` reports as unknown, a certificate URL that 404s. Not retried
    — the task resolves this to `REJECTED`, not `UNVERIFIED`, because the
    check *ran* and *disagreed* with the claim rather than failing to run.
    """

    status_code = 404
    code = "VERIFICATION_CLAIM_NOT_FOUND"
