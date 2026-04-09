"""ConversationSummary ORM model for per-conversation summaries."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from coyo.models.base import BaseModel


class ConversationSummary(BaseModel):
    """Stores a summary of a single conversation with its topic.

    Each conversation has at most one summary (enforced by UNIQUE on conversation_id).
    """

    __tablename__ = "conversation_summaries"
    __table_args__ = (
        sa.Index(
            "ix_conversation_summaries_user_id_created_at",
            "user_id",
            sa.text("created_at DESC"),
        ),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    topic_title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    source_keyword: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536),
        nullable=True,
    )
