"""Technology detection from dependency manifests — not from claimed skills.

`verify_repository_task` calls `detect_technologies` with the repo's file
tree (from `clients/github.get_repo_tree`) and a fetcher for individual file
contents. Every manifest parser here is best-effort and permissive: a
manifest that doesn't parse contributes nothing rather than raising, because
one malformed `package.json` in a repo must not fail the whole verification
check.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable

FileFetcher = Callable[[str], "str | None"]

# Ecosystem label attached to every dependency name found in a given manifest
# — this is what feeds `skills.py`'s category guess, and what a recruiter
# reads under "detected from" in the audit payload.
_MANIFEST_PARSERS: dict[str, str] = {
    "package.json": "npm",
    "requirements.txt": "pip",
    "pyproject.toml": "pip",
    "go.mod": "go",
    "Cargo.toml": "cargo",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "build.gradle.kts": "gradle",
    "Gemfile": "gem",
    "composer.json": "composer",
}

# Manifest filenames map to a base-language technology so a repo with only a
# `package.json` still credits "JavaScript" even before any dependency names
# are parsed out of it.
_MANIFEST_LANGUAGE_HINT: dict[str, str] = {
    "package.json": "JavaScript",
    "requirements.txt": "Python",
    "pyproject.toml": "Python",
    "go.mod": "Go",
    "Cargo.toml": "Rust",
    "pom.xml": "Java",
    "build.gradle": "Java",
    "build.gradle.kts": "Kotlin",
    "Gemfile": "Ruby",
    "composer.json": "PHP",
}

MAX_MANIFESTS_PER_REPO = 8
MAX_DEPENDENCIES_PER_MANIFEST = 40


@dataclass(frozen=True)
class DetectedTechnology:
    name: str
    ecosystem: str
    source_manifest: str


def _dedupe_case_insensitive(names: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for name in names:
        cleaned = name.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result[:MAX_DEPENDENCIES_PER_MANIFEST]


def _parse_package_json(content: str) -> list[str]:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return []
    names: list[str] = []
    for section in ("dependencies", "devDependencies"):
        names.extend((data.get(section) or {}).keys())
    return _dedupe_case_insensitive(names)


def _parse_requirements_txt(content: str) -> list[str]:
    names = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "-")):
            continue
        match = re.match(r"^([A-Za-z0-9_.\-]+)", stripped)
        if match:
            names.append(match.group(1))
    return _dedupe_case_insensitive(names)


def _parse_pyproject_toml(content: str) -> list[str]:
    # Best-effort regex rather than a TOML parser dependency: this only needs
    # dependency *names*, and both PEP 621 (`dependencies = [...]`) and
    # Poetry (`[tool.poetry.dependencies]` table) shapes are simple enough to
    # extract with two patterns.
    names: list[str] = []
    pep621 = re.search(r"dependencies\s*=\s*\[(.*?)\]", content, re.DOTALL)
    if pep621:
        names.extend(re.findall(r'["\']([A-Za-z0-9_.\-]+)', pep621.group(1)))
    poetry_section = re.search(
        r"\[tool\.poetry\.(?:dependencies|dev-dependencies)\](.*?)(?:\n\[|\Z)", content, re.DOTALL
    )
    if poetry_section:
        names.extend(re.findall(r"^([A-Za-z0-9_.\-]+)\s*=", poetry_section.group(1), re.MULTILINE))
    return _dedupe_case_insensitive([n for n in names if n.casefold() != "python"])


def _parse_go_mod(content: str) -> list[str]:
    names = re.findall(r"^\s*([\w.\-/]+)\s+v[\d.]", content, re.MULTILINE)
    # Module paths -> last path segment as the readable name.
    return _dedupe_case_insensitive([n.rsplit("/", 1)[-1] for n in names])


def _parse_cargo_toml(content: str) -> list[str]:
    section = re.search(r"\[dependencies\](.*?)(?:\n\[|\Z)", content, re.DOTALL)
    if not section:
        return []
    names = re.findall(r"^([A-Za-z0-9_\-]+)\s*=", section.group(1), re.MULTILINE)
    return _dedupe_case_insensitive(names)


def _parse_pom_xml(content: str) -> list[str]:
    return _dedupe_case_insensitive(re.findall(r"<artifactId>([\w.\-]+)</artifactId>", content))


def _parse_gradle(content: str) -> list[str]:
    matches = re.findall(r"""(?:implementation|api|compile)\s*\(?['"]([\w.\-]+:[\w.\-]+)""", content)
    return _dedupe_case_insensitive(matches)


def _parse_gemfile(content: str) -> list[str]:
    return _dedupe_case_insensitive(re.findall(r"""gem\s+['"]([\w.\-]+)['"]""", content))


def _parse_composer_json(content: str) -> list[str]:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return []
    names = list((data.get("require") or {}).keys())
    return _dedupe_case_insensitive([n for n in names if n != "php"])


_PARSER_FUNCTIONS: dict[str, Callable[[str], list[str]]] = {
    "package.json": _parse_package_json,
    "requirements.txt": _parse_requirements_txt,
    "pyproject.toml": _parse_pyproject_toml,
    "go.mod": _parse_go_mod,
    "Cargo.toml": _parse_cargo_toml,
    "pom.xml": _parse_pom_xml,
    "build.gradle": _parse_gradle,
    "build.gradle.kts": _parse_gradle,
    "Gemfile": _parse_gemfile,
    "composer.json": _parse_composer_json,
}


def detect_technologies(
    file_paths: list[str], fetch_content: FileFetcher, *, primary_language: str | None = None
) -> list[DetectedTechnology]:
    """Scans `file_paths` for known manifest filenames (at any depth) and
    parses each one found via `fetch_content`, up to `MAX_MANIFESTS_PER_REPO`
    to bound the number of content fetches on a monorepo with many nested
    manifests."""
    detected: list[DetectedTechnology] = []
    seen_names: set[str] = set()

    if primary_language:
        detected.append(
            DetectedTechnology(name=primary_language, ecosystem="github_language", source_manifest="<repo metadata>")
        )
        seen_names.add(primary_language.casefold())

    manifests_seen = 0
    for path in file_paths:
        filename = path.rsplit("/", 1)[-1]
        if filename not in _MANIFEST_PARSERS or manifests_seen >= MAX_MANIFESTS_PER_REPO:
            continue
        manifests_seen += 1

        language_hint = _MANIFEST_LANGUAGE_HINT[filename]
        if language_hint.casefold() not in seen_names:
            detected.append(DetectedTechnology(name=language_hint, ecosystem="language", source_manifest=path))
            seen_names.add(language_hint.casefold())

        content = fetch_content(path)
        if not content:
            continue
        ecosystem = _MANIFEST_PARSERS[filename]
        for name in _PARSER_FUNCTIONS[filename](content):
            if name.casefold() in seen_names:
                continue
            seen_names.add(name.casefold())
            detected.append(DetectedTechnology(name=name, ecosystem=ecosystem, source_manifest=path))

    return detected


_TEST_PATH_PATTERNS = re.compile(
    r"(^|/)(tests?|spec|__tests__)(/|$)|(^|/)[\w\-]+\.(test|spec)\.\w+$|(^|/)test_[\w\-]+\.py$",
    re.IGNORECASE,
)


def has_test_files(file_paths: list[str]) -> bool:
    return any(_TEST_PATH_PATTERNS.search(path) for path in file_paths)
