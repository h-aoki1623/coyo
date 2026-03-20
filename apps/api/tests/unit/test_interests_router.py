"""Unit tests for the interests router."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.user import User
from coyo.repositories.interest import InterestRepository


class TestGetInterests:
    """Tests for GET /api/interests."""

    @pytest.mark.unit
    async def test_get_interests_empty(self, client: AsyncClient):
        response = await client.get("/api/interests")
        assert response.status_code == 200
        data = response.json()
        assert data["interests"] == []

    @pytest.mark.unit
    async def test_get_interests_with_data(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ):
        repo = InterestRepository(db_session)
        await repo.upsert_interest(
            user_id=test_user.id,
            keyword="tennis",
            keyword_type="topic",
            is_news_relevant=True,
            current_conv_idx=1,
        )
        await repo.upsert_interest(
            user_id=test_user.id,
            keyword="kei nishikori",
            keyword_type="entity",
            is_news_relevant=True,
            current_conv_idx=1,
        )
        await db_session.commit()

        response = await client.get("/api/interests")
        assert response.status_code == 200
        data = response.json()
        assert len(data["interests"]) == 2

        # Check camelCase keys
        interest = data["interests"][0]
        assert "keywordType" in interest
        assert "isNewsRelevant" in interest
        assert "totalMentions" in interest
        assert "effectiveWeight" in interest
        assert "lastMentionedConvIdx" in interest

    @pytest.mark.unit
    async def test_get_interests_sorted_by_weight(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ):
        repo = InterestRepository(db_session)
        # tennis mentioned 3 times
        for i in range(1, 4):
            await repo.upsert_interest(
                user_id=test_user.id,
                keyword="tennis",
                keyword_type="topic",
                is_news_relevant=True,
                current_conv_idx=i,
            )
        # cooking mentioned 1 time
        await repo.upsert_interest(
            user_id=test_user.id,
            keyword="cooking",
            keyword_type="topic",
            is_news_relevant=False,
            current_conv_idx=1,
        )
        await db_session.commit()

        response = await client.get("/api/interests")
        data = response.json()
        assert data["interests"][0]["keyword"] == "tennis"
        assert (
            data["interests"][0]["effectiveWeight"]
            > data["interests"][1]["effectiveWeight"]
        )
