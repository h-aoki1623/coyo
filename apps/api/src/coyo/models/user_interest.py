"""UserInterest ORM model for tracking user interest keywords."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from coyo.models.base import Base


class UserInterest(Base):
    """Tracks an interest keyword extracted from a user's conversations.

    Uses a 2-layer weight model:
    - long_term: LONG_SCALE * log(1 + total_mentions)
    - short_term: short_term_stored * SHORT_DECAY ^ gap
    - effective_weight = long_term + short_term
    """

    __tablename__ = "user_interests"
    __table_args__ = (
        sa.CheckConstraint(
            "keyword_type IN ('category', 'entity')",
            name="ck_user_interests_keyword_type",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    keyword: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )
    keyword_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="'category' or 'entity'",
    )
    is_news_relevant: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    total_mentions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    short_term_stored: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default="0.0",
    )
    last_mentioned_conv_idx: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    iab_category_id: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    summary: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    summary_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    needs_summary_update: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
