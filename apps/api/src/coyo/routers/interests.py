"""User interest endpoints."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.dependencies import get_current_user, get_db
from coyo.models.user import User
from coyo.rate_limit import DEFAULT_RATE_LIMIT, limiter
from coyo.repositories.interest import InterestRepository
from coyo.schemas.interest import InterestResponse, InterestsListResponse

router = APIRouter(prefix="/api/interests", tags=["interests"])


@router.get("", response_model=InterestsListResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def get_interests(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterestsListResponse:
    """Get top interests for the current user, ordered by effective weight."""
    repo = InterestRepository(db)
    weighted = await repo.get_top_interests(
        user.id, user.conversation_count, limit=limit
    )

    return InterestsListResponse(
        interests=[
            InterestResponse(
                keyword=w.keyword,
                keyword_type=w.keyword_type,
                is_news_relevant=w.is_news_relevant,
                total_mentions=w.total_mentions,
                effective_weight=round(w.effective_weight, 4),
                last_mentioned_conv_idx=w.last_mentioned_conv_idx,
            )
            for w in weighted
        ]
    )
