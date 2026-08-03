"""Unit tests for certificate credential-URL verification
(`domains/verification/certificate.py`). `reachability.check_reachable` is
monkeypatched so these never make a real network call."""

from __future__ import annotations

import pytest

from src.domains.verification import certificate as certificate_checker
from src.domains.verification.clients import reachability
from src.domains.verification.exceptions import VerificationServiceUnavailable


def _stub_reachable(monkeypatch, *, reachable: bool, body: str = ""):
    monkeypatch.setattr(
        reachability, "check_reachable", lambda url, **kwargs: (reachable, body)
    )


def test_unreachable_url_is_rejected(monkeypatch):
    _stub_reachable(monkeypatch, reachable=False)
    verdict = certificate_checker.verify_certificate("https://dead-domain.example/cert/1", "Coursera")
    assert verdict.status == "rejected"
    assert verdict.score == 0.0
    assert verdict.reachable is False


def test_reachable_url_with_matching_issuer_domain_is_verified(monkeypatch):
    _stub_reachable(monkeypatch, reachable=True, body="")
    verdict = certificate_checker.verify_certificate("https://www.coursera.org/verify/abc123", "Coursera")
    assert verdict.status == "verified"
    assert verdict.issuer_matched is True
    assert verdict.score > 0


def test_reachable_url_with_issuer_named_in_body_is_verified(monkeypatch):
    _stub_reachable(monkeypatch, reachable=True, body="Issued by Coursera to the recipient.")
    verdict = certificate_checker.verify_certificate("https://cred.example.com/xyz", "Coursera")
    assert verdict.status == "verified"
    assert verdict.issuer_matched is True


def test_reachable_url_with_unmatched_issuer_is_flagged_not_rejected(monkeypatch):
    _stub_reachable(monkeypatch, reachable=True, body="A generic hosting page with no relevant text.")
    verdict = certificate_checker.verify_certificate("https://cred.example.com/xyz", "Coursera")
    assert verdict.status == "flagged"
    assert verdict.issuer_matched is False
    assert 0 < verdict.score < 100


def test_network_failure_propagates_rather_than_producing_a_verdict(monkeypatch):
    def _raise(url, **kwargs):
        raise VerificationServiceUnavailable("boom")

    monkeypatch.setattr(reachability, "check_reachable", _raise)
    with pytest.raises(VerificationServiceUnavailable):
        certificate_checker.verify_certificate("https://cred.example.com/xyz", "Coursera")
