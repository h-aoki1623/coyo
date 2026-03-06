"""Repository for Conversation data access."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.conversation import Conversation


class ConversationRepository:
    """Encapsulates database operations for the Conversation model."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        topic: str,
        time_limit_seconds: int,
    ) -> Conversation:
        """Create a new conversation and flush to obtain its ID."""
        conversation = Conversation(
            user_id=user_id,
            topic=topic,
            time_limit_seconds=time_limit_seconds,
        )
        self._session.add(conversation)
        await self._session.flush()
        return conversation

    async def get_by_id(self, conversation_id: uuid.UUID) -> Conversation | None:
        """Fetch a conversation by its primary key."""
        return await self._session.get(Conversation, conversation_id)

    async def get_by_id_for_user(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Conversation | None:
        """Fetch a conversation by ID, scoped to a specific user.

        Returns None if the conversation does not exist or belongs to
        a different user. This prevents IDOR attacks by not revealing
        whether a conversation ID exists for another user.
        """
        from sqlalchemy import select

        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        conversation_id: uuid.UUID,
        status: str,
    ) -> Conversation | None:
        """Transition a conversation to a new status."""
        conversation = await self._session.get(Conversation, conversation_id)
        if conversation is None:
            return None
        conversation.status = status
        await self._session.flush()
        return conversation

    async def update_on_end(
        self,
        conversation_id: uuid.UUID,
        *,
        status: str,
        ended_at: datetime,
        duration_seconds: int,
        total_corrections: int,
        score: float | None,
    ) -> Conversation | None:
        """Finalize a conversation with end-of-session metrics."""
        conversation = await self._session.get(Conversation, conversation_id)
        if conversation is None:
            return None
        conversation.status = status
        conversation.ended_at = ended_at
        conversation.duration_seconds = duration_seconds
        conversation.total_corrections = total_corrections
        conversation.score = score
        await self._session.flush()
        return conversation
