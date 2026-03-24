"""UserProfileSummary ORM model for free-text user profile summary."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from coyo.models.base import Base


class UserProfileSummary(Base):
    """Stores a free-text summary of a user's profile (1:1 with users).

    The summary is regenerated periodically as the user has more conversations.
    """

    __tablename__ = "user_profile_summaries"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    conversation_count_at_update: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
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
