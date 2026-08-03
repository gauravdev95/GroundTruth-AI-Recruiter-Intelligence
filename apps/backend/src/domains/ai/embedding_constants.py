"""`text-embedding-3-small`'s output dimension.

A standalone leaf module (no imports) so both `domains/matching/models.py`
(the pgvector column definition) and
`domains/ai/providers/openai_embedder.py` (the response-shape check) can
depend on it without either domain depending on the other.
"""

EMBEDDING_DIMENSIONS = 1536
