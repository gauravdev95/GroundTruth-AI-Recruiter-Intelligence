"""Deterministic resume extraction.

The public surface is deliberately four names. Everything else in this
package is an implementation detail of how a document becomes a draft, and
the worker (`jobs/tasks/resume.py`) should not need to know about sections,
line models or provenance tiers to run the pipeline.

    parse_resume(text)            -> ResumeDraft      the deterministic pass
    needs_escalation(draft, ...)  -> (bool, reason)   should the LLM run
    to_extraction(draft)          -> ResumeExtraction the existing wire schema
    merge_model_result(draft, m)  -> (extraction, draft)

`ResumeDraft.wire()` carries the per-field confidence the review screen
renders; see `confidence.py` for why that view exists and why an LLM cannot
produce it honestly.
"""

from src.domains.resume.extraction.confidence import (
    REVIEW_THRESHOLD,
    FieldMap,
    Provenance,
    Scored,
)
from src.domains.resume.extraction.pipeline import (
    ResumeDraft,
    merge_model_result,
    needs_escalation,
    parse_resume,
    to_extraction,
)
from src.domains.resume.extraction.taxonomy import canonicalise

__all__ = [
    "REVIEW_THRESHOLD",
    "FieldMap",
    "Provenance",
    "ResumeDraft",
    "Scored",
    "canonicalise",
    "merge_model_result",
    "needs_escalation",
    "parse_resume",
    "to_extraction",
]
