"""Repository for TopicSuggestion data access."""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.topic_suggestion import TopicSuggestion, UserTopicSuggestion


class TopicSuggestionRepository:
    """Encapsulates database operations for topic suggestions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_suggestion(
        self,
        *,
        title: str,
        summary: str,
        source_keyword: str,
        article_content: str,
        article_url: str | None,
        pool_type: str,
        generated_date: date,
    ) -> TopicSuggestion:
        """Create and flush a new topic suggestion."""
        suggestion = TopicSuggestion(
            title=title,
            summary=summary,
            source_keyword=source_keyword,
            article_content=article_content,
            article_url=article_url,
            pool_type=pool_type,
            generated_date=generated_date,
        )
        self._session.add(suggestion)
        await self._session.flush()
        return suggestion

    async def create_user_suggestion(
        self,
        *,
        user_id: uuid.UUID,
        topic_suggestion_id: uuid.UUID,
        relevance_score: float = 1.0,
    ) -> UserTopicSuggestion:
        """Create a user-to-suggestion link and flush."""
        user_suggestion = UserTopicSuggestion(
            user_id=user_id,
            topic_suggestion_id=topic_suggestion_id,
            relevance_score=relevance_score,
        )
        self._session.add(user_suggestion)
        await self._session.flush()
        return user_suggestion

    async def get_suggestions_for_user(
        self,
        user_id: uuid.UUID,
    ) -> list[tuple[TopicSuggestion, float]]:
        """Get topic suggestions from the most recent generated_date for a user.

        Uses MAX(generated_date) to find the latest batch, ordered by relevance.
        Returns an empty list if the user has no assigned suggestions (the MAX
        subquery returns NULL, causing the equality filter to match no rows).
        """
        latest_date_subq = (
            select(func.max(TopicSuggestion.generated_date))
            .join(
                UserTopicSuggestion,
                UserTopicSuggestion.topic_suggestion_id == TopicSuggestion.id,
            )
            .where(UserTopicSuggestion.user_id == user_id)
            .scalar_subquery()
        )

        stmt = (
            select(TopicSuggestion, UserTopicSuggestion.relevance_score)
            .join(
                UserTopicSuggestion,
                UserTopicSuggestion.topic_suggestion_id == TopicSuggestion.id,
            )
            .where(
                UserTopicSuggestion.user_id == user_id,
                TopicSuggestion.generated_date == latest_date_subq,
            )
            .order_by(UserTopicSuggestion.relevance_score.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.tuples().all())

    async def get_common_suggestions(self, target_date: date) -> list[TopicSuggestion]:
        """Get common pool suggestions for a date."""
        stmt = (
            select(TopicSuggestion)
            .where(
                TopicSuggestion.generated_date == target_date,
                TopicSuggestion.pool_type == "common",
            )
            .order_by(TopicSuggestion.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, suggestion_id: uuid.UUID) -> TopicSuggestion | None:
        """Retrieve a single topic suggestion by primary key."""
        return await self._session.get(TopicSuggestion, suggestion_id)

    async def user_has_suggestion(
        self,
        user_id: uuid.UUID,
        topic_suggestion_id: uuid.UUID,
    ) -> bool:
        """Check if a user has been assigned a specific suggestion."""
        stmt = select(UserTopicSuggestion.user_id).where(
            UserTopicSuggestion.user_id == user_id,
            UserTopicSuggestion.topic_suggestion_id == topic_suggestion_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_personal_suggestions(self, target_date: date) -> list[TopicSuggestion]:
        """Get personal pool suggestions for a date (idempotency check)."""
        stmt = (
            select(TopicSuggestion)
            .where(
                TopicSuggestion.generated_date == target_date,
                TopicSuggestion.pool_type == "personal",
            )
            .order_by(TopicSuggestion.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_users_with_conv_count(self) -> list[tuple[uuid.UUID, int]]:
        """Get (user_id, conversation_count) for all active users."""
        # Deferred import to avoid circular dependency: topic_suggestion -> user -> ...
        from coyo.models.user import User

        stmt = select(User.id, User.conversation_count)
        result = await self._session.execute(stmt)
        return list(result.tuples().all())

    async def get_active_user_ids(self) -> list[uuid.UUID]:
        """Get IDs of all users."""
        # Deferred import to avoid circular dependency: topic_suggestion -> user -> ...
        from coyo.models.user import User

        stmt = select(User.id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
