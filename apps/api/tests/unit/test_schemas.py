"""Unit tests for schema validation and camelCase serialization."""

import uuid
from datetime import UTC, datetime

import pytest

from coto.schemas.base import CamelModel
from coto.schemas.conversation import ConversationResponse, CreateConversationRequest
from coto.schemas.correction import (
    CorrectionItemResponse,
    FeedbackResponse,
    TurnCorrectionResponse,
)
from coto.schemas.history import (
    BatchDeleteRequest,
    HistoryDetailResponse,
    HistoryListItem,
    HistoryListResponse,
)
from coto.schemas.turn import TurnResponse


# ---------------------------------------------------------------------------
# CamelModel base
# ---------------------------------------------------------------------------


class TestCamelModel:
    """Tests for the CamelModel camelCase alias generation."""

    @pytest.mark.unit
    def test_snake_case_to_camel_case_alias_generation(self):
        """Verify that snake_case fields get camelCase aliases in JSON output."""

        class SampleModel(CamelModel):
            first_name: str
            last_name: str

        instance = SampleModel(first_name="Alice", last_name="Smith")
        dumped = instance.model_dump(by_alias=True)

        assert "firstName" in dumped
        assert "lastName" in dumped
        assert dumped["firstName"] == "Alice"
        assert dumped["lastName"] == "Smith"

    @pytest.mark.unit
    def test_camel_model_populates_by_python_name(self):
        """Verify that fields can be set via snake_case Python names."""

        class SampleModel(CamelModel):
            user_name: str

        instance = SampleModel(user_name="Bob")
        assert instance.user_name == "Bob"

    @pytest.mark.unit
    def test_camel_model_populates_by_alias(self):
        """Verify that fields can be set via camelCase aliases."""

        class SampleModel(CamelModel):
            user_name: str

        instance = SampleModel.model_validate({"userName": "Charlie"})
        assert instance.user_name == "Charlie"

    @pytest.mark.unit
    def test_from_attributes_enabled(self):
        """Verify that CamelModel can validate from ORM-like objects."""

        class FakeORM:
            user_name = "Diana"

        class SampleModel(CamelModel):
            user_name: str

        instance = SampleModel.model_validate(FakeORM())
        assert instance.user_name == "Diana"

    @pytest.mark.unit
    def test_model_dump_without_alias_uses_snake_case(self):
        """Verify that model_dump without by_alias uses snake_case keys."""

        class SampleModel(CamelModel):
            first_name: str

        instance = SampleModel(first_name="Eve")
        dumped = instance.model_dump()

        assert "first_name" in dumped
        assert "firstName" not in dumped


# ---------------------------------------------------------------------------
# CreateConversationRequest
# ---------------------------------------------------------------------------


class TestCreateConversationRequest:
    """Tests for the CreateConversationRequest schema."""

    @pytest.mark.unit
    def test_valid_topic_technology(self):
        req = CreateConversationRequest(topic="technology")
        assert req.topic == "technology"

    @pytest.mark.unit
    def test_valid_topic_sports(self):
        req = CreateConversationRequest(topic="sports")
        assert req.topic == "sports"

    @pytest.mark.unit
    def test_valid_topic_business(self):
        req = CreateConversationRequest(topic="business")
        assert req.topic == "business"

    @pytest.mark.unit
    def test_valid_topic_politics(self):
        req = CreateConversationRequest(topic="politics")
        assert req.topic == "politics"

    @pytest.mark.unit
    def test_valid_topic_entertainment(self):
        req = CreateConversationRequest(topic="entertainment")
        assert req.topic == "entertainment"

    @pytest.mark.unit
    def test_invalid_topic_rejected(self):
        with pytest.raises(Exception):
            CreateConversationRequest(topic="cooking")

    @pytest.mark.unit
    def test_empty_topic_rejected(self):
        with pytest.raises(Exception):
            CreateConversationRequest(topic="")

    @pytest.mark.unit
    def test_camel_case_serialization(self):
        """Verify camelCase output for CreateConversationRequest."""
        req = CreateConversationRequest(topic="technology")
        dumped = req.model_dump(by_alias=True)
        assert dumped["topic"] == "technology"


# ---------------------------------------------------------------------------
# ConversationResponse
# ---------------------------------------------------------------------------


class TestConversationResponse:
    """Tests for the ConversationResponse schema."""

    @pytest.mark.unit
    def test_valid_conversation_response(self):
        now = datetime.now(UTC)
        resp = ConversationResponse(
            id=uuid.uuid4(),
            topic="technology",
            status="active",
            duration_seconds=None,
            time_limit_seconds=1800,
            started_at=now,
            ended_at=None,
            total_corrections=0,
        )
        assert resp.status == "active"
        assert resp.duration_seconds is None
        assert resp.ended_at is None

    @pytest.mark.unit
    def test_completed_conversation_response(self):
        now = datetime.now(UTC)
        resp = ConversationResponse(
            id=uuid.uuid4(),
            topic="sports",
            status="completed",
            duration_seconds=900,
            time_limit_seconds=1800,
            started_at=now,
            ended_at=now,
            total_corrections=3,
        )
        assert resp.status == "completed"
        assert resp.duration_seconds == 900
        assert resp.total_corrections == 3

    @pytest.mark.unit
    def test_camel_case_serialization(self):
        now = datetime.now(UTC)
        resp = ConversationResponse(
            id=uuid.uuid4(),
            topic="technology",
            status="active",
            duration_seconds=None,
            time_limit_seconds=1800,
            started_at=now,
            ended_at=None,
            total_corrections=0,
        )
        dumped = resp.model_dump(by_alias=True)
        assert "durationSeconds" in dumped
        assert "timeLimitSeconds" in dumped
        assert "startedAt" in dumped
        assert "endedAt" in dumped
        assert "totalCorrections" in dumped

    @pytest.mark.unit
    def test_from_attributes(self):
        """Verify that ConversationResponse can be created from an ORM-like object."""

        class FakeConversation:
            id = uuid.uuid4()
            topic = "business"
            status = "active"
            duration_seconds = None
            time_limit_seconds = 1800
            started_at = datetime.now(UTC)
            ended_at = None
            total_corrections = 0

        resp = ConversationResponse.model_validate(FakeConversation())
        assert resp.topic == "business"
        assert resp.status == "active"


# ---------------------------------------------------------------------------
# TurnResponse
# ---------------------------------------------------------------------------


class TestTurnResponse:
    """Tests for the TurnResponse schema."""

    @pytest.mark.unit
    def test_valid_turn_response(self):
        now = datetime.now(UTC)
        resp = TurnResponse(
            id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            role="user",
            text="Hello there!",
            audio_url=None,
            sequence=1,
            correction_status="none",
            created_at=now,
        )
        assert resp.role == "user"
        assert resp.audio_url is None
        assert resp.sequence == 1

    @pytest.mark.unit
    def test_turn_response_with_audio_url(self):
        now = datetime.now(UTC)
        resp = TurnResponse(
            id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            role="ai",
            text="Hi!",
            audio_url="data:audio/mpeg;base64,abc123",
            sequence=2,
            correction_status="none",
            created_at=now,
        )
        assert resp.audio_url == "data:audio/mpeg;base64,abc123"

    @pytest.mark.unit
    def test_camel_case_serialization(self):
        now = datetime.now(UTC)
        resp = TurnResponse(
            id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            role="user",
            text="test",
            audio_url=None,
            sequence=1,
            correction_status="pending",
            created_at=now,
        )
        dumped = resp.model_dump(by_alias=True)
        assert "conversationId" in dumped
        assert "audioUrl" in dumped
        assert "correctionStatus" in dumped
        assert "createdAt" in dumped


# ---------------------------------------------------------------------------
# CorrectionItemResponse
# ---------------------------------------------------------------------------


class TestCorrectionItemResponse:
    """Tests for the CorrectionItemResponse schema."""

    @pytest.mark.unit
    def test_valid_correction_item(self):
        resp = CorrectionItemResponse(
            id=uuid.uuid4(),
            original="goed",
            corrected="went",
            original_sentence="I goed to the store.",
            corrected_sentence="I went to the store.",
            type="grammar",
            explanation="'go' is irregular; past tense is 'went'.",
        )
        assert resp.original == "goed"
        assert resp.corrected == "went"
        assert resp.type == "grammar"

    @pytest.mark.unit
    def test_camel_case_serialization(self):
        resp = CorrectionItemResponse(
            id=uuid.uuid4(),
            original="goed",
            corrected="went",
            original_sentence="I goed.",
            corrected_sentence="I went.",
            type="grammar",
            explanation="test",
        )
        dumped = resp.model_dump(by_alias=True)
        assert "originalSentence" in dumped
        assert "correctedSentence" in dumped


# ---------------------------------------------------------------------------
# TurnCorrectionResponse
# ---------------------------------------------------------------------------


class TestTurnCorrectionResponse:
    """Tests for the TurnCorrectionResponse schema."""

    @pytest.mark.unit
    def test_valid_turn_correction(self):
        item_id = uuid.uuid4()
        resp = TurnCorrectionResponse(
            id=uuid.uuid4(),
            turn_id=uuid.uuid4(),
            corrected_text="I went to the store.",
            explanation="Fixed irregular verb.",
            items=[
                CorrectionItemResponse(
                    id=item_id,
                    original="goed",
                    corrected="went",
                    original_sentence="I goed.",
                    corrected_sentence="I went.",
                    type="grammar",
                    explanation="Irregular verb.",
                ),
            ],
        )
        assert len(resp.items) == 1
        assert resp.items[0].id == item_id

    @pytest.mark.unit
    def test_empty_items_list(self):
        resp = TurnCorrectionResponse(
            id=uuid.uuid4(),
            turn_id=uuid.uuid4(),
            corrected_text="All good.",
            explanation="No corrections needed.",
            items=[],
        )
        assert len(resp.items) == 0

    @pytest.mark.unit
    def test_camel_case_serialization(self):
        resp = TurnCorrectionResponse(
            id=uuid.uuid4(),
            turn_id=uuid.uuid4(),
            corrected_text="test",
            explanation="test",
            items=[],
        )
        dumped = resp.model_dump(by_alias=True)
        assert "turnId" in dumped
        assert "correctedText" in dumped


# ---------------------------------------------------------------------------
# FeedbackResponse
# ---------------------------------------------------------------------------


class TestFeedbackResponse:
    """Tests for the FeedbackResponse schema."""

    @pytest.mark.unit
    def test_valid_feedback_response(self):
        resp = FeedbackResponse(
            total_turns=10,
            total_corrections=3,
            total_clean=7,
            corrections=[],
        )
        assert resp.total_turns == 10
        assert resp.total_corrections == 3
        assert resp.total_clean == 7

    @pytest.mark.unit
    def test_all_clean_feedback(self):
        resp = FeedbackResponse(
            total_turns=5,
            total_corrections=0,
            total_clean=5,
            corrections=[],
        )
        assert resp.total_corrections == 0
        assert len(resp.corrections) == 0

    @pytest.mark.unit
    def test_camel_case_serialization(self):
        resp = FeedbackResponse(
            total_turns=5,
            total_corrections=2,
            total_clean=3,
            corrections=[],
        )
        dumped = resp.model_dump(by_alias=True)
        assert "totalTurns" in dumped
        assert "totalCorrections" in dumped
        assert "totalClean" in dumped


# ---------------------------------------------------------------------------
# HistoryListItem and HistoryListResponse
# ---------------------------------------------------------------------------


class TestHistorySchemas:
    """Tests for the history-related schemas."""

    @pytest.mark.unit
    def test_valid_history_list_item(self):
        now = datetime.now(UTC)
        item = HistoryListItem(
            id=uuid.uuid4(),
            topic="technology",
            status="completed",
            started_at=now,
            ended_at=now,
            duration_seconds=600,
            total_corrections=1,
        )
        assert item.status == "completed"
        assert item.duration_seconds == 600

    @pytest.mark.unit
    def test_history_list_item_no_end(self):
        now = datetime.now(UTC)
        item = HistoryListItem(
            id=uuid.uuid4(),
            topic="sports",
            status="active",
            started_at=now,
            ended_at=None,
            duration_seconds=None,
            total_corrections=0,
        )
        assert item.ended_at is None
        assert item.duration_seconds is None

    @pytest.mark.unit
    def test_valid_history_list_response(self):
        resp = HistoryListResponse(
            items=[],
            total=0,
            page=1,
            per_page=20,
        )
        assert resp.total == 0
        assert resp.page == 1
        assert resp.per_page == 20

    @pytest.mark.unit
    def test_history_list_response_camel_case(self):
        resp = HistoryListResponse(
            items=[],
            total=0,
            page=1,
            per_page=20,
        )
        dumped = resp.model_dump(by_alias=True)
        assert "perPage" in dumped

    @pytest.mark.unit
    def test_history_detail_response_extends_conversation(self):
        now = datetime.now(UTC)
        resp = HistoryDetailResponse(
            id=uuid.uuid4(),
            topic="technology",
            status="completed",
            duration_seconds=600,
            time_limit_seconds=1800,
            started_at=now,
            ended_at=now,
            total_corrections=1,
            turns=[],
            corrections=[],
        )
        assert resp.turns == []
        assert resp.corrections == []

    @pytest.mark.unit
    def test_history_detail_response_default_empty_lists(self):
        now = datetime.now(UTC)
        resp = HistoryDetailResponse(
            id=uuid.uuid4(),
            topic="technology",
            status="completed",
            duration_seconds=600,
            time_limit_seconds=1800,
            started_at=now,
            ended_at=now,
            total_corrections=0,
        )
        assert resp.turns == []
        assert resp.corrections == []


# ---------------------------------------------------------------------------
# BatchDeleteRequest
# ---------------------------------------------------------------------------


class TestBatchDeleteRequest:
    """Tests for the BatchDeleteRequest schema."""

    @pytest.mark.unit
    def test_valid_batch_delete_single_id(self):
        req = BatchDeleteRequest(ids=[uuid.uuid4()])
        assert len(req.ids) == 1

    @pytest.mark.unit
    def test_valid_batch_delete_multiple_ids(self):
        ids = [uuid.uuid4() for _ in range(5)]
        req = BatchDeleteRequest(ids=ids)
        assert len(req.ids) == 5

    @pytest.mark.unit
    def test_empty_ids_rejected(self):
        with pytest.raises(Exception):
            BatchDeleteRequest(ids=[])

    @pytest.mark.unit
    def test_max_ids_100(self):
        ids = [uuid.uuid4() for _ in range(100)]
        req = BatchDeleteRequest(ids=ids)
        assert len(req.ids) == 100

    @pytest.mark.unit
    def test_over_100_ids_rejected(self):
        ids = [uuid.uuid4() for _ in range(101)]
        with pytest.raises(Exception):
            BatchDeleteRequest(ids=ids)

    @pytest.mark.unit
    def test_camel_case_serialization(self):
        req = BatchDeleteRequest(ids=[uuid.uuid4()])
        dumped = req.model_dump(by_alias=True)
        assert "ids" in dumped
