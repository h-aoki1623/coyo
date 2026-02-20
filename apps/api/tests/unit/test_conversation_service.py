"""Unit tests for the ConversationService."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from coto.exceptions import ConversationStateError, NotFoundError, ValidationError
from coto.models.conversation import Conversation
from coto.models.turn import Turn
from coto.models.user import User
from coto.services.conversation import ALLOWED_TOPICS, ConversationService, FeedbackStats


class TestConversationServiceStart:
    """Tests for ConversationService.start_conversation."""

    @pytest.mark.unit
    async def test_start_conversation_valid_topic(
        self, db_session: AsyncSession, test_user
    ):
        service = ConversationService(db_session)
        conversation = await service.start_conversation(
            user_id=test_user.id,
            topic="technology",
        )
        assert conversation.topic == "technology"
        assert conversation.status == "active"
        assert conversation.user_id == test_user.id

    @pytest.mark.unit
    async def test_start_conversation_all_valid_topics(
        self, db_session: AsyncSession, test_user
    ):
        """Verify all allowed topics are accepted."""
        service = ConversationService(db_session)
        for topic in ALLOWED_TOPICS:
            conversation = await service.start_conversation(
                user_id=test_user.id,
                topic=topic,
            )
            assert conversation.topic == topic

    @pytest.mark.unit
    async def test_start_conversation_invalid_topic_raises_validation_error(
        self, db_session: AsyncSession, test_user
    ):
        service = ConversationService(db_session)
        with pytest.raises(ValidationError) as exc_info:
            await service.start_conversation(
                user_id=test_user.id,
                topic="cooking",
            )
        assert "Invalid topic" in exc_info.value.message
        assert exc_info.value.status_code == 422

    @pytest.mark.unit
    async def test_start_conversation_empty_topic_raises_validation_error(
        self, db_session: AsyncSession, test_user
    ):
        service = ConversationService(db_session)
        with pytest.raises(ValidationError):
            await service.start_conversation(
                user_id=test_user.id,
                topic="",
            )

    @pytest.mark.unit
    async def test_start_conversation_default_time_limit(
        self, db_session: AsyncSession, test_user
    ):
        service = ConversationService(db_session)
        conversation = await service.start_conversation(
            user_id=test_user.id,
            topic="sports",
        )
        assert conversation.time_limit_seconds == 1800

    @pytest.mark.unit
    async def test_start_conversation_custom_time_limit(
        self, db_session: AsyncSession, test_user
    ):
        service = ConversationService(db_session)
        conversation = await service.start_conversation(
            user_id=test_user.id,
            topic="sports",
            time_limit_seconds=600,
        )
        assert conversation.time_limit_seconds == 600

    @pytest.mark.unit
    async def test_start_conversation_has_id(
        self, db_session: AsyncSession, test_user
    ):
        """Verify that the conversation is assigned an ID after creation."""
        service = ConversationService(db_session)
        conversation = await service.start_conversation(
            user_id=test_user.id,
            topic="technology",
        )
        assert conversation.id is not None


class TestConversationServiceGet:
    """Tests for ConversationService.get_conversation."""

    @pytest.mark.unit
    async def test_get_existing_conversation(
        self, db_session: AsyncSession, test_user: User, test_conversation: Conversation
    ):
        service = ConversationService(db_session)
        conversation = await service.get_conversation(test_conversation.id, test_user.id)
        assert conversation.id == test_conversation.id
        assert conversation.topic == "technology"

    @pytest.mark.unit
    async def test_get_nonexistent_conversation_raises_not_found(
        self, db_session: AsyncSession, test_user: User
    ):
        service = ConversationService(db_session)
        with pytest.raises(NotFoundError) as exc_info:
            await service.get_conversation(uuid.uuid4(), test_user.id)
        assert exc_info.value.status_code == 404
        assert "Conversation" in exc_info.value.message

    @pytest.mark.unit
    async def test_get_conversation_wrong_user_raises_not_found(
        self, db_session: AsyncSession, test_conversation: Conversation
    ):
        """Verify that accessing another user's conversation returns NotFound."""
        service = ConversationService(db_session)
        other_user_id = uuid.uuid4()
        with pytest.raises(NotFoundError):
            await service.get_conversation(test_conversation.id, other_user_id)


class TestConversationServiceEnd:
    """Tests for ConversationService.end_conversation."""

    @pytest.mark.unit
    async def test_end_active_conversation(
        self, db_session: AsyncSession, test_user: User, test_conversation: Conversation
    ):
        service = ConversationService(db_session)
        ended = await service.end_conversation(test_conversation.id, test_user.id)
        assert ended.status == "completed"
        assert ended.ended_at is not None
        assert ended.duration_seconds is not None
        assert ended.duration_seconds >= 0

    @pytest.mark.unit
    async def test_end_paused_conversation(
        self, db_session: AsyncSession, test_user: User, paused_conversation: Conversation
    ):
        service = ConversationService(db_session)
        ended = await service.end_conversation(paused_conversation.id, test_user.id)
        assert ended.status == "completed"

    @pytest.mark.unit
    async def test_end_completed_conversation_raises_state_error(
        self, db_session: AsyncSession, test_user: User, completed_conversation: Conversation
    ):
        service = ConversationService(db_session)
        with pytest.raises(ConversationStateError) as exc_info:
            await service.end_conversation(completed_conversation.id, test_user.id)
        assert exc_info.value.status_code == 409
        assert "completed" in exc_info.value.message

    @pytest.mark.unit
    async def test_end_nonexistent_conversation_raises_not_found(
        self, db_session: AsyncSession, test_user: User
    ):
        service = ConversationService(db_session)
        with pytest.raises(NotFoundError):
            await service.end_conversation(uuid.uuid4(), test_user.id)

    @pytest.mark.unit
    async def test_end_conversation_wrong_user_raises_not_found(
        self, db_session: AsyncSession, test_conversation: Conversation
    ):
        """Verify that ending another user's conversation returns NotFound."""
        service = ConversationService(db_session)
        with pytest.raises(NotFoundError):
            await service.end_conversation(test_conversation.id, uuid.uuid4())

    @pytest.mark.unit
    async def test_end_conversation_counts_corrections(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_conversation: Conversation,
        test_turn: Turn,
        test_correction,
    ):
        """Verify that total_corrections is calculated on end."""
        service = ConversationService(db_session)
        ended = await service.end_conversation(test_conversation.id, test_user.id)
        assert ended.total_corrections == 1


class TestConversationServiceResume:
    """Tests for ConversationService.resume_conversation."""

    @pytest.mark.unit
    async def test_resume_paused_conversation(
        self, db_session: AsyncSession, test_user: User, paused_conversation: Conversation
    ):
        service = ConversationService(db_session)
        resumed = await service.resume_conversation(paused_conversation.id, test_user.id)
        assert resumed.status == "active"

    @pytest.mark.unit
    async def test_resume_active_conversation_raises_state_error(
        self, db_session: AsyncSession, test_user: User, test_conversation: Conversation
    ):
        service = ConversationService(db_session)
        with pytest.raises(ConversationStateError) as exc_info:
            await service.resume_conversation(test_conversation.id, test_user.id)
        assert "active" in exc_info.value.message

    @pytest.mark.unit
    async def test_resume_completed_conversation_raises_state_error(
        self, db_session: AsyncSession, test_user: User, completed_conversation: Conversation
    ):
        service = ConversationService(db_session)
        with pytest.raises(ConversationStateError):
            await service.resume_conversation(completed_conversation.id, test_user.id)

    @pytest.mark.unit
    async def test_resume_nonexistent_conversation_raises_not_found(
        self, db_session: AsyncSession, test_user: User
    ):
        service = ConversationService(db_session)
        with pytest.raises(NotFoundError):
            await service.resume_conversation(uuid.uuid4(), test_user.id)

    @pytest.mark.unit
    async def test_resume_conversation_wrong_user_raises_not_found(
        self, db_session: AsyncSession, paused_conversation: Conversation
    ):
        """Verify that resuming another user's conversation returns NotFound."""
        service = ConversationService(db_session)
        with pytest.raises(NotFoundError):
            await service.resume_conversation(paused_conversation.id, uuid.uuid4())


class TestConversationServiceFeedback:
    """Tests for ConversationService.get_feedback and get_feedback_with_stats."""

    @pytest.mark.unit
    async def test_get_feedback_with_corrections(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_conversation: Conversation,
        test_turn: Turn,
        test_correction,
    ):
        service = ConversationService(db_session)
        corrections = await service.get_feedback(test_conversation.id, test_user.id)
        assert len(corrections) == 1
        assert corrections[0].corrected_text == "I went to the store yesterday."

    @pytest.mark.unit
    async def test_get_feedback_no_corrections(
        self, db_session: AsyncSession, test_user: User, test_conversation: Conversation
    ):
        service = ConversationService(db_session)
        corrections = await service.get_feedback(test_conversation.id, test_user.id)
        assert len(corrections) == 0

    @pytest.mark.unit
    async def test_get_feedback_nonexistent_conversation(
        self, db_session: AsyncSession, test_user: User
    ):
        service = ConversationService(db_session)
        with pytest.raises(NotFoundError):
            await service.get_feedback(uuid.uuid4(), test_user.id)

    @pytest.mark.unit
    async def test_get_feedback_wrong_user_raises_not_found(
        self,
        db_session: AsyncSession,
        test_conversation: Conversation,
    ):
        """Verify that getting feedback for another user's conversation returns NotFound."""
        service = ConversationService(db_session)
        with pytest.raises(NotFoundError):
            await service.get_feedback(test_conversation.id, uuid.uuid4())

    @pytest.mark.unit
    async def test_get_feedback_with_stats(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_conversation: Conversation,
        test_turn: Turn,
        test_correction,
    ):
        service = ConversationService(db_session)
        stats = await service.get_feedback_with_stats(test_conversation.id, test_user.id)
        assert isinstance(stats, FeedbackStats)
        assert stats.total_turns == 1  # One user turn
        assert stats.total_corrections == 1
        assert stats.total_clean == 0

    @pytest.mark.unit
    async def test_get_feedback_with_stats_no_corrections(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_conversation: Conversation,
        test_turn: Turn,
    ):
        """Verify stats when user has turns but no corrections."""
        # Update turn to 'clean' status
        test_turn.correction_status = "clean"
        await db_session.flush()

        service = ConversationService(db_session)
        stats = await service.get_feedback_with_stats(test_conversation.id, test_user.id)
        assert stats.total_turns == 1
        assert stats.total_corrections == 0
        assert stats.total_clean == 1

    @pytest.mark.unit
    async def test_get_feedback_with_stats_empty_conversation(
        self, db_session: AsyncSession, test_user: User, test_conversation: Conversation
    ):
        """Verify stats for a conversation with no turns."""
        service = ConversationService(db_session)
        stats = await service.get_feedback_with_stats(test_conversation.id, test_user.id)
        assert stats.total_turns == 0
        assert stats.total_corrections == 0
        assert stats.total_clean == 0


class TestFeedbackStats:
    """Tests for the FeedbackStats frozen dataclass."""

    @pytest.mark.unit
    def test_feedback_stats_is_frozen(self):
        stats = FeedbackStats(
            total_turns=5,
            total_corrections=2,
            total_clean=3,
            corrections=[],
        )
        with pytest.raises(AttributeError):
            stats.total_turns = 10

    @pytest.mark.unit
    def test_feedback_stats_attributes(self):
        stats = FeedbackStats(
            total_turns=10,
            total_corrections=3,
            total_clean=7,
            corrections=[],
        )
        assert stats.total_turns == 10
        assert stats.total_corrections == 3
        assert stats.total_clean == 7
        assert stats.corrections == []


class TestAllowedTopics:
    """Tests for the ALLOWED_TOPICS constant."""

    @pytest.mark.unit
    def test_allowed_topics_content(self):
        expected = {"sports", "business", "technology", "politics", "entertainment"}
        assert ALLOWED_TOPICS == expected

    @pytest.mark.unit
    def test_allowed_topics_is_frozenset(self):
        assert isinstance(ALLOWED_TOPICS, frozenset)
