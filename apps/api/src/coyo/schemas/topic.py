"""Schemas for topic suggestion endpoints."""

import uuid

from coyo.schemas.base import CamelModel


class TopicSuggestionResponse(CamelModel):
    """A single topic suggestion for the home screen."""

    id: uuid.UUID
    title: str
    summary: str
    source_keyword: str
    pool: str
    rank: int


class TopicSuggestionsListResponse(CamelModel):
    """Grouped topic suggestions for a user."""

    personal: list[TopicSuggestionResponse]
    trending: list[TopicSuggestionResponse]
