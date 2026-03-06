"""Unit tests for repository classes."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.conversation import Conversation
from coyo.models.turn import Turn
from coyo.models.user import User
from coyo.repositories.conversation import ConversationRepository
from coyo.repositories.history import HistoryRepository
from coyo.repositories.turn import TurnRepository
from coyo.repositories.user import UserRepository


# ---------------------------------------------------------------------------
# ConversationRepository
# ---------------------------------------------------------------------------


class TestConversationRepository:
    """Tests for the ConversationRepository."""

    @pytest.mark.unit
    async def test_create_conversation(
        self, db_session: AsyncSession, test_user: User
    ):
        repo = ConversationRepository(db_session)
        conversation = await repo.create(
            user_id=test_user.id,
            topic="technology",
            time_limit_seconds=1800,
        )
        assert conversation.id is not None
        assert conversation.topic == "technology"
        assert conversation.user_id == test_user.id

    @pytest.mark.unit
    async def test_get_by_id_existing(
        self, db_session: AsyncSession, test_conversation: Conversation
    ):
        repo = ConversationRepository(db_session)
        result = await repo.get_by_id(test_conversation.id)
        assert result is not None
        assert result.id == test_conversation.id

    @pytest.mark.unit
    async def test_get_by_id_nonexistent(self, db_session: AsyncSession):
        repo = ConversationRepository(db_session)
        result = await repo.get_by_id(uuid.uuid4())
        assert result is None

    @pytest.mark.unit
    async def test_update_status(
        self, db_session: AsyncSession, test_conversation: Conversation
    ):
        repo = ConversationRepository(db_session)
        result = await repo.update_status(test_conversation.id, "paused")
        assert result is not None
        assert result.status == "paused"

    @pytest.mark.unit
    async def test_update_status_nonexistent(self, db_session: AsyncSession):
        repo = ConversationRepository(db_session)
        result = await repo.update_status(uuid.uuid4(), "active")
        assert result is None

    @pytest.mark.unit
    async def test_update_on_end(
        self, db_session: AsyncSession, test_conversation: Conversation
    ):
        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)
        result = await repo.update_on_end(
            test_conversation.id,
            status="completed",
            ended_at=now,
            duration_seconds=600,
            total_corrections=3,
            score=85.5,
        )
        assert result is not None
        assert result.status == "completed"
        assert result.ended_at == now
        assert result.duration_seconds == 600
        assert result.total_corrections == 3
        assert result.score == 85.5

    @pytest.mark.unit
    async def test_update_on_end_nonexistent(self, db_session: AsyncSession):
        repo = ConversationRepository(db_session)
        result = await repo.update_on_end(
            uuid.uuid4(),
            status="completed",
            ended_at=datetime.now(UTC),
            duration_seconds=600,
            total_corrections=0,
            score=None,
        )
        assert result is None


# ---------------------------------------------------------------------------
# TurnRepository
# ---------------------------------------------------------------------------


class TestTurnRepository:
    """Tests for the TurnRepository."""

    @pytest.mark.unit
    async def test_create_turn(
        self, db_session: AsyncSession, test_conversation: Conversation
    ):
        repo = TurnRepository(db_session)
        turn = await repo.create(
            conversation_id=test_conversation.id,
            role="user",
            text="Hello!",
            sequence=1,
        )
        assert turn.id is not None
        assert turn.role == "user"
        assert turn.text == "Hello!"
        assert turn.sequence == 1
        assert turn.correction_status == "none"

    @pytest.mark.unit
    async def test_create_turn_with_correction_status(
        self, db_session: AsyncSession, test_conversation: Conversation
    ):
        repo = TurnRepository(db_session)
        turn = await repo.create(
            conversation_id=test_conversation.id,
            role="user",
            text="Test",
            sequence=1,
            correction_status="pending",
        )
        assert turn.correction_status == "pending"

    @pytest.mark.unit
    async def test_create_turn_with_audio_url(
        self, db_session: AsyncSession, test_conversation: Conversation
    ):
        repo = TurnRepository(db_session)
        turn = await repo.create(
            conversation_id=test_conversation.id,
            role="ai",
            text="Hi there!",
            sequence=1,
            audio_url="data:audio/mpeg;base64,abc",
        )
        assert turn.audio_url == "data:audio/mpeg;base64,abc"

    @pytest.mark.unit
    async def test_get_by_conversation_id_ordered_by_sequence(
        self, db_session: AsyncSession, test_conversation: Conversation
    ):
        repo = TurnRepository(db_session)
        await repo.create(
            conversation_id=test_conversation.id,
            role="user",
            text="First",
            sequence=1,
        )
        await repo.create(
            conversation_id=test_conversation.id,
            role="ai",
            text="Second",
            sequence=2,
        )
        await repo.create(
            conversation_id=test_conversation.id,
            role="user",
            text="Third",
            sequence=3,
        )

        turns = await repo.get_by_conversation_id(test_conversation.id)
        assert len(turns) == 3
        assert turns[0].sequence == 1
        assert turns[1].sequence == 2
        assert turns[2].sequence == 3

    @pytest.mark.unit
    async def test_get_by_conversation_id_empty(
        self, db_session: AsyncSession, test_conversation: Conversation
    ):
        repo = TurnRepository(db_session)
        turns = await repo.get_by_conversation_id(test_conversation.id)
        assert turns == []

    @pytest.mark.unit
    async def test_get_by_conversation_id_nonexistent(
        self, db_session: AsyncSession
    ):
        repo = TurnRepository(db_session)
        turns = await repo.get_by_conversation_id(uuid.uuid4())
        assert turns == []


# ---------------------------------------------------------------------------
# UserRepository
# ---------------------------------------------------------------------------


class TestUserRepository:
    """Tests for the UserRepository."""

    @pytest.mark.unit
    async def test_find_or_create_creates_new_user(
        self, db_session: AsyncSession
    ):
        repo = UserRepository(db_session)
        user = await repo.find_or_create_by_device_id("new-device-id")
        assert user.id is not None
        assert user.device_id == "new-device-id"

    @pytest.mark.unit
    async def test_find_or_create_returns_existing_user(
        self, db_session: AsyncSession, test_user: User
    ):
        repo = UserRepository(db_session)
        user = await repo.find_or_create_by_device_id(test_user.device_id)
        assert user.id == test_user.id

    @pytest.mark.unit
    async def test_find_or_create_idempotent(
        self, db_session: AsyncSession
    ):
        """Verify that calling find_or_create twice returns the same user."""
        repo = UserRepository(db_session)
        user1 = await repo.find_or_create_by_device_id("idempotent-device")
        user2 = await repo.find_or_create_by_device_id("idempotent-device")
        assert user1.id == user2.id


# ---------------------------------------------------------------------------
# HistoryRepository
# ---------------------------------------------------------------------------


class TestHistoryRepository:
    """Tests for the HistoryRepository."""

    @pytest.mark.unit
    async def test_get_list_empty(
        self, db_session: AsyncSession, test_user: User
    ):
        repo = HistoryRepository(db_session)
        items, total = await repo.get_list_by_device_id(test_user.id)
        assert items == []
        assert total == 0

    @pytest.mark.unit
    async def test_get_list_with_conversations(
        self, db_session: AsyncSession, test_user: User
    ):
        # Create 3 conversations
        for _ in range(3):
            conv = Conversation(
                user_id=test_user.id,
                topic="sports",
                status="active",
                time_limit_seconds=1800,
                started_at=datetime.now(UTC),
            )
            db_session.add(conv)
        await db_session.commit()

        repo = HistoryRepository(db_session)
        items, total = await repo.get_list_by_device_id(test_user.id)
        assert total == 3
        assert len(items) == 3

    @pytest.mark.unit
    async def test_get_list_pagination(
        self, db_session: AsyncSession, test_user: User
    ):
        for _ in range(5):
            conv = Conversation(
                user_id=test_user.id,
                topic="technology",
                status="active",
                time_limit_seconds=1800,
                started_at=datetime.now(UTC),
            )
            db_session.add(conv)
        await db_session.commit()

        repo = HistoryRepository(db_session)
        items, total = await repo.get_list_by_device_id(
            test_user.id, offset=0, limit=2
        )
        assert total == 5
        assert len(items) == 2

    @pytest.mark.unit
    async def test_get_detail_existing(
        self, db_session: AsyncSession, test_user: User, test_conversation: Conversation
    ):
        repo = HistoryRepository(db_session)
        detail = await repo.get_detail(test_conversation.id, test_user.id)
        assert detail is not None
        assert detail.id == test_conversation.id

    @pytest.mark.unit
    async def test_get_detail_nonexistent(
        self, db_session: AsyncSession, test_user: User
    ):
        repo = HistoryRepository(db_session)
        detail = await repo.get_detail(uuid.uuid4(), test_user.id)
        assert detail is None

    @pytest.mark.unit
    async def test_get_detail_wrong_user(
        self, db_session: AsyncSession, test_conversation: Conversation
    ):
        """Verify that a different user cannot access the conversation."""
        # Create a different user
        other_user = User(device_id="other-device")
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        repo = HistoryRepository(db_session)
        detail = await repo.get_detail(test_conversation.id, other_user.id)
        assert detail is None

    @pytest.mark.unit
    async def test_delete_existing(
        self, db_session: AsyncSession, test_user: User, test_conversation: Conversation
    ):
        repo = HistoryRepository(db_session)
        deleted = await repo.delete(test_conversation.id, test_user.id)
        assert deleted is True

    @pytest.mark.unit
    async def test_delete_nonexistent(
        self, db_session: AsyncSession, test_user: User
    ):
        repo = HistoryRepository(db_session)
        deleted = await repo.delete(uuid.uuid4(), test_user.id)
        assert deleted is False

    @pytest.mark.unit
    async def test_delete_wrong_user(
        self, db_session: AsyncSession, test_conversation: Conversation
    ):
        """Verify that a different user cannot delete the conversation."""
        other_user = User(device_id="other-device-2")
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        repo = HistoryRepository(db_session)
        deleted = await repo.delete(test_conversation.id, other_user.id)
        assert deleted is False

    @pytest.mark.unit
    async def test_batch_delete(
        self, db_session: AsyncSession, test_user: User
    ):
        convs = []
        for _ in range(3):
            conv = Conversation(
                user_id=test_user.id,
                topic="sports",
                status="active",
                time_limit_seconds=1800,
                started_at=datetime.now(UTC),
            )
            db_session.add(conv)
            convs.append(conv)
        await db_session.commit()
        for conv in convs:
            await db_session.refresh(conv)

        repo = HistoryRepository(db_session)
        ids = [c.id for c in convs[:2]]
        count = await repo.batch_delete(ids, test_user.id)
        assert count == 2

    @pytest.mark.unit
    async def test_batch_delete_nonexistent_ids(
        self, db_session: AsyncSession, test_user: User
    ):
        repo = HistoryRepository(db_session)
        count = await repo.batch_delete([uuid.uuid4(), uuid.uuid4()], test_user.id)
        assert count == 0

    @pytest.mark.unit
    async def test_batch_delete_empty_list(
        self, db_session: AsyncSession, test_user: User
    ):
        repo = HistoryRepository(db_session)
        count = await repo.batch_delete([], test_user.id)
        assert count == 0
