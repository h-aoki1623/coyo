"""Repository for Conversation data access."""

import uuid
from datetime import datetime

import sqlalchemy as sa
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
        time_limit_seconds: int,
        topic_suggestion_id: uuid.UUID | None = None,
    ) -> Conversation:
        """Create a new conversation and flush to obtain its ID."""
        conversation = Conversation(
            user_id=user_id,
            time_limit_seconds=time_limit_seconds,
            topic_suggestion_id=topic_suggestion_id,
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

    async def set_memory_context_text(
        self,
        conversation_id: uuid.UUID,
        text: str,
    ) -> None:
        """Unconditionally write the memory context snapshot.

        Used by the greeting path, where the conversation row already
        exists and no other writer is racing. Writes BOTH columns
        atomically via SQLAlchemy Core to avoid ORM cache surprises.
        """
        stmt = (
            sa.update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(
                memory_context_text=text,
                memory_context_built_at=sa.func.now(),
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def try_set_memory_context_text_if_null(
        self,
        conversation_id: uuid.UUID,
        text: str,
    ) -> str:
        """Race-safe lazy snapshot write for the turn path.

        Atomically sets ``memory_context_text`` and
        ``memory_context_built_at`` only when the column is currently
        NULL. If another concurrent caller wins the race, this method
        re-SELECTs and returns the winner's value so the caller's prompt
        is byte-identical to the persisted snapshot.

        The caller is responsible for refreshing any ORM-cached attribute
        on the ``Conversation`` object after this returns.
        """
        stmt = (
            sa.update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.memory_context_text.is_(None),
            )
            .values(
                memory_context_text=text,
                memory_context_built_at=sa.func.now(),
            )
            .returning(Conversation.memory_context_text)
        )
        result = await self._session.execute(stmt)
        row = result.one_or_none()
        if row is not None:
            await self._session.flush()
            return str(row[0])

        # We lost the race — re-SELECT the winner's value.
        winner_stmt = sa.select(Conversation.memory_context_text).where(
            Conversation.id == conversation_id,
        )
        winner_result = await self._session.execute(winner_stmt)
        winner_row = winner_result.one_or_none()
        if winner_row is None:
            # Conversation row vanished between UPDATE and SELECT (delete
            # race). Fall back to the caller's text — the snapshot is
            # best-effort and the prompt is still valid.
            return text
        winner_value = winner_row[0]
        # ``""`` is the explicit "computed but no memory" sentinel and
        # must be returned as-is. Only true NULL means "row exists but
        # not yet computed", which can't happen on this code path.
        return "" if winner_value is None else str(winner_value)

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
