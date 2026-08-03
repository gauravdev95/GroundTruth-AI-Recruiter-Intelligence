"""Per-mail-type content. Every template returns `(subject, text_body,
html_body)` — the text body is a real plain-text rendering, not an
afterthought, since `SMTPMailer` sends it as the `text/plain` alternative
(RFC 2046) alongside the HTML part.
"""

from __future__ import annotations

_WRAP = """
<div style="font-family: -apple-system, Segoe UI, sans-serif; max-width: 480px; margin: auto;">
  {inner}
  <p style="color:#999; font-size:12px; margin-top:24px;">If you didn't expect this email, you can safely ignore it.</p>
</div>
"""


def verification_otp(*, full_name: str, otp: str, expires_in_minutes: int) -> tuple[str, str, str]:
    subject = "Verify your GroundTruth AI email"
    text = (
        f"Hi {full_name},\n\n"
        f"Your GroundTruth AI verification code is: {otp}\n"
        f"This code expires in {expires_in_minutes} minutes.\n\n"
        "If you didn't request this, you can safely ignore this email."
    )
    html = _WRAP.format(
        inner=f"""
      <h2 style="color:#111;">Verify your email</h2>
      <p>Hi {full_name},</p>
      <p>Your GroundTruth AI verification code is:</p>
      <p style="font-size:32px; font-weight:700; letter-spacing:8px; color:#5E8BFF;">{otp}</p>
      <p style="color:#666;">This code expires in {expires_in_minutes} minutes.</p>
    """
    )
    return subject, text, html


def password_reset(*, full_name: str, reset_url: str, expires_in_minutes: int) -> tuple[str, str, str]:
    subject = "Reset your GroundTruth AI password"
    text = (
        f"Hi {full_name},\n\n"
        f"Reset your password using this link: {reset_url}\n"
        f"This link expires in {expires_in_minutes} minutes.\n\n"
        "If you didn't request this, you can safely ignore this email."
    )
    html = _WRAP.format(
        inner=f"""
      <h2 style="color:#111;">Reset your password</h2>
      <p>Hi {full_name},</p>
      <p>Click the button below to choose a new password. This link expires in {expires_in_minutes} minutes.</p>
      <p><a href="{reset_url}" style="display:inline-block; padding:12px 24px; background:#5E8BFF; color:#fff; border-radius:8px; text-decoration:none; font-weight:600;">Reset password</a></p>
    """
    )
    return subject, text, html


def stage_change(*, full_name: str, job_title: str, status_label: str, application_url: str) -> tuple[str, str, str]:
    subject = f"Update on your application: {job_title}"
    text = (
        f"Hi {full_name},\n\n"
        f"Your application for \"{job_title}\" has moved to: {status_label}.\n"
        f"View it here: {application_url}\n"
    )
    html = _WRAP.format(
        inner=f"""
      <h2 style="color:#111;">Application update</h2>
      <p>Hi {full_name},</p>
      <p>Your application for <strong>{job_title}</strong> has moved to:</p>
      <p style="font-size:20px; font-weight:700; color:#5E8BFF;">{status_label}</p>
      <p><a href="{application_url}" style="color:#5E8BFF;">View application</a></p>
    """
    )
    return subject, text, html


def new_message(*, full_name: str, job_title: str, application_url: str) -> tuple[str, str, str]:
    subject = f"New message about {job_title}"
    text = (
        f"Hi {full_name},\n\n"
        f"You have a new message regarding \"{job_title}\".\n"
        f"View it here: {application_url}\n"
    )
    html = _WRAP.format(
        inner=f"""
      <h2 style="color:#111;">New message</h2>
      <p>Hi {full_name},</p>
      <p>You have a new message regarding <strong>{job_title}</strong>.</p>
      <p><a href="{application_url}" style="color:#5E8BFF;">View conversation</a></p>
    """
    )
    return subject, text, html
