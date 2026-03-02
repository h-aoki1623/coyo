"""User and UserSettings ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from coto.models.base import Base, BaseModel

if TYPE_CHECKING:
    from coto.models.conversation import Conversation


class User(BaseModel):
    """Represents a user identified by device ID."""

    __tablename__ = "users"

    device_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        comment="Client-generated UUID from X-Device-Id header",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    settings: Mapped[UserSettings | None] = relationship(
        back_populates="user",
        uselist=False,
    )
    conversations: Mapped[list[Conversation]] = relationship(back_populates="user")


class UserSettings(Base):
    """Per-user preferences for UI language, correction language, TTS, etc."""

    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ui_language: Mapped[str] = mapped_column(String(5), default="ja")
    correction_language: Mapped[str] = mapped_column(String(5), default="ja")
    time_limit_seconds: Mapped[int] = mapped_column(Integer, default=1800)
    tts_voice: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tts_speed: Mapped[float] = mapped_column(Float, default=1.0)

    # Relationship
    user: Mapped[User] = relationship(back_populates="settings")
