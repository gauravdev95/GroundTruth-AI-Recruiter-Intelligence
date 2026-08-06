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


def verification_summary(
    *,
    full_name: str,
    confirmed: list[str],
    needs_attention: list[tuple[str, str]],
    profile_url: str,
) -> tuple[str, str, str]:
    """Sent once, when every check a candidate submitted has settled.

    One template, two outcomes, because they are the same email with a
    different centre of gravity — a candidate whose GitHub verified and whose
    certificate 404'd needs both facts in one message, and splitting them into
    "success" and "failure" mails would send that candidate two.

    `needs_attention` carries `(claim, reason)` pairs and every entry is
    actionable by design: the subject names the state, the body names the
    reason, and the link goes to the section that fixes it. A summary that says
    "verification failed" without saying which claim or why is a notification
    the candidate can do nothing with.

    Note what is *not* claimed here: a candidate with no failures is told their
    checks passed, never that their profile is now visible. Visibility
    additionally requires the AI interview, which has its own email
    (`interview_invitation`), and promising it here would leave them waiting.
    """
    all_good = not needs_attention
    subject = (
        "Your GroundTruth profile checks are complete"
        if all_good
        else "Some of your GroundTruth claims need attention"
    )

    confirmed_lines = "\n".join(f"  - {item}" for item in confirmed) or "  - (nothing yet)"
    attention_lines = "\n".join(f"  - {claim}: {reason}" for claim, reason in needs_attention)

    text = f"Hi {full_name},\n\nWe've finished checking what you submitted.\n\n"
    text += f"Confirmed:\n{confirmed_lines}\n"
    if not all_good:
        text += (
            f"\nNeeds your attention:\n{attention_lines}\n\n"
            "Fixing these is worth doing — recruiters see verified evidence, and an "
            "unconfirmed claim carries no weight in matching.\n"
        )
    text += f"\nReview your profile: {profile_url}\n"

    confirmed_html = "".join(f"<li>{item}</li>" for item in confirmed) or "<li>Nothing yet</li>"
    attention_html = "".join(
        f"<li><strong>{claim}</strong> — {reason}</li>" for claim, reason in needs_attention
    )
    attention_block = (
        ""
        if all_good
        else f"""
      <h3 style="color:#111; margin-bottom:4px;">Needs your attention</h3>
      <ul style="color:#444;">{attention_html}</ul>
      <p>Fixing these is worth doing — recruiters see verified evidence, and an
         unconfirmed claim carries no weight in matching.</p>
    """
    )

    html = _WRAP.format(
        inner=f"""
      <h2 style="color:#111;">{subject}</h2>
      <p>Hi {full_name},</p>
      <p>We've finished checking what you submitted.</p>
      <h3 style="color:#111; margin-bottom:4px;">Confirmed</h3>
      <ul style="color:#444;">{confirmed_html}</ul>
      {attention_block}
      <p><a href="{profile_url}" style="color:#5E8BFF; font-weight:700;">Review your profile</a></p>
    """
    )
    return subject, text, html


def interview_invitation(
    *, full_name: str, interview_url: str, has_verified_repositories: bool
) -> tuple[str, str, str]:
    """Sent once, when verification settles and the profile interview is ready.

    The copy is deliberately explicit that visibility to recruiters depends on
    completing it. This is the one email in the product that names a gate the
    candidate is currently behind, and softening it into "boost your profile"
    would leave them waiting on recruiters who structurally cannot see them.

    `has_verified_repositories` changes one clause — what the questions are
    drawn from. A candidate whose repositories all failed verification still
    gets a real interview grounded in their other evidence, and promising them
    questions about repositories they do not have would read as broken.
    """
    subject = "Your profile analysis is complete — one step left"
    grounded_in = (
        "your verified repositories, coding profiles, and experience"
        if has_verified_repositories
        else "your verified coding profiles, certificates, and experience"
    )
    text = (
        f"Hi {full_name},\n\n"
        "We've finished analysing your profile. Your personalised AI interview is ready.\n\n"
        f"The questions are generated from {grounded_in} — there is no generic question "
        "bank, and nothing is asked about anything we could not verify.\n\n"
        "Completing it is what makes your profile visible to recruiters, and your "
        "interview score becomes part of how you are matched to roles.\n\n"
        f"Start here: {interview_url}\n"
    )
    html = _WRAP.format(
        inner=f"""
      <h2 style="color:#111;">Your profile analysis is complete</h2>
      <p>Hi {full_name},</p>
      <p>Your personalised AI interview is ready. The questions are generated from
         <strong>{grounded_in}</strong> — no generic question bank, and nothing asked
         about anything we could not verify.</p>
      <p>Completing it is what makes your profile visible to recruiters, and your
         interview score becomes part of how you are matched to roles.</p>
      <p><a href="{interview_url}" style="color:#5E8BFF; font-weight:700;">Start your interview</a></p>
    """
    )
    return subject, text, html
