"""Repository for ConversationSummary data access."""

from __future__ import annotations

import uuid  # noqa: TC003 — dataclass field annotation needs runtime symbol
from dataclasses import dataclass
from datetime import datetime  # noqa: TC003 — dataclass field annotation
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from coyo.models.conversation_summary import ConversationSummary

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class ConversationSummaryEmbeddingRow:
    """Lean projection of a conversation summary used for theme retrieval."""

    id: uuid.UUID
    user_id: uuid.UUID
    source_keyword: str | None
    topic_title: str
    summary: str
    embedding: list[float]
    created_at: datetime


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
        embedding: list[float] | None = None,
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
            embedding=embedding,
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

    async def get_all_with_embeddings(
        self,
        user_id: uuid.UUID,
        *,
        limit: int = 2000,
    ) -> list[ConversationSummaryEmbeddingRow]:
        """Fetch lean summary rows with embeddings for theme-relevant retrieval.

        Excludes rows where ``embedding IS NULL`` (e.g. legacy rows from
        before this feature shipped, or rows whose embedding write failed).
        Callers fall back to ``get_latest_for_user`` to top up the result.

        ``limit`` caps the per-user candidate fetch as a DoS guard. Rows
        are ordered by ``created_at DESC`` (uses the existing
        ``ix_conversation_summaries_user_id_created_at`` index) so the
        most recent summaries are kept when the cap is reached. ``id``
        is added as a tiebreaker for byte-stable snapshots.
        """
        stmt = (
            select(
                ConversationSummary.id,
                ConversationSummary.user_id,
                ConversationSummary.source_keyword,
                ConversationSummary.topic_title,
                ConversationSummary.summary,
                ConversationSummary.embedding,
                ConversationSummary.created_at,
            )
            .where(
                ConversationSummary.user_id == user_id,
                ConversationSummary.embedding.is_not(None),
            )
            .order_by(
                ConversationSummary.created_at.desc(),
                ConversationSummary.id.desc(),
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows: list[ConversationSummaryEmbeddingRow] = []
        for row in result.all():
            embedding = row.embedding
            if embedding is None:
                continue
            if not isinstance(embedding, list):
                embedding = list(embedding)
            rows.append(
                ConversationSummaryEmbeddingRow(
                    id=row.id,
                    user_id=row.user_id,
                    source_keyword=row.source_keyword,
                    topic_title=row.topic_title,
                    summary=row.summary,
                    embedding=embedding,
                    created_at=row.created_at,
                )
            )
        return rows
