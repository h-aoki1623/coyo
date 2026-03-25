"""Unit tests for the AI greeting feature.

Covers the GreetingRequest schema, TurnOrchestrator.process_greeting pipeline,
and the POST /{conversation_id}/greeting endpoint guards.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.conversation import Conversation
from coyo.models.turn import Turn
from coyo.schemas.conversation import GreetingRequest
from coyo.services.turn_orchestrator import TurnOrchestrator, _GREETING_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# GreetingRequest schema validation
# ---------------------------------------------------------------------------


class TestGreetingRequestSchema:
    """Tests for the GreetingRequest Pydantic model."""

    @pytest.mark.unit
    def test_valid_topic_sports(self):
        req = GreetingRequest(topic="sports")
        assert req.topic == "sports"

    @pytest.mark.unit
    def test_valid_topic_business(self):
        req = GreetingRequest(topic="business")
        assert req.topic == "business"

    @pytest.mark.unit
    def test_valid_topic_technology(self):
        req = GreetingRequest(topic="technology")
        assert req.topic == "technology"

    @pytest.mark.unit
    def test_valid_topic_politics(self):
        req = GreetingRequest(topic="politics")
        assert req.topic == "politics"

    @pytest.mark.unit
    def test_valid_topic_entertainment(self):
        req = GreetingRequest(topic="entertainment")
        assert req.topic == "entertainment"

    @pytest.mark.unit
    def test_invalid_topic_rejected(self):
        with pytest.raises(Exception):
            GreetingRequest(topic="cooking")

    @pytest.mark.unit
    def test_empty_topic_rejected(self):
        with pytest.raises(Exception):
            GreetingRequest(topic="")

    @pytest.mark.unit
    def test_none_topic_rejected(self):
        with pytest.raises(Exception):
            GreetingRequest(topic=None)

    @pytest.mark.unit
    def test_camel_case_serialization(self):
        req = GreetingRequest(topic="technology")
        dumped = req.model_dump(by_alias=True)
        assert dumped["topic"] == "technology"

    @pytest.mark.unit
    def test_camel_case_deserialization(self):
        req = GreetingRequest.model_validate({"topic": "sports"})
        assert req.topic == "sports"


# ---------------------------------------------------------------------------
# TurnOrchestrator.process_greeting
# ---------------------------------------------------------------------------


class TestProcessGreeting:
    """Tests for the TurnOrchestrator.process_greeting method."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM client that yields tokens."""

        async def mock_chat(messages, options=None):
            for token in ["Hello", "! ", "How are you?"]:
                yield token

        mock = MagicMock()
        mock.chat = mock_chat
        return mock

    @pytest.fixture
    def mock_tts(self):
        """Create a mock TTS service."""
        mock = AsyncMock()
        mock.synthesize = AsyncMock(return_value="data:audio/mpeg;base64,fakeaudio")
        return mock

    @pytest.fixture
    def mock_turn_repo(self):
        """Create a mock TurnRepository."""
        mock = AsyncMock()
        mock_turn = MagicMock()
        mock_turn.id = uuid.uuid4()
        mock.create = AsyncMock(return_value=mock_turn)
        return mock

    @pytest.fixture
    def orchestrator(
        self, db_session: AsyncSession, mock_llm, mock_tts, mock_turn_repo
    ):
        """Create a TurnOrchestrator with mocked dependencies."""
        orch = TurnOrchestrator(db_session)
        orch._llm = mock_llm
        orch._tts = mock_tts
        orch._turn_repo = mock_turn_repo
        return orch

    @pytest.mark.unit
    async def test_process_greeting_yields_expected_event_sequence(
        self, orchestrator
    ):
        """Verify the event sequence: ai_response_chunk(s) -> ai_response_done -> tts_audio_url -> turn_complete."""
        conversation_id = uuid.uuid4()

        events = []
        async for event in orchestrator.process_greeting(
            conversation_id=conversation_id, user_id=uuid.uuid4(), topic="sports"
        ):
            events.append(event)

        event_types = [e["event"] for e in events]
        assert "ai_response_chunk" in event_types
        assert "ai_response_done" in event_types
        assert "tts_audio_url" in event_types
        assert "turn_complete" in event_types

        # Verify ordering: chunks come before done, done before tts, tts before complete
        done_idx = event_types.index("ai_response_done")
        tts_idx = event_types.index("tts_audio_url")
        complete_idx = event_types.index("turn_complete")
        assert done_idx < tts_idx < complete_idx

    @pytest.mark.unit
    async def test_process_greeting_yields_correct_chunk_data(self, orchestrator):
        """Verify that ai_response_chunk events contain the streamed tokens."""
        conversation_id = uuid.uuid4()

        chunk_texts = []
        async for event in orchestrator.process_greeting(
            conversation_id=conversation_id, user_id=uuid.uuid4(), topic="sports"
        ):
            if event["event"] == "ai_response_chunk":
                chunk_texts.append(event["data"]["text"])

        assert chunk_texts == ["Hello", "! ", "How are you?"]

    @pytest.mark.unit
    async def test_process_greeting_ai_response_done_contains_full_text(
        self, orchestrator
    ):
        """Verify that ai_response_done contains the concatenated full text."""
        conversation_id = uuid.uuid4()

        done_event = None
        async for event in orchestrator.process_greeting(
            conversation_id=conversation_id, user_id=uuid.uuid4(), topic="sports"
        ):
            if event["event"] == "ai_response_done":
                done_event = event

        assert done_event is not None
        assert done_event["data"]["text"] == "Hello! How are you?"

    @pytest.mark.unit
    async def test_process_greeting_saves_ai_turn_with_sequence_1(
        self, orchestrator, mock_turn_repo
    ):
        """Verify that the AI turn is saved with role='ai' and sequence=1."""
        conversation_id = uuid.uuid4()

        async for _ in orchestrator.process_greeting(
            conversation_id=conversation_id, user_id=uuid.uuid4(), topic="sports"
        ):
            pass

        mock_turn_repo.create.assert_called_once_with(
            conversation_id=conversation_id,
            role="ai",
            text="Hello! How are you?",
            sequence=1,
        )

    @pytest.mark.unit
    async def test_process_greeting_tts_audio_url_event(
        self, orchestrator, mock_tts
    ):
        """Verify that the tts_audio_url event contains the TTS URL."""
        conversation_id = uuid.uuid4()

        tts_event = None
        async for event in orchestrator.process_greeting(
            conversation_id=conversation_id, user_id=uuid.uuid4(), topic="sports"
        ):
            if event["event"] == "tts_audio_url":
                tts_event = event

        assert tts_event is not None
        assert tts_event["data"]["url"] == "data:audio/mpeg;base64,fakeaudio"
        mock_tts.synthesize.assert_called_once_with("Hello! How are you?")

    @pytest.mark.unit
    async def test_process_greeting_commits_session(
        self, orchestrator, db_session
    ):
        """Verify that the session is committed after all steps."""
        conversation_id = uuid.uuid4()

        # Replace commit with a mock to track calls
        db_session.commit = AsyncMock()

        async for _ in orchestrator.process_greeting(
            conversation_id=conversation_id, user_id=uuid.uuid4(), topic="sports"
        ):
            pass

        db_session.commit.assert_called_once()

    @pytest.mark.unit
    async def test_process_greeting_uses_greeting_system_prompt(
        self, orchestrator
    ):
        """Verify that the greeting system prompt is used, not the conversation prompt."""
        conversation_id = uuid.uuid4()
        topic = "technology"

        captured_messages = []

        async def capture_chat(messages, options=None):
            captured_messages.extend(messages)
            yield "Hi!"

        orchestrator._llm.chat = capture_chat

        async for _ in orchestrator.process_greeting(
            conversation_id=conversation_id, user_id=uuid.uuid4(), topic=topic
        ):
            pass

        assert len(captured_messages) == 1
        assert captured_messages[0].role == "system"
        expected_prompt = _GREETING_SYSTEM_PROMPT.format(topic=topic)
        assert captured_messages[0].content == expected_prompt

    @pytest.mark.unit
    async def test_process_greeting_with_empty_llm_response(self, orchestrator):
        """Verify that greeting handles empty LLM response gracefully."""

        async def empty_chat(messages, options=None):
            return
            yield  # noqa: RET503 - make it an async generator

        orchestrator._llm.chat = empty_chat

        events = []
        async for event in orchestrator.process_greeting(
            conversation_id=uuid.uuid4(), user_id=uuid.uuid4(), topic="sports"
        ):
            events.append(event)

        event_types = [e["event"] for e in events]
        assert "ai_response_done" in event_types
        # ai_response_done should contain empty text
        done = next(e for e in events if e["event"] == "ai_response_done")
        assert done["data"]["text"] == ""


# ---------------------------------------------------------------------------
# Greeting endpoint guards (integration-style with TestClient)
# ---------------------------------------------------------------------------


class TestGreetingEndpoint:
    """Tests for POST /api/conversations/{conversation_id}/greeting endpoint guards."""

    @pytest.mark.integration
    async def test_greeting_rejects_non_active_conversation(
        self, client, completed_conversation: Conversation
    ):
        """Greeting should return 409 for non-active conversations."""
        response = await client.post(
            f"/api/conversations/{completed_conversation.id}/greeting",
            json={"topic": "sports"},
        )
        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "INVALID_STATE"

    @pytest.mark.integration
    async def test_greeting_rejects_paused_conversation(
        self, client, paused_conversation: Conversation
    ):
        """Greeting should return 409 for paused conversations."""
        response = await client.post(
            f"/api/conversations/{paused_conversation.id}/greeting",
            json={"topic": "sports"},
        )
        assert response.status_code == 409

    @pytest.mark.integration
    async def test_greeting_rejects_duplicate_when_turns_exist(
        self,
        client,
        test_conversation: Conversation,
        test_turn: Turn,
    ):
        """Greeting should return 409 when turns already exist."""
        response = await client.post(
            f"/api/conversations/{test_conversation.id}/greeting",
            json={"topic": "sports"},
        )
        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "INVALID_STATE"

    @pytest.mark.integration
    async def test_greeting_rejects_invalid_topic(
        self, client, test_conversation: Conversation
    ):
        """Greeting should return 422 for invalid topic."""
        response = await client.post(
            f"/api/conversations/{test_conversation.id}/greeting",
            json={"topic": "cooking"},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    async def test_greeting_rejects_missing_topic(
        self, client, test_conversation: Conversation
    ):
        """Greeting should return 422 when topic is missing."""
        response = await client.post(
            f"/api/conversations/{test_conversation.id}/greeting",
            json={},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    async def test_greeting_rejects_nonexistent_conversation(self, client):
        """Greeting should return 404 for non-existent conversation."""
        fake_id = uuid.uuid4()
        response = await client.post(
            f"/api/conversations/{fake_id}/greeting",
            json={"topic": "sports"},
        )
        assert response.status_code == 404

    @pytest.mark.integration
    async def test_greeting_accepts_active_conversation_with_no_turns(
        self, client, test_conversation: Conversation
    ):
        """Greeting should accept an active conversation with no existing turns.

        We mock the orchestrator to avoid calling real LLM/TTS services.
        The endpoint returns an SSE response, so we check the status code.
        """
        with patch(
            "coyo.routers.conversations.TurnOrchestrator"
        ) as MockOrchestrator:
            mock_instance = MagicMock()

            async def mock_greeting(**kwargs):
                yield {"event": "ai_response_done", "data": {"text": "Hello!"}}
                yield {"event": "turn_complete", "data": {}}

            mock_instance.process_greeting = mock_greeting
            MockOrchestrator.return_value = mock_instance

            response = await client.post(
                f"/api/conversations/{test_conversation.id}/greeting",
                json={"topic": "sports"},
            )
            assert response.status_code == 200
