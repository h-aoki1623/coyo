"""Schemas for conversation endpoints."""

import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from coyo.schemas.base import CamelModel

TopicLiteral = Literal[
    "sports", "business", "technology", "politics", "entertainment"
]


class CreateConversationRequest(CamelModel):
    """Request body for starting a new conversation."""

    topic: TopicLiteral | None = Field(
        default=None,
        description="Conversation topic",
    )
    topic_suggestion_id: uuid.UUID | None = Field(
        default=None,
        description="ID of a topic suggestion to start from",
    )

    @model_validator(mode="after")
    def exactly_one_topic_source(self) -> Self:
        """Ensure exactly one of topic or topic_suggestion_id is provided."""
        if self.topic is None and self.topic_suggestion_id is None:
            raise ValueError("Either 'topic' or 'topicSuggestionId' must be provided")
        if self.topic is not None and self.topic_suggestion_id is not None:
            raise ValueError("Provide either 'topic' or 'topicSuggestionId', not both")
        return self


class GreetingRequest(CamelModel):
    """Request body for triggering an AI greeting."""

    topic: Literal[
        "sports", "business", "technology", "politics", "entertainment", "suggested"
    ] = Field(
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
