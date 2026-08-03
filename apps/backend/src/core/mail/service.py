"""Public sending API — the one seam every domain calls through. Backend
selection (console/SMTP/capture) lives entirely in `backends.get_mailer()`;
nothing here changes when that switches.
"""

from __future__ import annotations

from src.core.mail import templates
from src.core.mail.backends import get_mailer


def _dispatch(to_email: str, rendered: tuple[str, str, str]) -> None:
    subject, text_body, html_body = rendered
    get_mailer().send(to_email=to_email, subject=subject, text_body=text_body, html_body=html_body)


def send_verification_otp_email(*, to_email: str, full_name: str, otp: str, expires_in_minutes: int) -> None:
    _dispatch(to_email, templates.verification_otp(full_name=full_name, otp=otp, expires_in_minutes=expires_in_minutes))


def send_password_reset_email(*, to_email: str, full_name: str, reset_url: str, expires_in_minutes: int) -> None:
    _dispatch(
        to_email,
        templates.password_reset(full_name=full_name, reset_url=reset_url, expires_in_minutes=expires_in_minutes),
    )


def send_stage_change_email(*, to_email: str, full_name: str, job_title: str, status_label: str, application_url: str) -> None:
    _dispatch(
        to_email,
        templates.stage_change(
            full_name=full_name, job_title=job_title, status_label=status_label, application_url=application_url
        ),
    )


def send_new_message_email(*, to_email: str, full_name: str, job_title: str, application_url: str) -> None:
    _dispatch(
        to_email,
        templates.new_message(full_name=full_name, job_title=job_title, application_url=application_url),
    )
