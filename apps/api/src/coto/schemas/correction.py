"""Schemas for correction data in API responses."""

import uuid

from coto.schemas.base import CamelModel


class CorrectionItemResponse(CamelModel):
    """Response schema for a single correction item."""

    id: uuid.UUID
    original: str
    corrected: str
    original_sentence: str
    corrected_sentence: str
    type: str
    explanation: str


class TurnCorrectionResponse(CamelModel):
    """Response schema for a turn-level correction with all items."""

    id: uuid.UUID
    turn_id: uuid.UUID
    corrected_text: str
    explanation: str
    items: list[CorrectionItemResponse]


class FeedbackResponse(CamelModel):
    """Feedback summary with corrections for a completed conversation."""

    total_turns: int
    total_corrections: int
    total_clean: int
    corrections: list[TurnCorrectionResponse]
