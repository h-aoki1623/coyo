"""Unit tests for web search integration in TurnOrchestrator.process_turn()."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coyo.services.llm.base import TextChunk, WebSearchStarted


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_turn(turn_id=None, role="user", text="hello", sequence=1):
    """Create a mock Turn object."""
    turn = MagicMock()
    turn.id = turn_id or uuid.uuid4()
    turn.role = role
    turn.text = text
    turn.sequence = sequence
    return turn


def _make_mock_correction(corrected_text="hello", explanation="ok"):
    """Create a mock TurnCorrection."""
    correction = MagicMock()
    correction.id = uuid.uuid4()
    correction.corrected_text = corrected_text
    correction.explanation = explanation
    return correction


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTurnOrchestratorWebSearch:
    """Tests for web search branching in TurnOrchestrator.process_turn()."""

    @pytest.fixture
    def conversation_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def user_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.commit = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def orchestrator(self, mock_session):
        """Build a TurnOrchestrator with all dependencies mocked."""
        with (
            patch("coyo.services.turn_orchestrator.STTService") as mock_stt_cls,
            patch("coyo.services.turn_orchestrator.TTSService") as mock_tts_cls,
            patch("coyo.services.turn_orchestrator.CorrectionService") as mock_corr_cls,
            patch("coyo.services.turn_orchestrator.OpenAIClient") as mock_llm_cls,
            patch("coyo.services.turn_orchestrator.TurnRepository") as mock_repo_cls,
        ):
            # STT
            mock_stt = AsyncMock()
            mock_stt.transcribe = AsyncMock(return_value="yeah")
            mock_stt_cls.return_value = mock_stt

            # TTS
            mock_tts = AsyncMock()
            mock_tts.synthesize = AsyncMock(return_value="https://example.com/audio.mp3")
            mock_tts_cls.return_value = mock_tts

            # Correction
            mock_correction = AsyncMock()
            mock_correction.analyze_turn = AsyncMock(return_value=None)
            mock_corr_cls.return_value = mock_correction

            # LLM
            mock_llm = MagicMock()
            mock_llm_cls.return_value = mock_llm

            # Turn repository
            mock_repo = AsyncMock()
            mock_repo.get_by_conversation_id = AsyncMock(return_value=[])
            mock_repo.create = AsyncMock(
                side_effect=lambda **kwargs: _make_mock_turn(
                    role=kwargs.get("role", "user"),
                    text=kwargs.get("text", ""),
                    sequence=kwargs.get("sequence", 1),
                )
            )
            mock_repo_cls.return_value = mock_repo

            from coyo.services.turn_orchestrator import TurnOrchestrator

            orch = TurnOrchestrator(mock_session)

            # Store mocks for assertions
            orch._mock_stt = mock_stt
            orch._mock_tts = mock_tts
            orch._mock_correction = mock_correction
            orch._mock_llm = mock_llm
            orch._mock_repo = mock_repo

            yield orch

    @pytest.mark.unit
    async def test_filler_turn_uses_chat_no_web_search(
        self, orchestrator, conversation_id, user_id
    ):
        """Filler turns ('yeah') use chat() and never emit web_search_started."""
        orchestrator._mock_stt.transcribe = AsyncMock(return_value="yeah")

        async def mock_chat(messages, options=None):
            yield "Sure!"

        orchestrator._mock_llm.chat = mock_chat

        events = []
        async for event in orchestrator.process_turn(
            conversation_id=conversation_id,
            user_id=user_id,
            audio_data=b"fake-audio",
            topic="general",
        ):
            events.append(event)

        event_types = [e["event"] for e in events]
        assert "web_search_started" not in event_types
        assert "stt_result" in event_types
        assert "ai_response_chunk" in event_types
        assert "ai_response_done" in event_types

    @pytest.mark.unit
    async def test_non_filler_turn_uses_chat_with_tools(
        self, orchestrator, conversation_id, user_id
    ):
        """Non-filler turns use chat_with_tools() and can emit web_search_started."""
        orchestrator._mock_stt.transcribe = AsyncMock(
            return_value="What happened in the election?"
        )

        async def mock_chat_with_tools(messages, options=None):
            yield WebSearchStarted()
            yield TextChunk(text="The election results show...")

        orchestrator._mock_llm.chat_with_tools = mock_chat_with_tools

        events = []
        async for event in orchestrator.process_turn(
            conversation_id=conversation_id,
            user_id=user_id,
            audio_data=b"fake-audio",
            topic="general",
        ):
            events.append(event)

        event_types = [e["event"] for e in events]
        assert "web_search_started" in event_types
        assert "ai_response_chunk" in event_types
        assert "ai_response_done" in event_types

    @pytest.mark.unit
    async def test_non_filler_without_web_search_result(
        self, orchestrator, conversation_id, user_id
    ):
        """Non-filler turns that don't trigger web search still work correctly."""
        orchestrator._mock_stt.transcribe = AsyncMock(
            return_value="Tell me about your hobby"
        )

        async def mock_chat_with_tools(messages, options=None):
            yield TextChunk(text="I enjoy reading books.")

        orchestrator._mock_llm.chat_with_tools = mock_chat_with_tools

        events = []
        async for event in orchestrator.process_turn(
            conversation_id=conversation_id,
            user_id=user_id,
            audio_data=b"fake-audio",
            topic="general",
        ):
            events.append(event)

        event_types = [e["event"] for e in events]
        assert "web_search_started" not in event_types
        assert "ai_response_chunk" in event_types
        assert "ai_response_done" in event_types

        # Verify the ai_response_done has the full text
        done_events = [e for e in events if e["event"] == "ai_response_done"]
        assert done_events[0]["data"]["text"] == "I enjoy reading books."

    @pytest.mark.unit
    async def test_filler_turn_full_text_accumulated(
        self, orchestrator, conversation_id, user_id
    ):
        """Filler turn accumulates full AI text from chat() chunks."""
        orchestrator._mock_stt.transcribe = AsyncMock(return_value="ok")

        async def mock_chat(messages, options=None):
            yield "That's "
            yield "great!"

        orchestrator._mock_llm.chat = mock_chat

        events = []
        async for event in orchestrator.process_turn(
            conversation_id=conversation_id,
            user_id=user_id,
            audio_data=b"fake-audio",
            topic="general",
        ):
            events.append(event)

        done_events = [e for e in events if e["event"] == "ai_response_done"]
        assert done_events[0]["data"]["text"] == "That's great!"

    @pytest.mark.unit
    async def test_non_filler_turn_full_text_accumulated_from_text_chunks(
        self, orchestrator, conversation_id, user_id
    ):
        """Non-filler turn accumulates full AI text from TextChunk events only."""
        orchestrator._mock_stt.transcribe = AsyncMock(
            return_value="What is the weather today?"
        )

        async def mock_chat_with_tools(messages, options=None):
            yield WebSearchStarted()
            yield TextChunk(text="It's ")
            yield TextChunk(text="sunny today.")

        orchestrator._mock_llm.chat_with_tools = mock_chat_with_tools

        events = []
        async for event in orchestrator.process_turn(
            conversation_id=conversation_id,
            user_id=user_id,
            audio_data=b"fake-audio",
            topic="general",
        ):
            events.append(event)

        done_events = [e for e in events if e["event"] == "ai_response_done"]
        assert done_events[0]["data"]["text"] == "It's sunny today."
