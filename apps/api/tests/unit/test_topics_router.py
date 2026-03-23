"""Unit tests for the topics router endpoints."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.user import User


# ---------------------------------------------------------------------------
# POST /api/topics/generate — cron endpoint
# ---------------------------------------------------------------------------


class TestGenerateTopicsEndpoint:
    """Tests for the POST /api/topics/generate cron endpoint."""

    @pytest.mark.integration
    async def test_valid_cron_secret_returns_200(self, client: AsyncClient, mock_settings):
        """Valid X-Cron-Secret header should succeed."""
        mock_settings.cron_secret = "test-cron-secret"

        with (
            patch("coyo.routers.topics.get_settings", return_value=mock_settings),
            patch("coyo.routers.topics.TopicGenerationService") as MockService,
        ):
            mock_svc = AsyncMock()
            mock_svc.generate_common_topics = AsyncMock(return_value=3)
            mock_svc.assign_to_users = AsyncMock(return_value=10)
            mock_svc.generate_personal_topics = AsyncMock(return_value=2)
            MockService.return_value = mock_svc

            response = await client.post(
                "/api/topics/generate",
                headers={"X-Cron-Secret": "test-cron-secret"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["topics_generated"] == 3
        assert data["users_assigned"] == 10
        assert data["personal_topics_generated"] == 2

    @pytest.mark.integration
    async def test_missing_cron_secret_returns_403(self, client: AsyncClient, mock_settings):
        """Missing X-Cron-Secret header should return 403."""
        mock_settings.cron_secret = "test-cron-secret"

        with patch("coyo.routers.topics.get_settings", return_value=mock_settings):
            response = await client.post("/api/topics/generate")
        assert response.status_code == 403

    @pytest.mark.integration
    async def test_invalid_cron_secret_returns_403(self, client: AsyncClient, mock_settings):
        """Wrong X-Cron-Secret header should return 403."""
        mock_settings.cron_secret = "test-cron-secret"

        with patch("coyo.routers.topics.get_settings", return_value=mock_settings):
            response = await client.post(
                "/api/topics/generate",
                headers={"X-Cron-Secret": "wrong-secret"},
            )
        assert response.status_code == 403

    @pytest.mark.integration
    async def test_no_cron_secret_configured_returns_403(
        self, client: AsyncClient, mock_settings
    ):
        """When cron_secret is not configured (None), should return 403."""
        mock_settings.cron_secret = None

        with patch("coyo.routers.topics.get_settings", return_value=mock_settings):
            response = await client.post(
                "/api/topics/generate",
                headers={"X-Cron-Secret": "any-value"},
            )
        assert response.status_code == 403

    @pytest.mark.integration
    async def test_personal_topic_failure_doesnt_break_response(
        self, client: AsyncClient, mock_settings
    ):
        """If generate_personal_topics raises, response still returns 200 with 0."""
        mock_settings.cron_secret = "test-cron-secret"

        with (
            patch("coyo.routers.topics.get_settings", return_value=mock_settings),
            patch("coyo.routers.topics.TopicGenerationService") as MockService,
        ):
            mock_svc = AsyncMock()
            mock_svc.generate_common_topics = AsyncMock(return_value=3)
            mock_svc.assign_to_users = AsyncMock(return_value=10)
            mock_svc.generate_personal_topics = AsyncMock(
                side_effect=Exception("LLM down")
            )
            MockService.return_value = mock_svc

            response = await client.post(
                "/api/topics/generate",
                headers={"X-Cron-Secret": "test-cron-secret"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["personal_topics_generated"] == 0
        assert data["topics_generated"] == 3
        assert data["users_assigned"] == 10


# ---------------------------------------------------------------------------
# GET /api/topics/suggestions
# ---------------------------------------------------------------------------


class TestGetSuggestionsEndpoint:
    """Tests for the GET /api/topics/suggestions endpoint."""

    @pytest.mark.integration
    async def test_returns_empty_when_no_suggestions(self, client: AsyncClient):
        """When no suggestions exist, return empty lists."""
        with patch(
            "coyo.routers.topics.TopicSuggestionRepository"
        ) as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_suggestions_for_user = AsyncMock(return_value=[])
            MockRepo.return_value = mock_repo

            response = await client.get("/api/topics/suggestions")

        assert response.status_code == 200
        data = response.json()
        assert data["personal"] == []
        assert data["trending"] == []

    @pytest.mark.integration
    async def test_returns_suggestions_grouped_by_pool(self, client: AsyncClient):
        """Suggestions should be grouped into personal and trending."""
        common_suggestion = MagicMock()
        common_suggestion.id = uuid.uuid4()
        common_suggestion.title = "Trending News"
        common_suggestion.summary = "Summary"
        common_suggestion.source_keyword = "news"
        common_suggestion.pool_type = "common"

        personal_suggestion = MagicMock()
        personal_suggestion.id = uuid.uuid4()
        personal_suggestion.title = "Personal Topic"
        personal_suggestion.summary = "For you"
        personal_suggestion.source_keyword = "personal"
        personal_suggestion.pool_type = "personal"

        with patch(
            "coyo.routers.topics.TopicSuggestionRepository"
        ) as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_suggestions_for_user = AsyncMock(
                return_value=[
                    (personal_suggestion, 1.0),
                    (common_suggestion, 0.5),
                ]
            )
            MockRepo.return_value = mock_repo

            response = await client.get("/api/topics/suggestions")

        assert response.status_code == 200
        data = response.json()
        assert len(data["personal"]) == 1
        assert len(data["trending"]) == 1
        assert data["personal"][0]["title"] == "Personal Topic"
        assert data["trending"][0]["title"] == "Trending News"

    @pytest.mark.integration
    async def test_suggestions_have_camel_case_keys(self, client: AsyncClient):
        """Response should use camelCase field names."""
        suggestion = MagicMock()
        suggestion.id = uuid.uuid4()
        suggestion.title = "Test"
        suggestion.summary = "Sum"
        suggestion.source_keyword = "kw"
        suggestion.pool_type = "common"

        with patch(
            "coyo.routers.topics.TopicSuggestionRepository"
        ) as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_suggestions_for_user = AsyncMock(
                return_value=[(suggestion, 1.0)]
            )
            MockRepo.return_value = mock_repo

            response = await client.get("/api/topics/suggestions")

        assert response.status_code == 200
        data = response.json()
        item = data["trending"][0]
        assert "sourceKeyword" in item
        assert "source_keyword" not in item
