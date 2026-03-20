"""Unit tests for ConversationService with topic_suggestion_id support."""

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.exceptions import NotFoundError, ValidationError
from coyo.models.conversation import Conversation
from coyo.models.topic_suggestion import TopicSuggestion, UserTopicSuggestion
from coyo.models.user import User
from coyo.services.conversation import ALLOWED_TOPICS, ConversationService


class TestStartConversationWithSuggestion:
    """Tests for ConversationService.start_conversation with topic_suggestion_id."""

    @pytest.fixture
    async def today_suggestion(self, db_session: AsyncSession) -> TopicSuggestion:
        """Create a topic suggestion for today in the DB."""
        suggestion = TopicSuggestion(
            title="Test Topic",
            summary="Test summary",
            source_keyword="test",
            article_content="Test content for conversation.",
            article_url=None,
            pool_type="common",
            generated_date=date.today(),
        )
        db_session.add(suggestion)
        await db_session.commit()
        await db_session.refresh(suggestion)
        return suggestion

    @pytest.fixture
    async def yesterday_suggestion(self, db_session: AsyncSession) -> TopicSuggestion:
        """Create a topic suggestion from yesterday in the DB."""
        suggestion = TopicSuggestion(
            title="Old Topic",
            summary="Old summary",
            source_keyword="old",
            article_content="Old content.",
            article_url=None,
            pool_type="common",
            generated_date=date.today() - timedelta(days=1),
        )
        db_session.add(suggestion)
        await db_session.commit()
        await db_session.refresh(suggestion)
        return suggestion

    @pytest.mark.unit
    async def test_valid_suggestion_creates_conversation(
        self,
        db_session: AsyncSession,
        test_user: User,
        today_suggestion: TopicSuggestion,
    ):
        """A valid, today's suggestion should create a conversation with topic_suggestion_id."""
        # Assign the suggestion to the user (IDOR check requires this)
        user_suggestion = UserTopicSuggestion(
            user_id=test_user.id,
            topic_suggestion_id=today_suggestion.id,
            relevance_score=1.0,
        )
        db_session.add(user_suggestion)
        await db_session.commit()

        service = ConversationService(db_session)
        conversation = await service.start_conversation(
            user_id=test_user.id,
            topic_suggestion_id=today_suggestion.id,
        )

        assert conversation.status == "active"
        assert conversation.topic_suggestion_id == today_suggestion.id

    @pytest.mark.unit
    async def test_unassigned_suggestion_raises_not_found(
        self,
        db_session: AsyncSession,
        test_user: User,
        today_suggestion: TopicSuggestion,
    ):
        """A valid suggestion not assigned to the user should raise NotFoundError (IDOR prevention)."""
        service = ConversationService(db_session)
        with pytest.raises(NotFoundError):
            await service.start_conversation(
                user_id=test_user.id,
                topic_suggestion_id=today_suggestion.id,
            )

    @pytest.mark.unit
    async def test_nonexistent_suggestion_raises_not_found(
        self, db_session: AsyncSession, test_user: User
    ):
        """A suggestion ID that doesn't exist should raise NotFoundError."""
        fake_id = uuid.uuid4()

        service = ConversationService(db_session)
        with pytest.raises(NotFoundError) as exc_info:
            await service.start_conversation(
                user_id=test_user.id,
                topic_suggestion_id=fake_id,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.unit
    async def test_expired_suggestion_raises_not_found(
        self,
        db_session: AsyncSession,
        test_user: User,
        yesterday_suggestion: TopicSuggestion,
    ):
        """A suggestion from a different date should raise NotFoundError."""
        service = ConversationService(db_session)
        with pytest.raises(NotFoundError):
            await service.start_conversation(
                user_id=test_user.id,
                topic_suggestion_id=yesterday_suggestion.id,
            )

    @pytest.mark.unit
    async def test_no_topic_no_suggestion_raises_validation(
        self, db_session: AsyncSession, test_user: User
    ):
        """Calling with neither topic nor suggestion_id should raise ValidationError."""
        service = ConversationService(db_session)
        with pytest.raises(ValidationError):
            await service.start_conversation(user_id=test_user.id)

    @pytest.mark.unit
    async def test_suggested_is_valid_topic(self):
        """The 'suggested' value should be in ALLOWED_TOPICS."""
        assert "suggested" in ALLOWED_TOPICS

    @pytest.mark.unit
    async def test_topic_with_regular_value_still_works(
        self, db_session: AsyncSession, test_user: User
    ):
        """Regular topic values should still work after the suggestion feature."""
        service = ConversationService(db_session)
        conversation = await service.start_conversation(
            user_id=test_user.id,
            topic="technology",
        )
        assert conversation.status == "active"
        assert conversation.topic_suggestion_id is None
