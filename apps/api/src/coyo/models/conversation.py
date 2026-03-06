"""Conversation ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from coyo.models.base import BaseModel

if TYPE_CHECKING:
    from coyo.models.turn import Turn
    from coyo.models.user import User


class Conversation(BaseModel):
    """Represents a single conversation session between a user and the AI."""

    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Conversation topic: sports, business, technology, politics, entertainment",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        comment="Conversation state: active, paused, completed, abandoned",
    )
    duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=None,
    )
    time_limit_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1800,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    total_corrections: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        default=None,
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="conversations")
    turns: Mapped[list[Turn]] = relationship(
        back_populates="conversation",
        order_by="Turn.sequence",
    )
