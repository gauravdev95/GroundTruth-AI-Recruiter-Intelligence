"""Unit tests for the server-side validation rules in schemas.py."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.domains.auth.schemas import CandidateRegisterRequest, LoginRequest, RecruiterRegisterRequest

VALID_CANDIDATE = {
    "email": "Ada@Example.com",
    "password": "StrongPass1!",
}

VALID_RECRUITER = {
    "full_name": "Grace Hopper",
    "company_name": "Hopper Systems",
    "company_email": "grace@hoppersystems.com",
    "password": "StrongPass1!",
    "confirm_password": "StrongPass1!",
    "captcha_token": "token",
    "accept_terms": True,
}


def test_valid_candidate_register_normalizes_email() -> None:
    payload = CandidateRegisterRequest(**VALID_CANDIDATE)
    assert payload.email == "ada@example.com"


def test_candidate_register_needs_only_email_and_password() -> None:
    """Student signup is two fields.

    The name moved to `BasicInfoRequest` and the phone number to the same
    section as an optional field; `confirm_password` and `accept_terms` are
    now the form's concern. This test is the contract — if a required field
    reappears here, the two-field signup has regressed.
    """
    payload = CandidateRegisterRequest(email="ada@example.com", password="StrongPass1!")
    assert payload.captcha_token == ""


def test_candidate_captcha_token_is_optional_but_present() -> None:
    """Optional so the two-field form can post without one, but still a real
    field — `verify_captcha` fails closed when a secret key is configured, so
    the token has to be sendable once the widget is wired."""
    payload = CandidateRegisterRequest(
        email="ada@example.com", password="StrongPass1!", captcha_token="abc"
    )
    assert payload.captcha_token == "abc"


@pytest.mark.parametrize(
    "password",
    [
        "short1!",  # too short
        "alllowercase1!",  # no uppercase
        "ALLUPPERCASE1!",  # no lowercase
        "NoDigitsHere!",  # no digit
        "NoSpecialChar1",  # no special char
    ],
)
def test_weak_passwords_rejected(password: str) -> None:
    payload = {**VALID_CANDIDATE, "password": password}
    with pytest.raises(ValidationError):
        CandidateRegisterRequest(**payload)


# Recruiter registration deliberately keeps the fuller form — a company name
# and a work email are load-bearing there — so the confirm-password and
# terms rules are still exercised, just on the schema that still has them.


def test_recruiter_mismatched_confirm_password_rejected() -> None:
    payload = {**VALID_RECRUITER, "confirm_password": "SomethingElse1!"}
    with pytest.raises(ValidationError):
        RecruiterRegisterRequest(**payload)


def test_recruiter_unaccepted_terms_rejected() -> None:
    payload = {**VALID_RECRUITER, "accept_terms": False}
    with pytest.raises(ValidationError):
        RecruiterRegisterRequest(**payload)


def test_valid_recruiter_register() -> None:
    payload = RecruiterRegisterRequest(
        full_name="Grace Hopper",
        company_name="Acme Corp",
        company_email="Grace@Acme.com",
        password="StrongPass1!",
        confirm_password="StrongPass1!",
        captcha_token="token",
        accept_terms=True,
    )
    assert payload.company_email == "grace@acme.com"


def test_login_request_normalizes_email() -> None:
    payload = LoginRequest(
        email="Ada@Example.com",
        password="whatever",
        captcha_token="token",
        remember_me=False,
        expected_role="candidate",
    )
    assert payload.email == "ada@example.com"


def test_every_coding_platform_has_a_profile_url_template() -> None:
    """A `CodingPlatform` member with no entry in `_PLATFORM_PROFILE_URL`
    raises KeyError while *saving* section 2 — a 500 on a valid request, in a
    code path no existing test exercises for a newly added platform. Asserting
    exhaustiveness here turns that into a failing unit test instead."""
    from src.domains.student.models import CodingPlatform
    from src.domains.student.schemas import _PLATFORM_PROFILE_URL

    # `OTHER` is the one deliberate exception: it names a platform with no
    # template and no checker, so the student supplies the whole URL and
    # `build_coding_platform_url` refuses to guess one.
    missing = set(CodingPlatform) - set(_PLATFORM_PROFILE_URL) - {CodingPlatform.OTHER}
    assert not missing, f"No profile URL template for: {sorted(p.value for p in missing)}"
    assert CodingPlatform.OTHER not in _PLATFORM_PROFILE_URL

    # Every template must actually consume the handle, or two candidates on the
    # same platform would be stored with identical profile URLs.
    for platform, template in _PLATFORM_PROFILE_URL.items():
        assert "{handle}" in template, f"{platform.value} template ignores the handle"


def test_other_platform_requires_a_supplied_url() -> None:
    """The escape-hatch platform has no template, so a caller that omits the
    URL must get an error rather than a URL this codebase invented — a 404 on
    a guessed URL would be recorded as the candidate's claim failing."""
    import pytest as _pytest

    from src.domains.student.models import CodingPlatform
    from src.domains.student.schemas import build_coding_platform_url

    with _pytest.raises(ValueError):
        build_coding_platform_url(CodingPlatform.OTHER, "ada")

    assert (
        build_coding_platform_url(CodingPlatform.OTHER, "ada", custom_url="https://spoj.com/ada")
        == "https://spoj.com/ada"
    )


def test_reachability_only_platforms_have_a_rate_limit() -> None:
    """The reachability branch in `verify_coding_platform_account_task` looks
    its per-minute cap up by platform and would KeyError on a platform added
    without one.

    Asserted against `CodingPlatform` itself rather than a hand-written list,
    so adding a member without a bucket fails here instead of in a worker.
    The two API-backed platforms are excluded because they never reach that
    branch — they have real clients with their own limiters.
    """
    from src.config.config import VerificationSettings
    from src.domains.student.models import CodingPlatform

    settings = VerificationSettings(_env_file=None)
    setting_name = {CodingPlatform.OTHER: "other_platform"}

    for platform in CodingPlatform:
        if platform in (CodingPlatform.CODEFORCES, CodingPlatform.LEETCODE):
            continue
        name = setting_name.get(platform, platform.value)
        assert getattr(settings, f"{name}_rate_limit_per_minute") > 0


def test_integrity_event_vocabulary_matches_the_model():
    """The schema's Literal is the validation boundary and the model's tuple is
    the documentation; a value that exists in one and not the other means the
    room can either write something nothing describes, or be rejected for
    something the model says is legal."""
    from typing import get_args

    from src.domains.interview.models import INTEGRITY_EVENT_TYPES
    from src.domains.interview.schemas import IntegrityEventType

    assert set(get_args(IntegrityEventType)) == set(INTEGRITY_EVENT_TYPES)


def test_integrity_event_detail_rejects_a_large_or_nested_payload():
    """`detail` is room-supplied context, not a place to park arbitrary JSON on
    an authenticated write path."""
    from src.domains.interview.schemas import IntegrityEventRequest

    with pytest.raises(ValidationError):
        IntegrityEventRequest(
            client_sequence=1,
            event_type="tab_hidden",
            elapsed_seconds=1,
            detail={"nested": {"not": "allowed"}},
        )

    with pytest.raises(ValidationError):
        IntegrityEventRequest(
            client_sequence=1,
            event_type="tab_hidden",
            elapsed_seconds=1,
            detail={f"k{i}": "v" for i in range(9)},
        )
