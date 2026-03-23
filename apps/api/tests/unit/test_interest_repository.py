"""Unit tests for the InterestRepository with 2-layer weight model."""

import math
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.user import User
from coyo.models.user_interest import UserInterest
from coyo.repositories.interest import (
    LONG_SCALE,
    SHORT_BOOST,
    SHORT_CAP,
    SHORT_DECAY,
    InterestRepository,
    InterestWithWeight,
    compute_effective_weight,
)


class TestComputeEffectiveWeight:
    """Tests for the compute_effective_weight function."""

    @pytest.mark.unit
    def test_zero_mentions_zero_short_term(self):
        weight = compute_effective_weight(
            total_mentions=0,
            short_term_stored=0.0,
            last_mentioned_conv_idx=0,
            current_conv_idx=0,
        )
        assert weight == 0.0

    @pytest.mark.unit
    def test_single_mention_no_gap(self):
        weight = compute_effective_weight(
            total_mentions=1,
            short_term_stored=1.0,
            last_mentioned_conv_idx=1,
            current_conv_idx=1,
        )
        expected_long = LONG_SCALE * math.log(2)
        expected_short = 1.0  # decay^0 = 1
        assert weight == pytest.approx(expected_long + expected_short)

    @pytest.mark.unit
    def test_short_term_decays_with_gap(self):
        weight = compute_effective_weight(
            total_mentions=1,
            short_term_stored=1.0,
            last_mentioned_conv_idx=1,
            current_conv_idx=4,
        )
        gap = 3
        expected_long = LONG_SCALE * math.log(2)
        expected_short = 1.0 * (SHORT_DECAY**gap)
        assert weight == pytest.approx(expected_long + expected_short)

    @pytest.mark.unit
    def test_long_term_grows_logarithmically(self):
        w1 = compute_effective_weight(1, 0.0, 0, 0)
        w5 = compute_effective_weight(5, 0.0, 0, 0)
        w10 = compute_effective_weight(10, 0.0, 0, 0)
        # Logarithmic: growth rate decreases
        assert w5 > w1
        assert w10 > w5
        assert (w10 - w5) < (w5 - w1)

    @pytest.mark.unit
    def test_negative_gap_treated_as_zero(self):
        """If current_conv_idx < last_mentioned somehow, gap = 0."""
        weight = compute_effective_weight(
            total_mentions=1,
            short_term_stored=1.0,
            last_mentioned_conv_idx=5,
            current_conv_idx=3,
        )
        expected_long = LONG_SCALE * math.log(2)
        expected_short = 1.0  # gap clamped to 0
        assert weight == pytest.approx(expected_long + expected_short)


class TestInterestRepositoryUpsert:
    """Tests for InterestRepository.upsert_interest."""

    @pytest.mark.unit
    async def test_insert_new_interest(self, db_session: AsyncSession, test_user: User):
        repo = InterestRepository(db_session)
        interest = await repo.upsert_interest(
            user_id=test_user.id,
            keyword="tennis",
            keyword_type="topic",
            is_news_relevant=True,
            current_conv_idx=1,
        )
        assert interest.keyword == "tennis"
        assert interest.keyword_type == "topic"
        assert interest.is_news_relevant is True
        assert interest.total_mentions == 1
        assert interest.short_term_stored == pytest.approx(SHORT_BOOST)
        assert interest.last_mentioned_conv_idx == 1

    @pytest.mark.unit
    async def test_upsert_existing_interest_increments_mentions(
        self, db_session: AsyncSession, test_user: User
    ):
        repo = InterestRepository(db_session)
        await repo.upsert_interest(
            user_id=test_user.id,
            keyword="tennis",
            keyword_type="topic",
            is_news_relevant=True,
            current_conv_idx=1,
        )
        interest = await repo.upsert_interest(
            user_id=test_user.id,
            keyword="tennis",
            keyword_type="topic",
            is_news_relevant=True,
            current_conv_idx=2,
        )
        assert interest.total_mentions == 2

    @pytest.mark.unit
    async def test_upsert_applies_decay_and_boost(
        self, db_session: AsyncSession, test_user: User
    ):
        repo = InterestRepository(db_session)
        await repo.upsert_interest(
            user_id=test_user.id,
            keyword="tennis",
            keyword_type="topic",
            is_news_relevant=True,
            current_conv_idx=1,
        )
        # Gap of 3 conversations
        interest = await repo.upsert_interest(
            user_id=test_user.id,
            keyword="tennis",
            keyword_type="topic",
            is_news_relevant=True,
            current_conv_idx=4,
        )
        expected_short = min(SHORT_BOOST * (SHORT_DECAY**3) + SHORT_BOOST, SHORT_CAP)
        assert interest.short_term_stored == pytest.approx(expected_short)
        assert interest.last_mentioned_conv_idx == 4

    @pytest.mark.unit
    async def test_upsert_respects_short_cap(
        self, db_session: AsyncSession, test_user: User
    ):
        repo = InterestRepository(db_session)
        # Rapidly mention the same keyword many times
        for i in range(1, 10):
            interest = await repo.upsert_interest(
                user_id=test_user.id,
                keyword="tennis",
                keyword_type="topic",
                is_news_relevant=True,
                current_conv_idx=i,
            )
        assert interest.short_term_stored <= SHORT_CAP

    @pytest.mark.unit
    async def test_upsert_updates_news_relevance(
        self, db_session: AsyncSession, test_user: User
    ):
        repo = InterestRepository(db_session)
        await repo.upsert_interest(
            user_id=test_user.id,
            keyword="tennis",
            keyword_type="topic",
            is_news_relevant=False,
            current_conv_idx=1,
        )
        interest = await repo.upsert_interest(
            user_id=test_user.id,
            keyword="tennis",
            keyword_type="topic",
            is_news_relevant=True,
            current_conv_idx=2,
        )
        assert interest.is_news_relevant is True


class TestInterestRepositoryQuery:
    """Tests for InterestRepository query methods."""

    @pytest.mark.unit
    async def test_get_interests_for_user_empty(
        self, db_session: AsyncSession, test_user: User
    ):
        repo = InterestRepository(db_session)
        result = await repo.get_interests_for_user(test_user.id, 0)
        assert result == []

    @pytest.mark.unit
    async def test_get_interests_sorted_by_weight(
        self, db_session: AsyncSession, test_user: User
    ):
        repo = InterestRepository(db_session)
        # tennis mentioned 5 times, cooking mentioned 1 time
        for i in range(1, 6):
            await repo.upsert_interest(
                user_id=test_user.id,
                keyword="tennis",
                keyword_type="topic",
                is_news_relevant=True,
                current_conv_idx=i,
            )
        await repo.upsert_interest(
            user_id=test_user.id,
            keyword="cooking",
            keyword_type="topic",
            is_news_relevant=False,
            current_conv_idx=1,
        )

        result = await repo.get_interests_for_user(test_user.id, 5)
        assert len(result) == 2
        assert result[0].keyword == "tennis"
        assert result[0].effective_weight > result[1].effective_weight

    @pytest.mark.unit
    async def test_get_top_interests_with_limit(
        self, db_session: AsyncSession, test_user: User
    ):
        repo = InterestRepository(db_session)
        for keyword in ["a", "b", "c", "d", "e"]:
            await repo.upsert_interest(
                user_id=test_user.id,
                keyword=keyword,
                keyword_type="topic",
                is_news_relevant=True,
                current_conv_idx=1,
            )

        result = await repo.get_top_interests(
            test_user.id, 1, limit=3
        )
        assert len(result) == 3

    @pytest.mark.unit
    async def test_get_top_interests_filtered_by_type(
        self, db_session: AsyncSession, test_user: User
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

        topics = await repo.get_top_interests(
            test_user.id, 1, keyword_type="topic"
        )
        entities = await repo.get_top_interests(
            test_user.id, 1, keyword_type="entity"
        )
        assert len(topics) == 1
        assert topics[0].keyword == "tennis"
        assert len(entities) == 1
        assert entities[0].keyword == "kei nishikori"

    @pytest.mark.unit
    async def test_get_top_interests_filtered_by_news_relevance(
        self, db_session: AsyncSession, test_user: User
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
            keyword="cooking",
            keyword_type="topic",
            is_news_relevant=False,
            current_conv_idx=1,
        )

        news_relevant = await repo.get_top_interests(
            test_user.id, 1, is_news_relevant=True
        )
        assert len(news_relevant) == 1
        assert news_relevant[0].keyword == "tennis"

    @pytest.mark.unit
    async def test_different_users_have_separate_interests(
        self, db_session: AsyncSession, test_user: User
    ):
        other_user = User(
            auth_uid="other-uid",
            email="other@example.com",
            auth_provider="email",
        )
        db_session.add(other_user)
        await db_session.flush()

        repo = InterestRepository(db_session)
        await repo.upsert_interest(
            user_id=test_user.id,
            keyword="tennis",
            keyword_type="topic",
            is_news_relevant=True,
            current_conv_idx=1,
        )
        await repo.upsert_interest(
            user_id=other_user.id,
            keyword="chess",
            keyword_type="topic",
            is_news_relevant=True,
            current_conv_idx=1,
        )

        user_interests = await repo.get_interests_for_user(test_user.id, 1)
        other_interests = await repo.get_interests_for_user(other_user.id, 1)
        assert len(user_interests) == 1
        assert user_interests[0].keyword == "tennis"
        assert len(other_interests) == 1
        assert other_interests[0].keyword == "chess"
