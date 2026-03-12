"""User and UserSettings ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from coyo.models.base import Base, BaseModel

if TYPE_CHECKING:
    from coyo.models.conversation import Conversation


class AuthProvider(StrEnum):
    """Supported authentication providers."""

    EMAIL = "email"
    GOOGLE = "google"
    APPLE = "apple"


class User(BaseModel):
    """Represents a user identified by an external authentication provider UID."""

    __tablename__ = "users"
    __table_args__ = (
        sa.CheckConstraint(
            f"auth_provider IN ({', '.join(repr(p.value) for p in AuthProvider)})",
            name="ck_users_auth_provider_valid",
        ),
    )

    auth_uid: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        comment="External authentication provider UID",
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="User email from Firebase",
    )

    display_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Display name from Firebase",
    )

    auth_provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="email",
        comment="Authentication provider: email, google, apple",
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
