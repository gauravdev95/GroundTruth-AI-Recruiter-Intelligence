"""resize embeddings.vector for the local BAAI/bge-base-en-v1.5 model

The matching engine's embedding provider moved from OpenAI's hosted
`text-embedding-3-small` (1536 dimensions) to `BAAI/bge-base-en-v1.5` run
in-process via `sentence-transformers` (768 dimensions). Only the provider
changed — the `Embedder` seam, the `embeddings` table, the polymorphic
`(entity_type, entity_id, model_version)` key, and every read path are
untouched. What could not stay unchanged is the column *width*: the pgvector
type and its ivfflat index both carry a concrete dimension, which is exactly
why `domains/matching/models.py` notes that changing embedding models is a
migration rather than a config change.

**This migration deletes every existing row in `embeddings`.** That is not
collateral damage, it is the point:

* The stored vectors are 1536-dimensional OpenAI output. There is no
  meaningful conversion to a 768-dimensional BGE vector — the two models
  place text in unrelated spaces, so a truncation or projection would produce
  numbers that are silently *wrong* rather than merely differently shaped.
* They were already unreachable. Every read filters on
  `model_version = EmbeddingSettings.embedding_model`
  (`domains/matching/embeddings.py::get_embedding` / `_upsert_embedding`),
  and that value is now `BAAI/bge-base-en-v1.5`. Rows written under
  `text-embedding-3-small` would never again be returned to a caller;
  keeping them would leave dead rows padding the ANN index.

Nothing downstream is lost: `embeddings` is a derived cache. Candidates are
re-embedded on the next profile change or re-verification and jobs on the
next publish/re-embed, both through the existing tasks in
`jobs/tasks/matching.py`. Persisted `match_results` rows are deliberately
*not* touched — they hold committed scores that applications reference, and
they are rescored in place by the normal recompute path.

Revision ID: f4b81c26e9a7
Revises: a7d419e2c8b4
Create Date: 2026-08-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'f4b81c26e9a7'
down_revision: Union[str, None] = 'a7d419e2c8b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: Mirrors `domains/ai/embedding_constants.EMBEDDING_DIMENSIONS`, copied
#: rather than imported for the same reason `a3e7c19f5d6b` inlines its own:
#: a migration must describe the schema at *its* point in history, not
#: whatever the application constant happens to say when it runs.
NEW_DIMENSIONS = 768
OLD_DIMENSIONS = 1536


def _resize(dimensions: int) -> None:
    """Drop and re-add the column at a new width.

    `ALTER COLUMN ... TYPE vector(n)` would also work on an empty table, but
    drop-and-add is what `a3e7c19f5d6b` used to create the column in the
    first place and keeps this migration free of any assumption about which
    pgvector version's casts are available.
    """
    op.execute("DROP INDEX IF EXISTS ix_embeddings_vector_ann")
    # Rows are 1536-dim OpenAI vectors no read path can reach any more (see
    # the module docstring). The column is NOT NULL, so they cannot survive
    # the resize regardless.
    op.execute("DELETE FROM embeddings")
    op.execute("ALTER TABLE embeddings DROP COLUMN vector")
    op.execute(f"ALTER TABLE embeddings ADD COLUMN vector vector({dimensions}) NOT NULL")
    # Same ivfflat/cosine/lists=100 configuration as `a3e7c19f5d6b`; only the
    # underlying column width differs, so the retrieval pipeline's operator
    # and index choice are unchanged.
    op.execute(
        "CREATE INDEX ix_embeddings_vector_ann ON embeddings "
        "USING ivfflat (vector vector_cosine_ops) WITH (lists = 100)"
    )


def upgrade() -> None:
    _resize(NEW_DIMENSIONS)


def downgrade() -> None:
    # Symmetric, and symmetrically destructive: going back means going back to
    # a column that cannot hold a BGE vector, so the locally-generated
    # embeddings are dropped exactly as the OpenAI ones were on the way up.
    _resize(OLD_DIMENSIONS)
