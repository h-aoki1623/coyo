"""Unit tests for topic suggestion schema validation."""

import uuid

import pytest

from coyo.schemas.conversation import CreateConversationRequest
from coyo.schemas.topic import TopicSuggestionResponse, TopicSuggestionsListResponse


# ---------------------------------------------------------------------------
# CreateConversationRequest — topic/topic_suggestion_id validator
# ---------------------------------------------------------------------------


class TestCreateConversationRequestValidator:
    """Tests for the exactly-one-topic-source validator on CreateConversationRequest."""

    @pytest.mark.unit
    def test_valid_with_topic_only(self):
        req = CreateConversationRequest(topic="technology")
        assert req.topic == "technology"
        assert req.topic_suggestion_id is None

    @pytest.mark.unit
    def test_valid_with_topic_suggestion_id_only(self):
        sid = uuid.uuid4()
        req = CreateConversationRequest(topic_suggestion_id=sid)
        assert req.topic is None
        assert req.topic_suggestion_id == sid

    @pytest.mark.unit
    def test_invalid_neither_provided(self):
        with pytest.raises(Exception) as exc_info:
            CreateConversationRequest()
        assert "Either" in str(exc_info.value)

    @pytest.mark.unit
    def test_invalid_both_provided(self):
        with pytest.raises(Exception) as exc_info:
            CreateConversationRequest(topic="sports", topic_suggestion_id=uuid.uuid4())
        assert "not both" in str(exc_info.value)

    @pytest.mark.unit
    def test_camel_case_serialization_with_topic(self):
        req = CreateConversationRequest(topic="sports")
        dumped = req.model_dump(by_alias=True)
        assert dumped["topic"] == "sports"
        assert "topicSuggestionId" in dumped

    @pytest.mark.unit
    def test_camel_case_deserialization_with_suggestion_id(self):
        sid = uuid.uuid4()
        req = CreateConversationRequest.model_validate(
            {"topicSuggestionId": str(sid)}
        )
        assert req.topic_suggestion_id == sid
        assert req.topic is None

    @pytest.mark.unit
    def test_valid_all_topic_literals(self):
        for topic in ("sports", "business", "technology", "politics", "entertainment"):
            req = CreateConversationRequest(topic=topic)
            assert req.topic == topic

    @pytest.mark.unit
    def test_invalid_topic_value_rejected(self):
        with pytest.raises(Exception):
            CreateConversationRequest(topic="cooking")


# ---------------------------------------------------------------------------
# TopicSuggestionResponse
# ---------------------------------------------------------------------------


class TestTopicSuggestionResponse:
    """Tests for the TopicSuggestionResponse schema."""

    @pytest.mark.unit
    def test_valid_construction(self):
        resp = TopicSuggestionResponse(
            id=uuid.uuid4(),
            title="AI Revolution",
            summary="Artificial intelligence is changing the world.",
            source_keyword="AI",
            pool="common",
            rank=1,
        )
        assert resp.title == "AI Revolution"
        assert resp.pool == "common"
        assert resp.rank == 1

    @pytest.mark.unit
    def test_camel_case_serialization(self):
        resp = TopicSuggestionResponse(
            id=uuid.uuid4(),
            title="Test",
            summary="Summary",
            source_keyword="keyword",
            pool="personal",
            rank=2,
        )
        dumped = resp.model_dump(by_alias=True)
        assert "sourceKeyword" in dumped
        assert dumped["sourceKeyword"] == "keyword"

    @pytest.mark.unit
    def test_from_attributes(self):
        class FakeSuggestion:
            id = uuid.uuid4()
            title = "Test"
            summary = "Sum"
            source_keyword = "kw"
            pool = "common"
            rank = 1

        resp = TopicSuggestionResponse.model_validate(FakeSuggestion())
        assert resp.title == "Test"


# ---------------------------------------------------------------------------
# TopicSuggestionsListResponse
# ---------------------------------------------------------------------------


class TestTopicSuggestionsListResponse:
    """Tests for the TopicSuggestionsListResponse schema."""

    @pytest.mark.unit
    def test_valid_construction_empty_lists(self):
        resp = TopicSuggestionsListResponse(personal=[], trending=[])
        assert resp.personal == []
        assert resp.trending == []

    @pytest.mark.unit
    def test_valid_construction_with_items(self):
        item = TopicSuggestionResponse(
            id=uuid.uuid4(),
            title="Test",
            summary="Sum",
            source_keyword="kw",
            pool="common",
            rank=1,
        )
        resp = TopicSuggestionsListResponse(personal=[], trending=[item])
        assert len(resp.trending) == 1
        assert resp.trending[0].title == "Test"

    @pytest.mark.unit
    def test_camel_case_serialization(self):
        resp = TopicSuggestionsListResponse(personal=[], trending=[])
        dumped = resp.model_dump(by_alias=True)
        assert "personal" in dumped
        assert "trending" in dumped
