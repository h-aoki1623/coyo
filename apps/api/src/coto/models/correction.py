"""Correction ORM models for turn-level grammar and expression feedback."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from coto.models.base import BaseModel

if TYPE_CHECKING:
    from coto.models.turn import Turn


class TurnCorrection(BaseModel):
    """Aggregated correction for a single user turn."""

    __tablename__ = "turn_corrections"

    turn_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("turns.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    corrected_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Relationships
    turn: Mapped[Turn] = relationship(back_populates="correction")
    items: Mapped[list[CorrectionItem]] = relationship(back_populates="turn_correction")


class CorrectionItem(BaseModel):
    """Individual correction detail within a TurnCorrection."""

    __tablename__ = "correction_items"

    turn_correction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("turn_corrections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Denormalized FK for efficient user-level correction queries",
    )
    original: Mapped[str] = mapped_column(Text, nullable=False)
    corrected: Mapped[str] = mapped_column(Text, nullable=False)
    original_sentence: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_sentence: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Correction category: grammar, expression, vocabulary",
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    turn_correction: Mapped[TurnCorrection] = relationship(back_populates="items")
