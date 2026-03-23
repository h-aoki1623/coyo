"""Unit tests for the InterestExtractionService."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.conversation import Conversation
from coyo.models.turn import Turn
from coyo.models.user import User
from coyo.models.user_interest import UserInterest
from coyo.services.interest_extraction import (
    ExtractionResult,
    InterestExtractionService,
    KeywordItem,
)


class TestKeywordItem:
    """Tests for keyword normalization."""

    @pytest.mark.unit
    def test_keyword_lowercased(self):
        item = KeywordItem(keyword="Tennis", is_news_relevant=True)
        assert item.keyword == "tennis"

    @pytest.mark.unit
    def test_keyword_stripped(self):
        item = KeywordItem(keyword="  tennis  ", is_news_relevant=True)
        assert item.keyword == "tennis"

    @pytest.mark.unit
    def test_keyword_lowercased_and_stripped(self):
        item = KeywordItem(keyword="  Kei Nishikori  ", is_news_relevant=True)
        assert item.keyword == "kei nishikori"


class TestExtractionResult:
    """Tests for ExtractionResult schema."""

    @pytest.mark.unit
    def test_default_empty_lists(self):
        result = ExtractionResult()
        assert result.topics == []
        assert result.entities == []

    @pytest.mark.unit
    def test_parse_valid_json(self):
        result = ExtractionResult.model_validate_json(
            '{"topics": [{"keyword": "tennis", "is_news_relevant": true}], '
            '"entities": [{"keyword": "kei nishikori", "is_news_relevant": true}]}'
        )
        assert len(result.topics) == 1
        assert result.topics[0].keyword == "tennis"
        assert len(result.entities) == 1
        assert result.entities[0].keyword == "kei nishikori"


class TestBuildTranscript:
    """Tests for transcript building."""

    @pytest.mark.unit
    async def test_build_transcript_user_turns_only(
        self, db_session: AsyncSession, test_user: User
    ):
        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        turns = [
            Turn(
                conversation_id=conversation.id,
                role="user",
                text="I love tennis.",
                sequence=1,
                correction_status="none",
            ),
            Turn(
                conversation_id=conversation.id,
                role="ai",
                text="That's great! Do you play often?",
                sequence=2,
                correction_status="none",
            ),
            Turn(
                conversation_id=conversation.id,
                role="user",
                text="Yes, I watch Kei Nishikori.",
                sequence=3,
                correction_status="none",
            ),
        ]
        for turn in turns:
            db_session.add(turn)
        await db_session.flush()

        transcript = await InterestExtractionService._build_transcript(
            db_session, conversation.id
        )
        assert "I love tennis." in transcript
        assert "Yes, I watch Kei Nishikori." in transcript
        assert "That's great!" not in transcript

    @pytest.mark.unit
    async def test_build_transcript_empty_conversation(
        self, db_session: AsyncSession, test_user: User
    ):
        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        transcript = await InterestExtractionService._build_transcript(
            db_session, conversation.id
        )
        assert transcript == ""


class TestExtract:
    """Tests for the core extraction logic."""

    @pytest.mark.unit
    async def test_extract_skips_already_extracted(
        self, db_session: AsyncSession, test_user: User
    ):
        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
            interests_extracted=True,
        )
        db_session.add(conversation)
        await db_session.flush()

        # Should return without calling LLM
        await InterestExtractionService._extract(
            db_session, conversation.id, test_user.id
        )

        # conversation_count should NOT be incremented
        await db_session.refresh(test_user)
        assert test_user.conversation_count == 0

    @pytest.mark.unit
    async def test_extract_skips_empty_transcript(
        self, db_session: AsyncSession, test_user: User
    ):
        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        await InterestExtractionService._extract(
            db_session, conversation.id, test_user.id
        )

        await db_session.refresh(conversation)
        assert conversation.interests_extracted is True
        # conversation_count should still be incremented
        await db_session.refresh(test_user)
        assert test_user.conversation_count == 1

    @pytest.mark.unit
    async def test_extract_creates_interests(
        self, db_session: AsyncSession, test_user: User
    ):
        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        turn = Turn(
            conversation_id=conversation.id,
            role="user",
            text="I love watching NBA basketball.",
            sequence=1,
            correction_status="none",
        )
        db_session.add(turn)
        await db_session.flush()

        mock_result = ExtractionResult(
            topics=[KeywordItem(keyword="basketball", is_news_relevant=True)],
            entities=[KeywordItem(keyword="nba", is_news_relevant=True)],
        )

        with patch.object(
            InterestExtractionService,
            "_call_llm",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            await InterestExtractionService._extract(
                db_session, conversation.id, test_user.id
            )

        await db_session.refresh(conversation)
        assert conversation.interests_extracted is True

        await db_session.refresh(test_user)
        assert test_user.conversation_count == 1

        stmt = select(UserInterest).where(UserInterest.user_id == test_user.id)
        result = await db_session.execute(stmt)
        interests = result.scalars().all()
        assert len(interests) == 2
        keywords = {i.keyword for i in interests}
        assert "basketball" in keywords
        assert "nba" in keywords

    @pytest.mark.unit
    async def test_extract_deduplicates_across_topics_and_entities(
        self, db_session: AsyncSession, test_user: User
    ):
        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        turn = Turn(
            conversation_id=conversation.id,
            role="user",
            text="I love tennis.",
            sequence=1,
            correction_status="none",
        )
        db_session.add(turn)
        await db_session.flush()

        # "tennis" appears in both topics and entities
        mock_result = ExtractionResult(
            topics=[KeywordItem(keyword="tennis", is_news_relevant=True)],
            entities=[KeywordItem(keyword="tennis", is_news_relevant=True)],
        )

        with patch.object(
            InterestExtractionService,
            "_call_llm",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            await InterestExtractionService._extract(
                db_session, conversation.id, test_user.id
            )

        stmt = select(UserInterest).where(UserInterest.user_id == test_user.id)
        result = await db_session.execute(stmt)
        interests = result.scalars().all()
        # Should only be 1, not 2 (deduplicated)
        assert len(interests) == 1
        assert interests[0].keyword == "tennis"

    @pytest.mark.unit
    async def test_extract_limits_topics_and_entities(
        self, db_session: AsyncSession, test_user: User
    ):
        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        turn = Turn(
            conversation_id=conversation.id,
            role="user",
            text="I talked about many things.",
            sequence=1,
            correction_status="none",
        )
        db_session.add(turn)
        await db_session.flush()

        # LLM returns more than limits
        mock_result = ExtractionResult(
            topics=[
                KeywordItem(keyword=f"topic{i}", is_news_relevant=True)
                for i in range(10)
            ],
            entities=[
                KeywordItem(keyword=f"entity{i}", is_news_relevant=True)
                for i in range(10)
            ],
        )

        with patch.object(
            InterestExtractionService,
            "_call_llm",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            await InterestExtractionService._extract(
                db_session, conversation.id, test_user.id
            )

        stmt = select(UserInterest).where(UserInterest.user_id == test_user.id)
        result = await db_session.execute(stmt)
        interests = result.scalars().all()
        # At most 3 topics + 5 entities = 8
        assert len(interests) <= 8

    @pytest.mark.unit
    async def test_extract_nonexistent_conversation(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should not raise, just log and return."""
        await InterestExtractionService._extract(
            db_session, uuid.uuid4(), test_user.id
        )

    @pytest.mark.unit
    async def test_extract_nonexistent_user(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should not raise, just log and return."""
        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        await InterestExtractionService._extract(
            db_session, conversation.id, uuid.uuid4()
        )

    @pytest.mark.unit
    async def test_extract_user_mismatch_returns_without_processing(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should abort if conversation.user_id != provided user_id."""
        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        other_user_id = uuid.uuid4()
        await InterestExtractionService._extract(
            db_session, conversation.id, other_user_id
        )

        # conversation_count should NOT be incremented
        await db_session.refresh(test_user)
        assert test_user.conversation_count == 0
        # interests_extracted should NOT be set
        await db_session.refresh(conversation)
        assert conversation.interests_extracted is False


class TestExtractPublicMethod:
    """Tests for the public extract() method used by Cloud Tasks."""

    @pytest.mark.unit
    async def test_extract_raises_on_failure(self, mock_settings):
        """Unlike extract_background, extract() should propagate exceptions."""
        conv_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_session = AsyncMock(spec=AsyncSession)

        with (
            patch(
                "coyo.services.interest_extraction.get_session_factory"
            ) as mock_factory,
            patch.object(
                InterestExtractionService,
                "_extract",
                new_callable=AsyncMock,
                side_effect=RuntimeError("DB connection lost"),
            ),
        ):
            mock_factory.return_value = MagicMock(
                __call__=MagicMock(return_value=mock_session)
            )
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(RuntimeError, match="DB connection lost"):
                await InterestExtractionService.extract(conv_id, user_id)

    @pytest.mark.unit
    async def test_extract_background_swallows_exceptions(self, mock_settings):
        """extract_background should NOT propagate exceptions (logs only)."""
        conv_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_session = AsyncMock(spec=AsyncSession)

        with (
            patch(
                "coyo.services.interest_extraction.get_session_factory"
            ) as mock_factory,
            patch.object(
                InterestExtractionService,
                "_extract",
                new_callable=AsyncMock,
                side_effect=RuntimeError("DB connection lost"),
            ),
        ):
            mock_factory.return_value = MagicMock(
                __call__=MagicMock(return_value=mock_session)
            )
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            # Should NOT raise
            await InterestExtractionService.extract_background(conv_id, user_id)
