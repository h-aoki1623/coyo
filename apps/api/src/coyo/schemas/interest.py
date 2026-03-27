"""Schemas for interest extraction endpoints."""

from typing import Literal

from coyo.schemas.base import CamelModel


class InterestResponse(CamelModel):
    """A single user interest with its computed weight."""

    keyword: str
    keyword_type: Literal["category", "entity"]
    is_news_relevant: bool
    total_mentions: int
    effective_weight: float
    last_mentioned_conv_idx: int


class InterestsListResponse(CamelModel):
    """List of user interests ordered by effective weight."""

    interests: list[InterestResponse]
