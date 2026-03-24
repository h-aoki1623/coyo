"""Repository for UserInterest data access with 2-layer weight model."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from coyo.models.user_interest import UserInterest

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

# 2-layer weight model parameters
SHORT_DECAY: float = 0.85
SHORT_BOOST: float = 1.0
SHORT_CAP: float = 3.0
LONG_SCALE: float = 0.5


@dataclass(frozen=True)
class InterestWithWeight:
    """An interest keyword with its computed effective weight."""

    keyword: str
    keyword_type: str
    is_news_relevant: bool
    total_mentions: int
    effective_weight: float
    last_mentioned_conv_idx: int
    summary: str | None


def compute_effective_weight(
    total_mentions: int,
    short_term_stored: float,
    last_mentioned_conv_idx: int,
    current_conv_idx: int,
) -> float:
    """Compute the effective weight for an interest keyword.

    effective_weight = long_term + short_term
    long_term  = LONG_SCALE * log(1 + total_mentions)
    short_term = short_term_stored * SHORT_DECAY ^ gap
    """
    gap = max(0, current_conv_idx - last_mentioned_conv_idx)
    long_term = LONG_SCALE * math.log(1 + total_mentions)
    short_term = short_term_stored * (SHORT_DECAY**gap)
    return long_term + short_term


class InterestRepository:
    """Encapsulates database operations for the UserInterest model."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_interest(
        self,
        *,
        user_id: uuid.UUID,
        keyword: str,
        keyword_type: str,
        is_news_relevant: bool,
        current_conv_idx: int,
        summary: str | None = None,
    ) -> UserInterest:
        """Insert or update an interest keyword with 2-layer model logic.

        On insert: sets initial values and summary if provided,
            sets needs_summary_update = False.
        On update: applies decay to short_term, then boosts.
            Does NOT update summary; sets needs_summary_update = True instead.
        """
        keyword = keyword.lower().strip()
        stmt = select(UserInterest).where(
            UserInterest.user_id == user_id,
            UserInterest.keyword == keyword,
        )
        result = await self._session.execute(stmt)
        interest = result.scalar_one_or_none()

        if interest is None:
            interest = UserInterest(
                user_id=user_id,
                keyword=keyword,
                keyword_type=keyword_type,
                is_news_relevant=is_news_relevant,
                total_mentions=1,
                short_term_stored=min(SHORT_BOOST, SHORT_CAP),
                last_mentioned_conv_idx=current_conv_idx,
                summary=summary,
                needs_summary_update=False,
            )
            self._session.add(interest)
            try:
                await self._session.flush()
            except IntegrityError:
                # Concurrent insert race — rollback and fall through to update
                await self._session.rollback()
                result = await self._session.execute(
                    select(UserInterest).where(
                        UserInterest.user_id == user_id,
                        UserInterest.keyword == keyword,
                    )
                )
                interest = result.scalar_one()
                self._apply_mention(interest, is_news_relevant, current_conv_idx)
                await self._session.flush()
        else:
            self._apply_mention(interest, is_news_relevant, current_conv_idx)
            await self._session.flush()

        return interest

    @staticmethod
    def _apply_mention(
        interest: UserInterest,
        is_news_relevant: bool,
        current_conv_idx: int,
    ) -> None:
        """Apply a mention: decay short_term, boost, and update metadata."""
        gap = max(0, current_conv_idx - interest.last_mentioned_conv_idx)
        cur_short = interest.short_term_stored * (SHORT_DECAY**gap)

        interest.total_mentions = interest.total_mentions + 1
        interest.short_term_stored = min(cur_short + SHORT_BOOST, SHORT_CAP)
        interest.last_mentioned_conv_idx = current_conv_idx
        interest.is_news_relevant = is_news_relevant
        interest.needs_summary_update = True

    @staticmethod
    def _to_weighted(
        interest: UserInterest,
        current_conv_idx: int,
    ) -> InterestWithWeight:
        """Convert an ORM interest to a weighted dataclass."""
        return InterestWithWeight(
            keyword=interest.keyword,
            keyword_type=interest.keyword_type,
            is_news_relevant=interest.is_news_relevant,
            total_mentions=interest.total_mentions,
            effective_weight=compute_effective_weight(
                interest.total_mentions,
                interest.short_term_stored,
                interest.last_mentioned_conv_idx,
                current_conv_idx,
            ),
            last_mentioned_conv_idx=interest.last_mentioned_conv_idx,
            summary=interest.summary,
        )

    async def get_interests_for_user(
        self,
        user_id: uuid.UUID,
        current_conv_idx: int,
    ) -> list[InterestWithWeight]:
        """Get all interests for a user with computed effective weights."""
        stmt = select(UserInterest).where(UserInterest.user_id == user_id)
        result = await self._session.execute(stmt)
        interests = result.scalars().all()

        weighted = [self._to_weighted(i, current_conv_idx) for i in interests]
        return sorted(weighted, key=lambda x: x.effective_weight, reverse=True)

    async def get_top_interests(
        self,
        user_id: uuid.UUID,
        current_conv_idx: int,
        *,
        keyword_type: str | None = None,
        is_news_relevant: bool | None = None,
        limit: int = 10,
    ) -> list[InterestWithWeight]:
        """Get top interests filtered by type and/or news relevance.

        Used by Pipeline B to select keywords for personal topic generation.
        """
        conditions = [UserInterest.user_id == user_id]
        if keyword_type is not None:
            conditions.append(UserInterest.keyword_type == keyword_type)
        if is_news_relevant is not None:
            conditions.append(UserInterest.is_news_relevant == is_news_relevant)

        stmt = select(UserInterest).where(*conditions)
        result = await self._session.execute(stmt)
        interests = result.scalars().all()

        weighted = [self._to_weighted(i, current_conv_idx) for i in interests]
        weighted.sort(key=lambda x: x.effective_weight, reverse=True)
        return weighted[:limit]

    async def get_interests_needing_summary_update(
        self,
        user_id: uuid.UUID,
    ) -> list[UserInterest]:
        """Get interests where needs_summary_update=True."""
        stmt = select(UserInterest).where(
            UserInterest.user_id == user_id,
            UserInterest.needs_summary_update.is_(True),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_summary(
        self,
        user_id: uuid.UUID,
        keyword: str,
        summary: str,
    ) -> None:
        """Update interest summary, set summary_updated_at=now(), needs_summary_update=False."""
        keyword = keyword.lower().strip()
        stmt = select(UserInterest).where(
            UserInterest.user_id == user_id,
            UserInterest.keyword == keyword,
        )
        result = await self._session.execute(stmt)
        interest = result.scalar_one_or_none()

        if interest is not None:
            interest.summary = summary
            interest.summary_updated_at = datetime.now(UTC)
            interest.needs_summary_update = False
            await self._session.flush()
