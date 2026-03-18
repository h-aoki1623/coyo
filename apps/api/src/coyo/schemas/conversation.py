"""Schemas for conversation endpoints."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from coyo.schemas.base import CamelModel


class CreateConversationRequest(CamelModel):
    """Request body for starting a new conversation."""

    topic: Literal["sports", "business", "technology", "politics", "entertainment"] = Field(
        ...,
        description="Conversation topic",
    )


class GreetingRequest(CamelModel):
    """Request body for triggering an AI greeting."""

    topic: Literal["sports", "business", "technology", "politics", "entertainment"] = Field(
        ...,
        description="Conversation topic for the greeting",
    )


class ConversationResponse(CamelModel):
    """Standard response for a single conversation."""

    id: uuid.UUID
    status: str
    duration_seconds: int | None
    time_limit_seconds: int
    started_at: datetime
    ended_at: datetime | None
    total_corrections: int
