"""Unit tests for TopicGenerationService.generate_common_topics (keyword-driven rewrite)."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.services.topic_generation import TopicGenerationService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_topic_json(count: int = 3) -> str:
    """Build a valid JSON string for TopicSearchResult with `count` topics."""
    topics = []
    for i in range(count):
        topics.append(
            f'{{"title":"Topic {i}","summary":"Summary {i}",'
            f'"source_keyword":"kw{i}","article_content":"Content {i}"}}'
        )
    return '{"topics":[' + ",".join(topics) + "]}"


def _make_personal_topic_json(index: int = 0) -> str:
    """Build a valid JSON string for PersonalTopicItem (single topic)."""
    return (
        f'{{"title":"Topic {index}","summary":"Summary {index}",'
        f'"article_content":"Content {index}"}}'
    )


def _make_suggestion_mock(suggestion_id: uuid.UUID | None = None):
    """Create a mock TopicSuggestion object."""
    mock = MagicMock()
    mock.id = suggestion_id or uuid.uuid4()
    mock.title = "Test Topic"
    mock.summary = "Test Summary"
    mock.source_keyword = "test"
    mock.article_content = "Test content"
    return mock


# ---------------------------------------------------------------------------
# Tests for keyword-driven generate_common_topics
# ---------------------------------------------------------------------------


class TestGenerateCommonTopicsKeywordDriven:
    """Tests for generate_common_topics with interest-keyword-driven generation."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mock TopicSuggestionRepository."""
        repo = AsyncMock()
        repo.get_common_suggestions = AsyncMock(return_value=[])
        repo.create_suggestion = AsyncMock(return_value=_make_suggestion_mock())
        return repo

    @pytest.fixture
    def mock_interest_repo(self):
        """Create a mock InterestRepository."""
        repo = AsyncMock()
        repo.get_global_top_keywords = AsyncMock(
            return_value=["sports", "technology", "music"]
        )
        return repo

    @pytest.fixture
    def mock_llm(self):
        """Create a mock OpenAIClient that returns valid personal topic JSON."""
        from coyo.services.llm.base import TextChunk

        mock = MagicMock()

        async def mock_chat_with_tools(messages, options=None):
            yield TextChunk(text=_make_personal_topic_json())

        mock.chat_with_tools = mock_chat_with_tools
        return mock

    @pytest.fixture
    def service(
        self,
        db_session: AsyncSession,
        mock_repo,
        mock_interest_repo,
        mock_llm,
    ):
        """Create a TopicGenerationService with mocked dependencies."""
        svc = TopicGenerationService.__new__(TopicGenerationService)
        svc._session = db_session
        svc._repo = mock_repo
        svc._interest_repo = mock_interest_repo
        svc._llm = mock_llm
        return svc

    @pytest.mark.unit
    async def test_uses_top_keywords_when_available(
        self, service, mock_repo, mock_interest_repo
    ):
        """When top keywords exist, generates topics per keyword."""
        count = await service.generate_common_topics()

        mock_interest_repo.get_global_top_keywords.assert_called_once()
        assert count == 3
        assert mock_repo.create_suggestion.call_count == 3

    @pytest.mark.unit
    async def test_creates_suggestion_with_keyword_as_source(
        self, service, mock_repo
    ):
        """Each created suggestion uses the keyword as source_keyword."""
        await service.generate_common_topics()

        calls = mock_repo.create_suggestion.call_args_list
        source_keywords = [c.kwargs["source_keyword"] for c in calls]
        assert source_keywords == ["sports", "technology", "music"]

    @pytest.mark.unit
    async def test_falls_back_to_trending_when_no_keywords(
        self, service, mock_repo, mock_interest_repo, mock_llm
    ):
        """Falls back to LLM trending search when no keywords available."""
        from coyo.services.llm.base import TextChunk

        mock_interest_repo.get_global_top_keywords = AsyncMock(return_value=[])

        # Override LLM to return 3 topics for the fallback path
        async def mock_trending(messages, options=None):
            yield TextChunk(text=_make_topic_json(3))

        mock_llm.chat_with_tools = mock_trending

        count = await service.generate_common_topics()

        assert count == 3
        assert mock_repo.create_suggestion.call_count == 3

    @pytest.mark.unit
    async def test_idempotent_when_already_generated(
        self, service, mock_repo, mock_interest_repo
    ):
        """If topics already exist for today, skip generation and return count."""
        mock_repo.get_common_suggestions = AsyncMock(
            return_value=[_make_suggestion_mock() for _ in range(3)]
        )
        count = await service.generate_common_topics()

        assert count == 3
        mock_repo.create_suggestion.assert_not_called()
        mock_interest_repo.get_global_top_keywords.assert_not_called()

    @pytest.mark.unit
    async def test_handles_fetch_failure_gracefully(
        self, service, mock_repo, mock_llm
    ):
        """If _fetch_personal_topic returns None for a keyword, it is skipped."""
        from coyo.services.llm.base import TextChunk

        call_count = 0

        async def mock_chat_sometimes_fail(messages, options=None):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                # Return invalid JSON to cause parse failure
                yield TextChunk(text="invalid json")
            else:
                yield TextChunk(text=_make_personal_topic_json())

        mock_llm.chat_with_tools = mock_chat_sometimes_fail
        # Also stub out structured fallback to fail
        mock_llm.structured = AsyncMock(side_effect=Exception("structured failed"))

        count = await service.generate_common_topics()

        # 3 keywords attempted, 1 fails => 2 succeed
        assert count == 2

    @pytest.mark.unit
    async def test_suggestion_pool_type_is_common(self, service, mock_repo):
        """All created suggestions have pool_type='common'."""
        await service.generate_common_topics()

        for call in mock_repo.create_suggestion.call_args_list:
            assert call.kwargs["pool_type"] == "common"

    @pytest.mark.unit
    async def test_suggestion_generated_date_is_today(self, service, mock_repo):
        """All created suggestions have generated_date=today."""
        await service.generate_common_topics()

        for call in mock_repo.create_suggestion.call_args_list:
            assert call.kwargs["generated_date"] == date.today()
