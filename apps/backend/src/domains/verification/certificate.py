"""Certificate credential-URL verification.

No general API exists to validate an arbitrary issuer's certificate, so this
combines two weak signals into one verdict:

1. **Reachability** — does `credential_url` resolve to something (not a 404,
   not a dead domain)?
2. **Issuer-domain match** — does the URL's registered domain plausibly
   belong to the claimed issuer (e.g. issuer "Coursera" and a
   `coursera.org` URL)? A crude token-overlap check, not a lookup against a
   registry of accredited issuers (no such open registry exists) — cited as
   a limitation in `PROGRESS.md`, not hidden.

Per constraint §4 of the task this implements: a failed *network* call
(timeout, DNS failure) never reaches a verdict at all — the caller
(`verify_certificate_task`) lets that exception propagate so the claim stays
`UNVERIFIED`. This module only runs once the URL was actually reachable
(or definitively 4xx'd).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.domains.verification.clients import reachability

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.casefold()))


def _issuer_matches_domain(issuer: str, domain: str) -> bool:
    issuer_tokens = _tokens(issuer)
    domain_tokens = _tokens(domain)
    if not issuer_tokens or not domain_tokens:
        return False
    return bool(issuer_tokens & domain_tokens)


@dataclass(frozen=True)
class CertificateVerdict:
    status: str  # "verified" | "rejected" | "flagged"
    score: float
    reason: str
    domain: str
    reachable: bool
    issuer_matched: bool


def verify_certificate(credential_url: str, issuer: str) -> CertificateVerdict:
    """Raises `VerificationServiceUnavailable` on a genuine network failure —
    callers must not catch that and must let it propagate so the claim stays
    `UNVERIFIED` (constraint §4)."""
    reachable, body = reachability.check_reachable(
        credential_url, rate_limit_name="certificate_check", max_requests_per_minute=_rate_limit()
    )
    domain = reachability.domain_of(credential_url)

    if not reachable:
        return CertificateVerdict(
            status="rejected",
            score=0.0,
            reason=f"{credential_url} did not resolve to a valid document.",
            domain=domain,
            reachable=False,
            issuer_matched=False,
        )

    issuer_matched = _issuer_matches_domain(issuer, domain) or issuer.casefold() in body.casefold()
    if issuer_matched:
        return CertificateVerdict(
            status="verified",
            score=90.0,
            reason=f"{credential_url} is reachable and its domain/content plausibly matches issuer '{issuer}'.",
            domain=domain,
            reachable=True,
            issuer_matched=True,
        )

    return CertificateVerdict(
        status="flagged",
        score=50.0,
        reason=(
            f"{credential_url} is reachable, but its domain ('{domain}') could not be confidently "
            f"matched to the claimed issuer ('{issuer}'). Flagged for manual review rather than rejected — "
            "many legitimate credential hosts (e.g. institutional LMS platforms) don't share a name "
            "with the issuing organization."
        ),
        domain=domain,
        reachable=True,
        issuer_matched=False,
    )


def _rate_limit() -> int:
    from src.config.config import get_verification_settings

    return get_verification_settings().certificate_check_rate_limit_per_minute
