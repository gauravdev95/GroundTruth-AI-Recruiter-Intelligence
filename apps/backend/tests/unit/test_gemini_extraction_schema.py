"""The Gemini-dialect conversion and the volume clamp in `gemini_extractor`.

Gemini is the only resume extractor, so a schema it rejects takes the whole
capability down with a bare 400 that names no field — which is exactly the
failure these assert against. They run against the real
`ResumeExtraction`, not a fixture, so adding a field to the extraction schema
that Gemini cannot express fails here rather than in production.
"""

from __future__ import annotations

from typing import Any

from src.domains.ai.extraction_schema import MAX_LINKS, ResumeExtraction
from src.domains.ai.providers.gemini_extractor import (
    _SUPPORTED_KEYWORDS,
    _clamp_lists,
    to_gemini_schema,
)


def _walk(node: Any):
    """Every dict in the converted schema, including nested ones."""
    if isinstance(node, dict):
        yield node
        for key, value in node.items():
            # `properties` keys are field names, not schema nodes — descend
            # into the values only.
            for sub in (value.values() if key == "properties" else [value]):
                yield from _walk(sub)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def test_converted_schema_uses_only_supported_keywords():
    schema = to_gemini_schema(ResumeExtraction)

    for node in _walk(schema):
        if node.get("type") == "object" and "properties" in node:
            # Field names are unconstrained; the sibling keywords are not.
            unsupported = set(node) - _SUPPORTED_KEYWORDS
        else:
            unsupported = set(node) - _SUPPORTED_KEYWORDS - {"nullable"}
        assert not unsupported, f"unsupported keyword(s) {unsupported} survived conversion"


def test_contact_fields_survive_conversion():
    """The identity fields are the ones most likely to be lost, because they
    are nullable scalars nested one level down — the shape `_inline` rewrites."""
    contact = to_gemini_schema(ResumeExtraction)["properties"]["contact"]["properties"]

    assert {"full_name", "email", "phone", "links"} <= set(contact)
    assert contact["links"]["type"] == "array"
    assert contact["email"]["nullable"] is True


def test_clamp_trims_contact_links():
    payload = _clamp_lists({"contact": {"links": [f"https://example.com/{i}" for i in range(MAX_LINKS + 5)]}})

    assert len(payload["contact"]["links"]) == MAX_LINKS


def test_clamp_tolerates_a_missing_or_malformed_contact():
    """The clamp runs before validation, so it sees whatever the model
    returned — including a `contact` that is absent or not an object."""
    assert _clamp_lists({}) == {}
    assert _clamp_lists({"contact": None}) == {"contact": None}
    assert _clamp_lists({"contact": "nope"}) == {"contact": "nope"}
