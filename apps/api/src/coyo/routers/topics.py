"""Topic suggestion endpoints."""

import hmac

import structlog
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.config import get_settings
from coyo.dependencies import get_current_user, get_db
from coyo.exceptions import CoyoError
from coyo.models.user import User
from coyo.rate_limit import DEFAULT_RATE_LIMIT, EXPENSIVE_RATE_LIMIT, limiter
from coyo.repositories.topic_suggestion import TopicSuggestionRepository
from coyo.schemas.topic import TopicSuggestionResponse, TopicSuggestionsListResponse
from coyo.services.topic_generation import TopicGenerationService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("/suggestions", response_model=TopicSuggestionsListResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def get_suggestions(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TopicSuggestionsListResponse:
    """Get topic suggestions for the current user."""
    repo = TopicSuggestionRepository(db)
    suggestions = await repo.get_suggestions_for_user(user.id)

    personal: list[TopicSuggestionResponse] = []
    trending: list[TopicSuggestionResponse] = []

    for rank, (suggestion, _score) in enumerate(suggestions, start=1):
        item = TopicSuggestionResponse(
            id=suggestion.id,
            title=suggestion.title,
            summary=suggestion.summary,
            source_keyword=suggestion.source_keyword,
            pool=suggestion.pool_type,
            rank=rank,
        )
        if suggestion.pool_type == "personal":
            personal.append(item)
        else:
            trending.append(item)

    return TopicSuggestionsListResponse(personal=personal, trending=trending)


@router.post("/generate", status_code=200)
@limiter.limit(EXPENSIVE_RATE_LIMIT)
async def generate_topics(
    request: Request,
    x_cron_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Generate trending topic suggestions (cron endpoint).

    Protected by X-Cron-Secret header.
    """
    settings = get_settings()
    if not settings.cron_secret:
        raise CoyoError(
            "Cron endpoint not configured (cron_secret is None)",
            "FORBIDDEN",
            403,
            client_message="Forbidden",
        )
    if not hmac.compare_digest(x_cron_secret or "", settings.cron_secret):
        raise CoyoError(
            "Invalid cron secret",
            "FORBIDDEN",
            403,
            client_message="Forbidden",
        )

    service = TopicGenerationService(db)
    topic_count = await service.generate_common_topics()
    user_count = await service.assign_to_users()

    personal_count = 0
    try:
        personal_count = await service.generate_personal_topics()
    except Exception:
        logger.exception("personal_topic_generation_failed")

    return {
        "topics_generated": topic_count,
        "users_assigned": user_count,
        "personal_topics_generated": personal_count,
    }
