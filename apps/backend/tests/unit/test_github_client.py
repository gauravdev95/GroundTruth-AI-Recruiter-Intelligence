"""Unit tests for the pure-parsing parts of
`domains/verification/clients/github.py`."""

from __future__ import annotations

import pytest

from src.domains.verification.clients.github import parse_repo_url
from src.domains.verification.exceptions import ClaimNotFound


def test_parses_a_plain_repo_url():
    assert parse_repo_url("https://github.com/ada/compiler") == ("ada", "compiler")


def test_parses_a_repo_url_with_git_suffix():
    assert parse_repo_url("https://github.com/ada/compiler.git") == ("ada", "compiler")


def test_parses_a_repo_url_with_trailing_slash():
    assert parse_repo_url("https://github.com/ada/compiler/") == ("ada", "compiler")


def test_rejects_a_url_with_no_repo_segment():
    with pytest.raises(ClaimNotFound):
        parse_repo_url("https://github.com/ada")


def test_rejects_a_non_github_url_shape():
    with pytest.raises(ClaimNotFound):
        parse_repo_url("not-a-url")
