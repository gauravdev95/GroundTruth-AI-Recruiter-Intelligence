"""Unit tests for the "consolidated internal signals" experience check
(`domains/verification/experience.py`) — no network calls, pure scoring."""

from __future__ import annotations

from src.domains.verification.experience import score_experience


def test_no_corroboration_stays_unverified():
    verdict = score_experience(
        company_name="Some Startup Nobody Has Heard Of",
        technologies=["Cobol"],
        known_company_names=set(),
        verified_technologies=set(),
    )
    assert verdict.status == "unverified"
    assert verdict.company_known is False
    assert verdict.overlapping_technologies == []


def test_known_company_alone_is_enough_to_flag():
    verdict = score_experience(
        company_name="Acme Corp",
        technologies=["Cobol"],
        known_company_names={"Acme Corp"},
        verified_technologies=set(),
    )
    assert verdict.status == "flagged"
    assert verdict.company_known is True


def test_company_match_is_case_insensitive():
    verdict = score_experience(
        company_name="acme corp",
        technologies=[],
        known_company_names={"Acme Corp"},
        verified_technologies=set(),
    )
    assert verdict.company_known is True


def test_technology_overlap_alone_is_enough_to_flag():
    verdict = score_experience(
        company_name="Unknown Co",
        technologies=["Django", "Python"],
        known_company_names=set(),
        verified_technologies={"django"},
    )
    assert verdict.status == "flagged"
    assert verdict.overlapping_technologies == ["Django"]


def test_both_signals_together_score_higher_than_either_alone():
    both = score_experience(
        company_name="Acme Corp",
        technologies=["Django"],
        known_company_names={"Acme Corp"},
        verified_technologies={"django"},
    )
    one = score_experience(
        company_name="Acme Corp",
        technologies=["Cobol"],
        known_company_names={"Acme Corp"},
        verified_technologies=set(),
    )
    assert both.score > one.score


def test_never_reaches_verified_status():
    # No combination of inputs may produce "verified" — there is no
    # external source of truth for experience claims.
    for company_known in (set(), {"Acme Corp"}):
        for verified_tech in (set(), {"django", "python", "react"}):
            verdict = score_experience(
                company_name="Acme Corp",
                technologies=["Django", "Python", "React"],
                known_company_names=company_known,
                verified_technologies=verified_tech,
            )
            assert verdict.status in ("flagged", "unverified")
