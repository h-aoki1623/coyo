"""Topic suggestion ORM models."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from coyo.models.base import Base, BaseModel


class TopicSuggestion(BaseModel):
    """A generated topic suggestion for English conversation."""

    __tablename__ = "topic_suggestions"

    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_keyword: Mapped[str] = mapped_column(Text, nullable=False)
    article_content: Mapped[str] = mapped_column(Text, nullable=False)
    article_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    pool_type: Mapped[str] = mapped_column(String(20), nullable=False, default="common")
    generated_date: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        Index("ix_topic_suggestions_date_pool", "generated_date", "pool_type"),
        CheckConstraint("pool_type IN ('common', 'personal')", name="ck_topic_pool_type"),
    )


class UserTopicSuggestion(Base):
    """Links a user to their assigned topic suggestions."""

    __tablename__ = "user_topic_suggestions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    topic_suggestion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topic_suggestions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_user_topic_suggestions_user_created",
            "user_id",
            created_at.desc(),
        ),
    )
