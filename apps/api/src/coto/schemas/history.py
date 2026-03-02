"""Schemas for conversation history endpoints."""

import uuid
from datetime import datetime

from pydantic import Field

from coto.schemas.base import CamelModel
from coto.schemas.conversation import ConversationResponse
from coto.schemas.correction import TurnCorrectionResponse
from coto.schemas.turn import TurnResponse


class HistoryListItem(CamelModel):
    """Summary item for the conversation history list."""

    id: uuid.UUID
    topic: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    total_corrections: int


class HistoryListResponse(CamelModel):
    """Paginated list of conversation history items."""

    items: list[HistoryListItem]
    total: int
    page: int
    per_page: int


class HistoryDetailResponse(ConversationResponse):
    """Detailed conversation history with turns and corrections."""

    turns: list[TurnResponse] = Field(default_factory=list)
    corrections: list[TurnCorrectionResponse] = Field(default_factory=list)


class BatchDeleteRequest(CamelModel):
    """Request body for batch-deleting conversations."""

    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100)
