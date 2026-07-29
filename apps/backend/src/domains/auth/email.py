"""Transactional email for the auth flows (OTP verification, password reset).

Uses stdlib smtplib so no new email-provider SDK is required. When SMTP
isn't configured (e.g. local development), messages are logged to the
console instead of sent, so the full flow is testable with zero external
accounts.
"""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

import structlog

from src.config.config import get_email_settings

logger = structlog.get_logger(__name__)


def _send(to_email: str, subject: str, text_body: str, html_body: str) -> None:
    settings = get_email_settings()

    if not settings.is_configured:
        logger.info(
            "email_dev_fallback",
            to=to_email,
            subject=subject,
            body=text_body,
        )
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls(context=context)
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)


def send_verification_otp_email(*, to_email: str, full_name: str, otp: str, expires_in_minutes: int) -> None:
    subject = "Verify your GroundTruth AI email"
    text_body = (
        f"Hi {full_name},\n\n"
        f"Your GroundTruth AI verification code is: {otp}\n"
        f"This code expires in {expires_in_minutes} minutes.\n\n"
        "If you didn't request this, you can safely ignore this email."
    )
    html_body = f"""
    <div style="font-family: -apple-system, Segoe UI, sans-serif; max-width: 480px; margin: auto;">
      <h2 style="color:#111;">Verify your email</h2>
      <p>Hi {full_name},</p>
      <p>Your GroundTruth AI verification code is:</p>
      <p style="font-size:32px; font-weight:700; letter-spacing:8px; color:#5E8BFF;">{otp}</p>
      <p style="color:#666;">This code expires in {expires_in_minutes} minutes.</p>
      <p style="color:#999; font-size:12px;">If you didn't request this, you can safely ignore this email.</p>
    </div>
    """
    _send(to_email, subject, text_body, html_body)


def send_password_reset_email(*, to_email: str, full_name: str, reset_url: str, expires_in_minutes: int) -> None:
    subject = "Reset your GroundTruth AI password"
    text_body = (
        f"Hi {full_name},\n\n"
        f"Reset your password using this link: {reset_url}\n"
        f"This link expires in {expires_in_minutes} minutes.\n\n"
        "If you didn't request this, you can safely ignore this email."
    )
    html_body = f"""
    <div style="font-family: -apple-system, Segoe UI, sans-serif; max-width: 480px; margin: auto;">
      <h2 style="color:#111;">Reset your password</h2>
      <p>Hi {full_name},</p>
      <p>Click the button below to choose a new password. This link expires in {expires_in_minutes} minutes.</p>
      <p><a href="{reset_url}" style="display:inline-block; padding:12px 24px; background:#5E8BFF; color:#fff; border-radius:8px; text-decoration:none; font-weight:600;">Reset password</a></p>
      <p style="color:#999; font-size:12px;">If you didn't request this, you can safely ignore this email.</p>
    </div>
    """
    _send(to_email, subject, text_body, html_body)
