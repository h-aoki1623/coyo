"""Unit tests for interest schema validation."""

import pytest

from coyo.schemas.interest import InterestResponse, InterestsListResponse


class TestInterestResponse:
    """Tests for InterestResponse schema."""

    @pytest.mark.unit
    def test_valid_construction(self):
        resp = InterestResponse(
            keyword="tennis",
            keyword_type="topic",
            is_news_relevant=True,
            total_mentions=5,
            effective_weight=2.1,
            last_mentioned_conv_idx=12,
        )
        assert resp.keyword == "tennis"
        assert resp.effective_weight == 2.1

    @pytest.mark.unit
    def test_camel_case_serialization(self):
        resp = InterestResponse(
            keyword="tennis",
            keyword_type="topic",
            is_news_relevant=True,
            total_mentions=5,
            effective_weight=2.1,
            last_mentioned_conv_idx=12,
        )
        dumped = resp.model_dump(by_alias=True)
        assert "keywordType" in dumped
        assert "isNewsRelevant" in dumped
        assert "totalMentions" in dumped
        assert "effectiveWeight" in dumped
        assert "lastMentionedConvIdx" in dumped


class TestInterestsListResponse:
    """Tests for InterestsListResponse schema."""

    @pytest.mark.unit
    def test_empty_list(self):
        resp = InterestsListResponse(interests=[])
        assert resp.interests == []

    @pytest.mark.unit
    def test_with_items(self):
        item = InterestResponse(
            keyword="tennis",
            keyword_type="topic",
            is_news_relevant=True,
            total_mentions=5,
            effective_weight=2.1,
            last_mentioned_conv_idx=12,
        )
        resp = InterestsListResponse(interests=[item])
        assert len(resp.interests) == 1
        assert resp.interests[0].keyword == "tennis"
