"""structlog configuration for structured application logging.

Auth flows log security-relevant events (registration, login
success/failure, lockout, password reset, email verification) — never
passwords, tokens, or OTPs.
"""

from __future__ import annotations

import logging

import structlog


def configure_logging(*, debug: bool) -> None:
    logging.basicConfig(level=logging.INFO if not debug else logging.DEBUG, format="%(message)s")

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
