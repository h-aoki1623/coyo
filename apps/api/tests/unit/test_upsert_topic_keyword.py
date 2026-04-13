"""Unit tests for MemoryExtractionService._upsert_topic_keyword."""

import uuid
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.conversation import Conversation
from coyo.models.user import User
from coyo.repositories.interest import InterestRepository
from coyo.services.memory_extraction import MemoryExtractionService


@pytest.fixture(autouse=True)
def _mock_embedding_service() -> Generator[MagicMock, None, None]:
    """Stub get_embedding_service so tests never hit the real OpenAI API."""
    fake_service = MagicMock()

    async def _embed(texts: list[str]) -> list[list[float]]:
        return [[0.0] * 1536 for _ in texts]

    fake_service.embed = AsyncMock(side_effect=_embed)
    with patch(
        "coyo.services.embedding.get_embedding_service",
        return_value=fake_service,
    ) as _:
        yield fake_service


def _make_conversation(
    *,
    topic: str | None = None,
    topic_suggestion_id: uuid.UUID | None = None,
) -> Conversation:
    """Build a minimal Conversation mock."""
    conv = MagicMock(spec=Conversation)
    conv.topic = topic
    conv.topic_suggestion_id = topic_suggestion_id
    return conv


class TestUpsertTopicKeyword:
    """Tests for _upsert_topic_keyword static method."""

    @pytest.mark.unit
    async def test_skipped_when_keyword_already_in_seen(
        self, db_session: AsyncSession, test_user: User
    ):
        """Topic keyword already in seen_keywords -> no upsert call."""
        conv = _make_conversation(topic="sports")
        repo = AsyncMock(spec=InterestRepository)
        seen = {"sports"}

        await MemoryExtractionService._upsert_topic_keyword(
            db_session, repo, test_user.id, 1, conv, seen
        )

        repo.upsert_interest.assert_not_called()

    @pytest.mark.unit
    async def test_skipped_when_no_topic_resolved(
        self, db_session: AsyncSession, test_user: User
    ):
        """No topic keyword resolved (topic=None) -> no upsert call."""
        conv = _make_conversation(topic=None)
        repo = AsyncMock(spec=InterestRepository)
        seen: set[str] = set()

        await MemoryExtractionService._upsert_topic_keyword(
            db_session, repo, test_user.id, 1, conv, seen
        )

        repo.upsert_interest.assert_not_called()

    @pytest.mark.unit
    async def test_existing_interest_uses_existing_news_relevant(
        self, db_session: AsyncSession, test_user: User
    ):
        """When keyword exists in DB, upserts with existing is_news_relevant value."""
        conv = _make_conversation(topic="sports")
        repo = AsyncMock(spec=InterestRepository)
        seen: set[str] = set()

        # Mock the existing interest lookup
        existing_interest = MagicMock()
        existing_interest.is_news_relevant = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_interest

        with patch.object(
            db_session, "execute", new_callable=AsyncMock, return_value=mock_result
        ):
            await MemoryExtractionService._upsert_topic_keyword(
                db_session, repo, test_user.id, 1, conv, seen
            )

        repo.upsert_interest.assert_called_once()
        call_kwargs = repo.upsert_interest.call_args.kwargs
        assert call_kwargs["keyword"] == "sports"
        assert call_kwargs["is_news_relevant"] is False
        assert call_kwargs["embedding"] is None  # existing -> no embedding
        assert "sports" in seen

    @pytest.mark.unit
    async def test_new_keyword_computes_embedding(
        self, db_session: AsyncSession, test_user: User, _mock_embedding_service
    ):
        """When keyword is new (not in DB), computes embedding before upsert."""
        conv = _make_conversation(topic="sports")
        repo = AsyncMock(spec=InterestRepository)
        seen: set[str] = set()

        # No existing interest
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        with patch.object(
            db_session, "execute", new_callable=AsyncMock, return_value=mock_result
        ):
            await MemoryExtractionService._upsert_topic_keyword(
                db_session, repo, test_user.id, 1, conv, seen
            )

        repo.upsert_interest.assert_called_once()
        call_kwargs = repo.upsert_interest.call_args.kwargs
        assert call_kwargs["keyword"] == "sports"
        assert call_kwargs["keyword_type"] == "category"
        assert call_kwargs["is_news_relevant"] is True  # default for new
        assert call_kwargs["iab_category_id"] == "483"
        assert call_kwargs["embedding"] is not None
        assert len(call_kwargs["embedding"]) == 1536
        assert "sports" in seen

    @pytest.mark.unit
    async def test_adds_keyword_to_seen_set(
        self, db_session: AsyncSession, test_user: User
    ):
        """After successful upsert, keyword is added to seen_keywords."""
        conv = _make_conversation(topic="business")
        repo = AsyncMock(spec=InterestRepository)
        seen: set[str] = set()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        with patch.object(
            db_session, "execute", new_callable=AsyncMock, return_value=mock_result
        ):
            await MemoryExtractionService._upsert_topic_keyword(
                db_session, repo, test_user.id, 1, conv, seen
            )

        assert "business and finance" in seen

    @pytest.mark.unit
    async def test_skipped_when_suggested_topic_without_id(
        self, db_session: AsyncSession, test_user: User
    ):
        """topic='suggested' with no topic_suggestion_id -> skipped."""
        conv = _make_conversation(topic="suggested")
        repo = AsyncMock(spec=InterestRepository)
        seen: set[str] = set()

        await MemoryExtractionService._upsert_topic_keyword(
            db_session, repo, test_user.id, 1, conv, seen
        )

        repo.upsert_interest.assert_not_called()
