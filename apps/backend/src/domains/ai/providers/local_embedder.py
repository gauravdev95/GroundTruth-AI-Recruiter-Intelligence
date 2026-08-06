"""Local sentence-transformers adapter for the embedding capability.

The only module in the codebase that imports `sentence_transformers` —
everything above it depends only on the `Embedder` protocol in
`domains/ai/llm.py`, the same seam discipline the Gemini adapters keep.

Structurally different from every other adapter here in one way that matters:
there is no network call and no API key. Encoding happens in this process, so
"the provider is down", "the key is missing", and "we are rate limited" are
not reachable states — the failure modes are instead *load time* (the weights
have to be fetched once from the Hugging Face hub, then come from the local
cache) and *memory*. The typed errors from `domains/ai/exceptions.py` are
still what leaves this module, because the worker's retry policy branches on
them and a leaked `torch`/`transformers` exception would be retried as a
generic failure regardless of whether retrying could help.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import structlog

from src.config.config import get_embedding_settings
from src.domains.ai.embedding_constants import EMBEDDING_DIMENSIONS
from src.domains.ai.exceptions import (
    LLMMalformedOutput,
    LLMProviderError,
)

if TYPE_CHECKING:  # pragma: no cover - import only for type checkers
    from sentence_transformers import SentenceTransformer

logger = structlog.get_logger(__name__)

# Same reasoning as the adapters' own input ceilings: bounds one
# pathological input (a job description that's actually a document dump)
# rather than encoding unbounded text. The model's own 512-token window
# truncates far earlier than this; the cap exists so a document dump cannot
# spend minutes of CPU being tokenized before that truncation happens.
MAX_INPUT_CHARS = 30_000


class LocalEmbedder:
    """Encodes with a sentence-transformers model held in this process.

    The model is loaded lazily on the first `embed` call rather than in
    `__init__`, and guarded by a lock: `get_embedder()` is `lru_cache`d, so
    one instance is shared by every request thread in the API process and
    every task in a worker. Loading in `__init__` would move a multi-second
    weight load onto whichever caller happened to construct it — including,
    on a cold cache, a hub download — and two threads racing into the first
    call would otherwise load two copies of the weights.

    Normalized embeddings are requested from the model itself, so the vectors
    written to `embeddings.vector` are unit length — which is what lets
    `domains/matching/scoring.py` treat a dot product as cosine similarity
    directly instead of dividing by magnitudes on every comparison.
    """

    def __init__(self) -> None:
        self._settings = get_embedding_settings()
        self._model: "SentenceTransformer | None" = None
        self._load_lock = threading.Lock()

    def _get_model(self) -> "SentenceTransformer":
        if self._model is not None:
            return self._model

        with self._load_lock:
            # Re-checked inside the lock: a thread that blocked here while
            # another was loading must use that result, not load again.
            if self._model is not None:
                return self._model

            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - packaging failure
                raise LLMProviderError(
                    "sentence-transformers is not installed; the embedding service cannot run"
                ) from exc

            model_name = self._settings.embedding_model
            logger.info(
                "embedding_model_loading",
                model=model_name,
                device=self._settings.embedding_device or "auto",
            )
            try:
                model = SentenceTransformer(
                    model_name,
                    device=self._settings.embedding_device or None,
                    cache_folder=self._settings.embedding_cache_dir or None,
                )
            except Exception as exc:
                # Covers a hub download failure on a cold cache, an unknown
                # model id, and an out-of-memory load. All three are "the
                # embedding service is unavailable" to the caller, and all
                # three are worth retrying — a transient hub outage resolves,
                # and the load is not idempotent-unsafe.
                raise LLMProviderError(
                    f"Could not load the embedding model {model_name!r}"
                ) from exc

            # Renamed in sentence-transformers 5.x; the old name still works
            # but warns. Prefer the new one, fall back so the floor in
            # pyproject.toml (>=3.0.0) stays honest.
            get_dim = getattr(model, "get_embedding_dimension", None) or (
                model.get_sentence_embedding_dimension
            )
            reported = get_dim()
            if reported != EMBEDDING_DIMENSIONS:
                # Caught at load rather than per-encode: a model/dimension
                # mismatch would fail every insert against the pgvector
                # column, and naming the model in the error is what makes a
                # mis-set EMBEDDING_MODEL diagnosable.
                raise LLMProviderError(
                    f"Embedding model {model_name!r} produces {reported} dimensions, "
                    f"but this deployment's schema is built for {EMBEDDING_DIMENSIONS}. "
                    "Changing embedding models requires a migration, not a config change."
                )

            self._model = model
            logger.info("embedding_model_loaded", model=model_name, dimensions=reported)
            return model

    def embed(self, text: str) -> list[float]:
        cleaned = text.strip()
        if not cleaned:
            raise LLMMalformedOutput("Cannot embed empty text")
        if len(cleaned) > MAX_INPUT_CHARS:
            cleaned = cleaned[:MAX_INPUT_CHARS]

        model = self._get_model()
        try:
            vector = model.encode(
                cleaned,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
        except Exception as exc:
            raise LLMProviderError("The embedding model failed to encode the input") from exc

        values = [float(value) for value in vector.tolist()]
        if len(values) != EMBEDDING_DIMENSIONS:
            # Unreachable given the load-time check above, kept because
            # pgvector enforces the column's fixed dimension at insert time
            # anyway and failing here with a clear message beats a raw DB
            # error surfacing three layers up.
            raise LLMMalformedOutput(
                f"Embedding model returned {len(values)} dimensions, expected {EMBEDDING_DIMENSIONS}"
            )
        return values
