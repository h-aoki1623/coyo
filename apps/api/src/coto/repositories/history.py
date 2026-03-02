"""Repository for conversation history queries."""

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from coto.models.conversation import Conversation
from coto.models.correction import TurnCorrection
from coto.models.turn import Turn


class HistoryRepository:
    """Encapsulates read-heavy queries for conversation history."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_list_by_device_id(
        self,
        user_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Conversation], int]:
        """Return a paginated list of conversations for a user.

        Returns:
            A tuple of (conversations, total_count).
        """
        # Count total matching rows
        count_stmt = (
            select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)
        )
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        # Fetch paginated results ordered by most recent first
        list_stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.started_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(list_stmt)
        conversations = list(result.scalars().all())

        return conversations, total

    async def get_detail(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Conversation | None:
        """Fetch a conversation with eagerly loaded turns and corrections.

        Uses selectinload to prevent N+1 queries on turns and corrections.
        """
        stmt = (
            select(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
            .options(
                selectinload(Conversation.turns)
                .selectinload(Turn.correction)
                .selectinload(TurnCorrection.items)
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Delete a single conversation. Returns True if a row was deleted."""
        stmt = delete(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def batch_delete(
        self,
        conversation_ids: list[uuid.UUID],
        user_id: uuid.UUID,
    ) -> int:
        """Delete multiple conversations. Returns the count of deleted rows."""
        stmt = delete(Conversation).where(
            Conversation.id.in_(conversation_ids),
            Conversation.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.rowcount
