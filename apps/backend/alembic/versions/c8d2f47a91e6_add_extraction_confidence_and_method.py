"""Add per-field extraction confidence and method to resume drafts.

Backs the deterministic-first extraction pipeline
(`domains/resume/extraction/`). Three additive nullable columns; no
existing data is read, rewritten or dropped, so this is reversible without
loss in both directions.

Why nullable rather than defaulted:

* `confidence_payload` — drafts written before this migration were produced
  by the unconditional LLM pass and have no per-field provenance. A default
  of `{}` would be indistinguishable from "the pipeline ran and found
  nothing", and the review screen renders those two states differently: a
  legacy draft shows no badges at all, an empty result shows every field
  amber. NULL is the honest encoding of "this predates confidence".
* `extraction_method` — same argument. A legacy row's method is genuinely
  unknown, and backfilling it as `model` would assert something about how
  those drafts were produced that this migration cannot verify.
* `escalation_reason` — meaningful only when the LLM ran, so it is NULL on
  every purely deterministic draft by design rather than by omission.

Revision ID: c8d2f47a91e6
Revises: f4b81c26e9a7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "c8d2f47a91e6"
down_revision: Union[str, None] = "f4b81c26e9a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "resume_extraction_drafts",
        sa.Column("confidence_payload", JSONB(), nullable=True),
    )
    op.add_column(
        "resume_extraction_drafts",
        sa.Column("extraction_method", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "resume_extraction_drafts",
        sa.Column("escalation_reason", sa.String(length=60), nullable=True),
    )

    # Partial index on the escalated rows only. The question this answers —
    # "which documents are defeating the deterministic parser, and why" — is
    # the one that drives threshold tuning in `pipeline.py`, and it is always
    # asked over the minority of rows that escalated. Indexing the full table
    # would carry every deterministic row for a query that never wants them.
    op.create_index(
        "ix_resume_drafts_escalation_reason",
        "resume_extraction_drafts",
        ["escalation_reason"],
        unique=False,
        postgresql_where=sa.text("escalation_reason IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_resume_drafts_escalation_reason", table_name="resume_extraction_drafts")
    op.drop_column("resume_extraction_drafts", "escalation_reason")
    op.drop_column("resume_extraction_drafts", "extraction_method")
    op.drop_column("resume_extraction_drafts", "confidence_payload")
