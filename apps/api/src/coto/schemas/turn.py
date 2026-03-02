"""Schemas for turn data in API responses."""

import uuid
from datetime import datetime

from coto.schemas.base import CamelModel


class TurnResponse(CamelModel):
    """Response schema for a single conversation turn."""

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    text: str
    audio_url: str | None
    sequence: int
    correction_status: str
    created_at: datetime
