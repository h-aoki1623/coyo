"""Unit tests for InterestRepository.get_global_top_keywords."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.user import AuthProvider, User
from coyo.models.user_interest import UserInterest
from coyo.repositories.interest import InterestRepository


async def _create_user(db_session: AsyncSession, suffix: str) -> User:
    """Create a unique test user."""
    user = User(
        auth_uid=f"test-uid-{suffix}",
        email=f"user-{suffix}@example.com",
        auth_provider=AuthProvider.EMAIL,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _create_interest(
    db_session: AsyncSession,
    user_id: uuid.UUID,
    keyword: str,
    *,
    keyword_type: str = "category",
    is_news_relevant: bool = True,
) -> UserInterest:
    """Create a UserInterest record."""
    interest = UserInterest(
        user_id=user_id,
        keyword=keyword,
        keyword_type=keyword_type,
        is_news_relevant=is_news_relevant,
        total_mentions=1,
        short_term_stored=1.0,
        last_mentioned_conv_idx=1,
    )
    db_session.add(interest)
    await db_session.flush()
    return interest


class TestGetGlobalTopKeywords:
    """Tests for get_global_top_keywords repository method."""

    @pytest.mark.unit
    async def test_returns_keywords_ordered_by_user_count_desc(
        self, db_session: AsyncSession
    ):
        """Keywords with more distinct users rank higher."""
        user1 = await _create_user(db_session, "a")
        user2 = await _create_user(db_session, "b")
        user3 = await _create_user(db_session, "c")

        # "sports" -> 3 users, "tech" -> 1 user, "music" -> 2 users
        await _create_interest(db_session, user1.id, "sports")
        await _create_interest(db_session, user2.id, "sports")
        await _create_interest(db_session, user3.id, "sports")
        await _create_interest(db_session, user1.id, "tech")
        await _create_interest(db_session, user1.id, "music")
        await _create_interest(db_session, user2.id, "music")
        await db_session.commit()

        repo = InterestRepository(db_session)
        result = await repo.get_global_top_keywords(limit=3)

        assert result == ["sports", "music", "tech"]

    @pytest.mark.unit
    async def test_filters_by_keyword_type(self, db_session: AsyncSession):
        """Only returns keywords matching the keyword_type filter."""
        user1 = await _create_user(db_session, "d")

        await _create_interest(
            db_session, user1.id, "tennis", keyword_type="entity"
        )
        await _create_interest(
            db_session, user1.id, "sports", keyword_type="category"
        )
        await db_session.commit()

        repo = InterestRepository(db_session)
        result = await repo.get_global_top_keywords(keyword_type="category")

        assert result == ["sports"]
        assert "tennis" not in result

    @pytest.mark.unit
    async def test_filters_by_is_news_relevant(self, db_session: AsyncSession):
        """Only returns keywords with is_news_relevant=True by default."""
        user1 = await _create_user(db_session, "e")

        await _create_interest(
            db_session, user1.id, "cooking", is_news_relevant=False
        )
        await _create_interest(
            db_session, user1.id, "politics", is_news_relevant=True
        )
        await db_session.commit()

        repo = InterestRepository(db_session)
        result = await repo.get_global_top_keywords()

        assert result == ["politics"]
        assert "cooking" not in result

    @pytest.mark.unit
    async def test_respects_limit_parameter(self, db_session: AsyncSession):
        """Returns at most `limit` keywords."""
        user1 = await _create_user(db_session, "f")
        user2 = await _create_user(db_session, "g")

        for kw in ["sports", "music", "tech", "politics"]:
            await _create_interest(db_session, user1.id, kw)
            await _create_interest(db_session, user2.id, kw)
        await db_session.commit()

        repo = InterestRepository(db_session)
        result = await repo.get_global_top_keywords(limit=2)

        assert len(result) == 2

    @pytest.mark.unit
    async def test_returns_empty_list_when_no_interests(
        self, db_session: AsyncSession
    ):
        """Returns empty list when no interests exist in the database."""
        repo = InterestRepository(db_session)
        result = await repo.get_global_top_keywords()

        assert result == []
