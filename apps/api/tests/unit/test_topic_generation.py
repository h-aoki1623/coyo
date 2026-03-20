"""Unit tests for the TopicGenerationService."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.services.topic_generation import TopicGenerationService, TopicSearchResult


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
# TopicGenerationService.generate_common_topics
# ---------------------------------------------------------------------------


class TestGenerateCommonTopics:
    """Tests for TopicGenerationService.generate_common_topics."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mock TopicSuggestionRepository."""
        repo = AsyncMock()
        repo.get_common_suggestions = AsyncMock(return_value=[])
        repo.create_suggestion = AsyncMock(return_value=_make_suggestion_mock())
        return repo

    @pytest.fixture
    def mock_llm(self):
        """Create a mock OpenAIClient that returns valid topic JSON via chat_with_tools."""
        from coyo.services.llm.base import TextChunk

        mock = MagicMock()

        async def mock_chat_with_tools(messages, options=None):
            json_text = _make_topic_json(3)
            yield TextChunk(text=json_text)

        mock.chat_with_tools = mock_chat_with_tools
        return mock

    @pytest.fixture
    def service(self, db_session: AsyncSession, mock_repo, mock_llm):
        """Create a TopicGenerationService with mocked dependencies."""
        svc = TopicGenerationService.__new__(TopicGenerationService)
        svc._session = db_session
        svc._repo = mock_repo
        svc._llm = mock_llm
        return svc

    @pytest.mark.unit
    async def test_generates_topics_and_returns_count(self, service, mock_repo):
        count = await service.generate_common_topics()
        assert count == 3
        assert mock_repo.create_suggestion.call_count == 3

    @pytest.mark.unit
    async def test_idempotent_when_already_generated(self, service, mock_repo):
        """If topics already exist for today, skip generation."""
        mock_repo.get_common_suggestions = AsyncMock(
            return_value=[_make_suggestion_mock() for _ in range(3)]
        )
        count = await service.generate_common_topics()
        assert count == 3
        mock_repo.create_suggestion.assert_not_called()

    @pytest.mark.unit
    async def test_limits_to_max_topics(self, service, mock_repo, mock_llm):
        """Even if LLM returns more than 3 topics, only 3 are created."""
        from coyo.services.llm.base import TextChunk

        async def many_topics(messages, options=None):
            yield TextChunk(text=_make_topic_json(5))

        mock_llm.chat_with_tools = many_topics
        count = await service.generate_common_topics()
        assert count == 3
        assert mock_repo.create_suggestion.call_count == 3

    @pytest.mark.unit
    async def test_handles_save_error_gracefully(self, service, mock_repo):
        """If one topic fails to save with IntegrityError, others still proceed."""
        call_count = 0

        async def create_with_error(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise IntegrityError("duplicate", {}, Exception())
            return _make_suggestion_mock()

        mock_repo.create_suggestion = create_with_error
        count = await service.generate_common_topics()
        assert count == 2  # 1st and 3rd succeed

    @pytest.mark.unit
    async def test_calls_create_suggestion_with_correct_args(self, service, mock_repo):
        await service.generate_common_topics()
        first_call = mock_repo.create_suggestion.call_args_list[0]
        kwargs = first_call.kwargs
        assert kwargs["title"] == "Topic 0"
        assert kwargs["summary"] == "Summary 0"
        assert kwargs["source_keyword"] == "kw0"
        assert kwargs["pool_type"] == "common"
        assert kwargs["generated_date"] == date.today()


# ---------------------------------------------------------------------------
# TopicGenerationService.assign_to_users
# ---------------------------------------------------------------------------


class TestAssignToUsers:
    """Tests for TopicGenerationService.assign_to_users."""

    @pytest.fixture
    def mock_repo(self):
        repo = AsyncMock()
        suggestions = [_make_suggestion_mock() for _ in range(2)]
        repo.get_common_suggestions = AsyncMock(return_value=suggestions)
        user_ids = [uuid.uuid4(), uuid.uuid4()]
        repo.get_active_user_ids = AsyncMock(return_value=user_ids)
        repo.create_user_suggestion = AsyncMock()
        return repo

    @pytest.fixture
    def service(self, db_session: AsyncSession, mock_repo):
        svc = TopicGenerationService.__new__(TopicGenerationService)
        svc._session = db_session
        svc._repo = mock_repo
        svc._llm = MagicMock()
        return svc

    @pytest.mark.unit
    async def test_creates_user_suggestion_links(self, service, mock_repo):
        count = await service.assign_to_users()
        # 2 users x 2 suggestions = 4 links
        assert count == 4
        assert mock_repo.create_user_suggestion.call_count == 4

    @pytest.mark.unit
    async def test_returns_zero_when_no_suggestions(self, service, mock_repo):
        mock_repo.get_common_suggestions = AsyncMock(return_value=[])
        count = await service.assign_to_users()
        assert count == 0

    @pytest.mark.unit
    async def test_handles_integrity_error_for_duplicates(self, service, mock_repo):
        """IntegrityError (duplicate) should be silently skipped."""
        call_count = 0

        async def create_with_dup(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise IntegrityError("duplicate", {}, Exception())
            return MagicMock()

        mock_repo.create_user_suggestion = create_with_dup

        # Mock begin_nested as an async context manager that lets
        # IntegrityError propagate (to be caught by the except clause).
        class FakeNested:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False  # don't suppress — let except IntegrityError handle it

        service._session.begin_nested = lambda: FakeNested()

        count = await service.assign_to_users()
        # 1 fails (IntegrityError caught by except), 3 succeed
        assert count == 3

    @pytest.mark.unit
    async def test_relevance_score_decreases_with_rank(self, service, mock_repo):
        await service.assign_to_users()
        # Check first user's calls: rank 1 -> score 1.0, rank 2 -> score 0.5
        calls = mock_repo.create_user_suggestion.call_args_list
        first_call_kwargs = calls[0].kwargs
        second_call_kwargs = calls[1].kwargs
        assert first_call_kwargs["relevance_score"] == 1.0
        assert second_call_kwargs["relevance_score"] == 0.5
