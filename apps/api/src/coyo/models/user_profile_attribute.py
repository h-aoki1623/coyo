"""UserProfileAttribute ORM model for structured user profile facts."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from coyo.models.base import Base


class UserProfileAttribute(Base):
    """Stores a structured profile fact about a user.

    Each attribute is a key-value pair with a confidence score.
    Allowed keys: english_goal, job_industry, hometown_or_location, family_status.
    """

    __tablename__ = "user_profile_attributes"
    __table_args__ = (
        sa.CheckConstraint(
            "key IN ('english_goal', 'job_industry', 'hometown_or_location', 'family_status')",
            name="ck_user_profile_attributes_key",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    key: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )
    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default="0.8",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
