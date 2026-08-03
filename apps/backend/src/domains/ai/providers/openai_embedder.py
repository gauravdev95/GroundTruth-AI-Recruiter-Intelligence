"""OpenAI adapter for the embedding capability.

The only module in the codebase that imports the `openai` SDK — everything
above it depends only on the `Embedder` protocol in `domains/ai/llm.py`,
same seam discipline as the Anthropic adapters.
"""

from __future__ import annotations

import openai
import structlog

from src.config.config import get_embedding_settings
from src.domains.ai.embedding_constants import EMBEDDING_DIMENSIONS
from src.domains.ai.exceptions import (
    LLMMalformedOutput,
    LLMProviderError,
    LLMTimeout,
)

logger = structlog.get_logger(__name__)

# Same reasoning as `anthropic_extractor.py::MAX_INPUT_CHARS`: bounds one
# pathological input (a job description that's actually a document dump)
# rather than sending unbounded text to the embedding endpoint.
MAX_INPUT_CHARS = 30_000


class OpenAIEmbedder:
    def __init__(self) -> None:
        settings = get_embedding_settings()
        self._settings = settings
        self._client = openai.OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.embedding_timeout_seconds,
            max_retries=settings.embedding_max_retries,
        )

    def embed(self, text: str) -> list[float]:
        cleaned = text.strip()
        if not cleaned:
            raise LLMMalformedOutput("Cannot embed empty text")
        if len(cleaned) > MAX_INPUT_CHARS:
            cleaned = cleaned[:MAX_INPUT_CHARS]

        try:
            response = self._client.embeddings.create(
                model=self._settings.embedding_model, input=cleaned
            )
        except openai.APITimeoutError as exc:
            raise LLMTimeout("The embedding service timed out") from exc
        except openai.APIConnectionError as exc:
            raise LLMProviderError("Could not reach the embedding service") from exc
        except openai.RateLimitError as exc:
            raise LLMProviderError("The embedding service is rate limited") from exc
        except openai.APIStatusError as exc:
            if exc.status_code < 500:
                raise LLMMalformedOutput(
                    f"The embedding request was rejected ({exc.status_code})"
                ) from exc
            raise LLMProviderError(f"The embedding service failed ({exc.status_code})") from exc

        vector = response.data[0].embedding
        if len(vector) != EMBEDDING_DIMENSIONS:
            # A model/dimension mismatch would silently corrupt the ANN
            # index (pgvector enforces the column's fixed dimension at
            # insert time anyway, but failing here with a clear message
            # beats a raw DB error surfacing three layers up).
            raise LLMMalformedOutput(
                f"Embedding service returned {len(vector)} dimensions, expected {EMBEDDING_DIMENSIONS}"
            )
        return vector
