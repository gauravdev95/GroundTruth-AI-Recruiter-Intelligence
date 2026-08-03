"""Mailer backends behind one interface (`Mailer`), selected by
`MailSettings.mail_backend` with no code change at any call site.

Three backends:
- `ConsoleMailer` — logs instead of sending. Dev fallback, zero setup.
- `SMTPMailer` — real delivery via stdlib `smtplib`. Works unmodified
  against MailHog (host/port only, no auth/TLS) in dev/docker-compose and
  against a real provider in production (set `smtp_use_tls` + credentials).
- `CaptureMailer` — in-memory outbox for integration tests, so a test can
  assert a message was actually sent, to whom, and that a token embedded
  in its body really works when submitted back to the API.
"""

from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

import structlog

from src.config.config import get_mail_settings

logger = structlog.get_logger(__name__)


class Mailer(Protocol):
    def send(self, *, to_email: str, subject: str, text_body: str, html_body: str) -> None: ...


@dataclass
class CapturedMessage:
    to_email: str
    subject: str
    text_body: str
    html_body: str


class ConsoleMailer:
    def send(self, *, to_email: str, subject: str, text_body: str, html_body: str) -> None:
        logger.info("email_console", to=to_email, subject=subject, body=text_body)


class SMTPMailer:
    def send(self, *, to_email: str, subject: str, text_body: str, html_body: str) -> None:
        settings = get_mail_settings()

        message = EmailMessage()
        message["From"] = settings.smtp_from_email
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
        logger.info("email_sent", to=to_email, subject=subject)


class CaptureMailer:
    """Module-level outbox — cleared by `tests/conftest.py`'s autouse
    `_clear_mail_outbox` fixture so messages never leak across tests."""

    def __init__(self) -> None:
        self.outbox: list[CapturedMessage] = []

    def send(self, *, to_email: str, subject: str, text_body: str, html_body: str) -> None:
        self.outbox.append(
            CapturedMessage(to_email=to_email, subject=subject, text_body=text_body, html_body=html_body)
        )


_capture_mailer = CaptureMailer()


def get_mailer() -> Mailer:
    backend = get_mail_settings().mail_backend
    if backend == "smtp":
        return SMTPMailer()
    if backend == "capture":
        return _capture_mailer
    return ConsoleMailer()


def get_capture_outbox() -> list[CapturedMessage]:
    return _capture_mailer.outbox


def clear_capture_outbox() -> None:
    _capture_mailer.outbox.clear()
