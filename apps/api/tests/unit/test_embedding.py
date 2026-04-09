"""Unit tests for coyo.services.embedding."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coyo.exceptions import ExternalServiceError
from coyo.services.embedding import EmbeddingService


@pytest.fixture()
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.openai_api_key = "test-key"
    settings.embedding_model = "text-embedding-3-small"
    # Tests use tiny synthetic vectors; the dim must match for the
    # production guard inside EmbeddingService.embed().
    settings.embedding_dim = 3
    return settings


@pytest.fixture()
def mock_openai_client() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def service(mock_settings: MagicMock, mock_openai_client: AsyncMock):
    """Patch get_settings for the duration of the whole test, so that
    EmbeddingService.embed() also sees the test's embedding_dim=3."""
    with (
        patch("coyo.services.embedding.get_settings", return_value=mock_settings),
        patch("coyo.services.embedding.AsyncOpenAI", return_value=mock_openai_client),
    ):
        yield EmbeddingService()


class TestEmbed:
    @pytest.mark.asyncio()
    async def test_returns_embeddings_in_correct_order(
        self,
        service: EmbeddingService,
        mock_openai_client: AsyncMock,
    ) -> None:
        emb1 = [0.1, 0.2, 0.3]
        emb2 = [0.4, 0.5, 0.6]
        item1 = MagicMock()
        item1.embedding = emb1
        item2 = MagicMock()
        item2.embedding = emb2

        response = MagicMock()
        response.data = [item1, item2]
        mock_openai_client.embeddings.create = AsyncMock(return_value=response)

        result = await service.embed(["hello", "world"])

        assert result == [emb1, emb2]
        mock_openai_client.embeddings.create.assert_awaited_once_with(
            model="text-embedding-3-small",
            input=["hello", "world"],
        )

    @pytest.mark.asyncio()
    async def test_empty_input_returns_empty_list(
        self,
        service: EmbeddingService,
        mock_openai_client: AsyncMock,
    ) -> None:
        result = await service.embed([])
        assert result == []
        mock_openai_client.embeddings.create.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_api_failure_raises_external_service_error(
        self,
        service: EmbeddingService,
        mock_openai_client: AsyncMock,
    ) -> None:
        mock_openai_client.embeddings.create = AsyncMock(
            side_effect=RuntimeError("API timeout"),
        )

        with pytest.raises(ExternalServiceError) as exc_info:
            await service.embed(["test"])

        assert "OpenAI Embeddings" in str(exc_info.value)
        assert "API timeout" in str(exc_info.value)

    @pytest.mark.asyncio()
    async def test_single_text_input(
        self,
        service: EmbeddingService,
        mock_openai_client: AsyncMock,
    ) -> None:
        item = MagicMock()
        item.embedding = [1.0, 0.0, 0.5]
        response = MagicMock()
        response.data = [item]
        mock_openai_client.embeddings.create = AsyncMock(return_value=response)

        result = await service.embed(["single"])
        assert result == [[1.0, 0.0, 0.5]]

    @pytest.mark.asyncio()
    async def test_dim_mismatch_raises_external_service_error(
        self,
        service: EmbeddingService,
        mock_openai_client: AsyncMock,
    ) -> None:
        """Vectors with the wrong dimensionality must fail fast."""
        item = MagicMock()
        item.embedding = [0.1, 0.2]  # length 2, expected 3
        response = MagicMock()
        response.data = [item]
        mock_openai_client.embeddings.create = AsyncMock(return_value=response)

        with pytest.raises(ExternalServiceError) as exc_info:
            await service.embed(["x"])
        assert "dim mismatch" in str(exc_info.value)
