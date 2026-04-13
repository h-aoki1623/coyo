"""Unit tests for MemoryExtractionService._resolve_topic_keyword."""

import uuid
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.conversation import Conversation
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
    ):
        yield fake_service


def _make_conversation(
    *,
    topic: str | None = None,
    topic_suggestion_id: uuid.UUID | None = None,
) -> Conversation:
    """Build a minimal Conversation with topic fields set."""
    conv = MagicMock(spec=Conversation)
    conv.topic = topic
    conv.topic_suggestion_id = topic_suggestion_id
    return conv


class TestResolveTopicKeyword:
    """Tests for _resolve_topic_keyword static method."""

    @pytest.mark.unit
    async def test_suggested_topic_returns_source_keyword(
        self, db_session: AsyncSession
    ):
        """Suggested topic (topic_suggestion_id set) returns (source_keyword, None)."""
        suggestion_id = uuid.uuid4()
        conv = _make_conversation(
            topic="suggested", topic_suggestion_id=suggestion_id
        )

        mock_suggestion = MagicMock()
        mock_suggestion.source_keyword = "  NBA  "

        with patch.object(db_session, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_suggestion

            keyword, iab_id = await MemoryExtractionService._resolve_topic_keyword(
                db_session, conv
            )

        assert keyword == "nba"
        assert iab_id is None

    @pytest.mark.unit
    async def test_fixed_topic_business_returns_iab_mapping(
        self, db_session: AsyncSession
    ):
        """Fixed topic 'business' returns ('business and finance', '52')."""
        conv = _make_conversation(topic="business")

        keyword, iab_id = await MemoryExtractionService._resolve_topic_keyword(
            db_session, conv
        )

        assert keyword == "business and finance"
        assert iab_id == "52"

    @pytest.mark.unit
    async def test_fixed_topic_sports_returns_iab_mapping(
        self, db_session: AsyncSession
    ):
        """Fixed topic 'sports' returns ('sports', '483')."""
        conv = _make_conversation(topic="sports")

        keyword, iab_id = await MemoryExtractionService._resolve_topic_keyword(
            db_session, conv
        )

        assert keyword == "sports"
        assert iab_id == "483"

    @pytest.mark.unit
    async def test_fixed_topic_technology_returns_iab_mapping(
        self, db_session: AsyncSession
    ):
        """Fixed topic 'technology' returns ('technology & computing', '596')."""
        conv = _make_conversation(topic="technology")

        keyword, iab_id = await MemoryExtractionService._resolve_topic_keyword(
            db_session, conv
        )

        assert keyword == "technology & computing"
        assert iab_id == "596"

    @pytest.mark.unit
    async def test_fixed_topic_politics_returns_iab_mapping(
        self, db_session: AsyncSession
    ):
        """Fixed topic 'politics' returns ('politics', '386')."""
        conv = _make_conversation(topic="politics")

        keyword, iab_id = await MemoryExtractionService._resolve_topic_keyword(
            db_session, conv
        )

        assert keyword == "politics"
        assert iab_id == "386"

    @pytest.mark.unit
    async def test_fixed_topic_entertainment_returns_iab_mapping(
        self, db_session: AsyncSession
    ):
        """Fixed topic 'entertainment' returns ('entertainment', 'JLBCU7')."""
        conv = _make_conversation(topic="entertainment")

        keyword, iab_id = await MemoryExtractionService._resolve_topic_keyword(
            db_session, conv
        )

        assert keyword == "entertainment"
        assert iab_id == "JLBCU7"

    @pytest.mark.unit
    async def test_suggested_topic_without_suggestion_id_returns_none(
        self, db_session: AsyncSession
    ):
        """topic='suggested' with no topic_suggestion_id returns (None, None)."""
        conv = _make_conversation(topic="suggested")

        keyword, iab_id = await MemoryExtractionService._resolve_topic_keyword(
            db_session, conv
        )

        assert keyword is None
        assert iab_id is None

    @pytest.mark.unit
    async def test_none_topic_returns_none(self, db_session: AsyncSession):
        """topic=None returns (None, None)."""
        conv = _make_conversation(topic=None)

        keyword, iab_id = await MemoryExtractionService._resolve_topic_keyword(
            db_session, conv
        )

        assert keyword is None
        assert iab_id is None

    @pytest.mark.unit
    async def test_unknown_fixed_topic_returns_none(self, db_session: AsyncSession):
        """An unknown topic key (not in _FIXED_TOPIC_IAB) returns (None, None)."""
        conv = _make_conversation(topic="cooking")

        keyword, iab_id = await MemoryExtractionService._resolve_topic_keyword(
            db_session, conv
        )

        assert keyword is None
        assert iab_id is None

    @pytest.mark.unit
    async def test_suggested_topic_with_missing_suggestion_returns_none(
        self, db_session: AsyncSession
    ):
        """topic_suggestion_id set but suggestion not found in DB returns (None, None)."""
        suggestion_id = uuid.uuid4()
        conv = _make_conversation(
            topic="suggested", topic_suggestion_id=suggestion_id
        )

        with patch.object(db_session, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            keyword, iab_id = await MemoryExtractionService._resolve_topic_keyword(
                db_session, conv
            )

        assert keyword is None
        assert iab_id is None

    @pytest.mark.unit
    async def test_fixed_topic_case_insensitive(self, db_session: AsyncSession):
        """Fixed topic lookup is case-insensitive."""
        conv = _make_conversation(topic="SPORTS")

        keyword, iab_id = await MemoryExtractionService._resolve_topic_keyword(
            db_session, conv
        )

        assert keyword == "sports"
        assert iab_id == "483"
