"""`BAAI/bge-base-en-v1.5`'s output dimension.

A standalone leaf module (no imports) so both `domains/matching/models.py`
(the pgvector column definition) and
`domains/ai/providers/local_embedder.py` (the encode-shape check) can
depend on it without either domain depending on the other.

Was 1536 (`text-embedding-3-small`) until the embedding provider moved
in-process; `f4b81c26e9a7` is the migration that resized the column and
its ANN index to match.
"""

EMBEDDING_DIMENSIONS = 768
