"""Unit tests for dependency-manifest technology detection
(`domains/verification/manifests.py`) — this is what makes detected
technologies come from a repository's actual manifests, not from whatever a
student typed into the projects section."""

from __future__ import annotations

import json

from src.domains.verification.manifests import detect_technologies, has_test_files


def _fetcher(files: dict[str, str]):
    return lambda path: files.get(path)


def test_detects_javascript_dependencies_from_package_json():
    package_json = json.dumps({"dependencies": {"react": "^18.0.0"}, "devDependencies": {"vitest": "^1.0.0"}})
    detected = detect_technologies(
        ["package.json", "src/index.js"], _fetcher({"package.json": package_json})
    )
    names = {t.name for t in detected}
    assert "JavaScript" in names
    assert "react" in names
    assert "vitest" in names


def test_detects_python_dependencies_from_requirements_txt():
    content = "fastapi==0.115.0\n# a comment\nsqlalchemy>=2.0\n\n-e .\n"
    detected = detect_technologies(["requirements.txt"], _fetcher({"requirements.txt": content}))
    names = {t.name for t in detected}
    assert "Python" in names
    assert "fastapi" in names
    assert "sqlalchemy" in names


def test_detects_pep621_dependencies_from_pyproject_toml():
    content = 'name = "x"\ndependencies = [\n  "httpx>=0.27",\n  "pydantic>=2.9",\n]\n'
    detected = detect_technologies(["pyproject.toml"], _fetcher({"pyproject.toml": content}))
    names = {t.name for t in detected}
    assert "httpx" in names
    assert "pydantic" in names
    assert "python" not in {n.casefold() for n in names if n != "Python"}


def test_detects_go_mod_dependencies():
    content = "module example.com/foo\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.1\n)\n"
    detected = detect_technologies(["go.mod"], _fetcher({"go.mod": content}))
    names = {t.name for t in detected}
    assert "Go" in names
    assert "gin" in names


def test_primary_language_from_repo_metadata_is_included_once():
    detected = detect_technologies(["README.md"], _fetcher({}), primary_language="Rust")
    assert [t.name for t in detected] == ["Rust"]


def test_duplicate_names_across_sources_are_not_repeated():
    package_json = json.dumps({"dependencies": {}})
    detected = detect_technologies(
        ["package.json"], _fetcher({"package.json": package_json}), primary_language="JavaScript"
    )
    names = [t.name for t in detected]
    assert names.count("JavaScript") == 1


def test_missing_manifest_content_still_credits_the_language_but_no_dependencies():
    """Finding the manifest by filename is enough to credit the base
    language even when the fetch fails; only dependency-name parsing needs
    the content."""
    detected = detect_technologies(["package.json"], _fetcher({}))
    assert [t.name for t in detected] == ["JavaScript"]


def test_malformed_manifest_content_is_skipped_not_raised():
    detected = detect_technologies(["package.json"], _fetcher({"package.json": "{not json"}))
    assert [t.name for t in detected] == ["JavaScript"]


def test_has_test_files_matches_common_test_layouts():
    assert has_test_files(["tests/test_foo.py"])
    assert has_test_files(["src/__tests__/foo.test.ts"])
    assert has_test_files(["spec/foo_spec.rb"])
    assert has_test_files(["src/specification.rb"]) is False  # "spec" as a substring, not a path segment
    assert has_test_files(["src/index.js", "README.md"]) is False
