"""Turn ORM model representing a single message in a conversation."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from coto.models.base import BaseModel

if TYPE_CHECKING:
    from coto.models.conversation import Conversation
    from coto.models.correction import TurnCorrection


class Turn(BaseModel):
    """A single message (user or AI) within a conversation."""

    __tablename__ = "turns"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Message author: user or ai",
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    audio_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        default=None,
    )
    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    correction_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="none",
        comment="Correction state: none, pending, clean, has_corrections",
    )

    # Relationships
    conversation: Mapped[Conversation] = relationship(back_populates="turns")
    correction: Mapped[TurnCorrection | None] = relationship(
        back_populates="turn",
        uselist=False,
    )
