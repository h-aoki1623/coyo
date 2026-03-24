"""Repository for ConversationSummary data access."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.conversation_summary import ConversationSummary


class ConversationSummaryRepository:
    """Encapsulates database operations for the ConversationSummary model."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        topic_title: str,
        source_keyword: str | None,
        summary: str,
    ) -> ConversationSummary:
        """Create a conversation summary.

        Idempotent on conversation_id (UNIQUE constraint). If a summary already
        exists for the conversation, the existing record is returned unchanged.
        """
        conv_summary = ConversationSummary(
            conversation_id=conversation_id,
            user_id=user_id,
            topic_title=topic_title,
            source_keyword=source_keyword,
            summary=summary,
        )
        self._session.add(conv_summary)
        try:
            await self._session.flush()
        except IntegrityError:
            # Summary already exists for this conversation — return existing
            await self._session.rollback()
            stmt = select(ConversationSummary).where(
                ConversationSummary.conversation_id == conversation_id,
            )
            result = await self._session.execute(stmt)
            conv_summary = result.scalar_one()

        return conv_summary

    async def get_latest_for_user(
        self,
        user_id: uuid.UUID,
        *,
        limit: int = 5,
    ) -> list[ConversationSummary]:
        """Get the most recent conversation summaries, ordered by created_at DESC."""
        stmt = (
            select(ConversationSummary)
            .where(ConversationSummary.user_id == user_id)
            .order_by(ConversationSummary.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
