"""Embedding service wrapping the OpenAI Embeddings API."""

from __future__ import annotations

from functools import lru_cache

import structlog
from openai import AsyncOpenAI

from coyo.config import get_settings
from coyo.exceptions import ExternalServiceError

logger = structlog.get_logger()

_BATCH_SIZE = 100


class EmbeddingService:
    """Generates text embeddings via the OpenAI Embeddings API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Compute embeddings for a batch of texts.

        Returns a list of embedding vectors in the same order as the input.
        Automatically splits large inputs into batches to respect API limits.
        """
        if not texts:
            return []

        try:
            all_embeddings: list[list[float]] = []
            for i in range(0, len(texts), _BATCH_SIZE):
                batch = texts[i : i + _BATCH_SIZE]
                response = await self._client.embeddings.create(
                    model=self._model,
                    input=batch,
                )
                all_embeddings.extend(item.embedding for item in response.data)
            return all_embeddings
        except Exception as exc:
            raise ExternalServiceError("OpenAI Embeddings", str(exc)) from exc


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Lazily instantiate and cache the embedding service."""
    return EmbeddingService()
