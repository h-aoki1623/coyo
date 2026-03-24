"""Unit tests for TurnOrchestrator with suggested topic support."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.services.turn_orchestrator import (
    TurnOrchestrator,
    _GREETING_SYSTEM_PROMPT,
    _SUGGESTED_GREETING_SYSTEM_PROMPT,
    _CONVERSATION_SYSTEM_PROMPT,
)


# ---------------------------------------------------------------------------
# process_greeting with article_context
# ---------------------------------------------------------------------------


class TestProcessGreetingWithArticleContext:
    """Tests for process_greeting when article_context is provided (suggested topics)."""

    @pytest.fixture
    def mock_llm(self):
        mock = MagicMock()

        async def mock_chat(messages, options=None):
            for token in ["Hey", "! ", "Great topic."]:
                yield token

        mock.chat = mock_chat
        return mock

    @pytest.fixture
    def mock_tts(self):
        mock = AsyncMock()
        mock.synthesize = AsyncMock(return_value="data:audio/mpeg;base64,fakeaudio")
        return mock

    @pytest.fixture
    def mock_turn_repo(self):
        mock = AsyncMock()
        mock_turn = MagicMock()
        mock_turn.id = uuid.uuid4()
        mock.create = AsyncMock(return_value=mock_turn)
        return mock

    @pytest.fixture
    def orchestrator(self, db_session: AsyncSession, mock_llm, mock_tts, mock_turn_repo):
        orch = TurnOrchestrator(db_session)
        orch._llm = mock_llm
        orch._tts = mock_tts
        orch._turn_repo = mock_turn_repo
        return orch

    @pytest.mark.unit
    async def test_uses_suggested_greeting_prompt_with_article_context(self, orchestrator):
        """When article_context is provided, the suggested greeting prompt should be used."""
        article_context = "Title: AI News\n\nAI is transforming industries."
        captured_messages = []

        async def capture_chat(messages, options=None):
            captured_messages.extend(messages)
            yield "Hello!"

        orchestrator._llm.chat = capture_chat

        async for _ in orchestrator.process_greeting(
            conversation_id=uuid.uuid4(), user_id=uuid.uuid4(),
            topic="suggested",
            article_context=article_context,
        ):
            pass

        assert len(captured_messages) == 1
        assert captured_messages[0].role == "system"
        expected = _SUGGESTED_GREETING_SYSTEM_PROMPT.format(
            article_context=article_context
        )
        assert captured_messages[0].content == expected

    @pytest.mark.unit
    async def test_uses_regular_greeting_prompt_without_article_context(self, orchestrator):
        """When article_context is None, the regular greeting prompt should be used."""
        captured_messages = []

        async def capture_chat(messages, options=None):
            captured_messages.extend(messages)
            yield "Hi!"

        orchestrator._llm.chat = capture_chat

        async for _ in orchestrator.process_greeting(
            conversation_id=uuid.uuid4(), user_id=uuid.uuid4(),
            topic="sports",
        ):
            pass

        assert len(captured_messages) == 1
        expected = _GREETING_SYSTEM_PROMPT.format(topic="sports")
        assert captured_messages[0].content == expected

    @pytest.mark.unit
    async def test_streams_correctly_with_article_context(self, orchestrator):
        """The event sequence should be correct even with article_context."""
        events = []
        async for event in orchestrator.process_greeting(
            conversation_id=uuid.uuid4(), user_id=uuid.uuid4(),
            topic="suggested",
            article_context="Title: Test\n\nContent here.",
        ):
            events.append(event)

        event_types = [e["event"] for e in events]
        assert "ai_response_chunk" in event_types
        assert "ai_response_done" in event_types
        assert "tts_audio_url" in event_types
        assert "turn_complete" in event_types

    @pytest.mark.unit
    async def test_empty_article_context_uses_regular_prompt(self, orchestrator):
        """Empty string article_context should still use the regular prompt."""
        captured_messages = []

        async def capture_chat(messages, options=None):
            captured_messages.extend(messages)
            yield "Hi!"

        orchestrator._llm.chat = capture_chat

        # Empty string is falsy, so it should use the regular prompt
        async for _ in orchestrator.process_greeting(
            conversation_id=uuid.uuid4(), user_id=uuid.uuid4(),
            topic="technology",
            article_context="",
        ):
            pass

        expected = _GREETING_SYSTEM_PROMPT.format(topic="technology")
        assert captured_messages[0].content == expected


# ---------------------------------------------------------------------------
# _build_messages with topic="suggested"
# ---------------------------------------------------------------------------


class TestBuildMessagesWithSuggestedTopic:
    """Tests for _build_messages when topic is 'suggested'."""

    @pytest.fixture
    def mock_turn_repo(self):
        mock = AsyncMock()
        mock.get_by_conversation_id = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def orchestrator(self, db_session: AsyncSession, mock_turn_repo):
        orch = TurnOrchestrator(db_session)
        orch._turn_repo = mock_turn_repo
        return orch

    @pytest.mark.unit
    async def test_suggested_topic_uses_human_readable_label(self, orchestrator):
        """The 'suggested' topic should be replaced with a human-readable label."""
        messages = await orchestrator._build_messages(
            uuid.uuid4(),
            "Hello",
            user_id=uuid.uuid4(),
            topic="suggested",
        )
        system_content = messages[0].content
        # Should NOT contain the literal word "suggested"
        assert "suggested" not in system_content.lower()
        # Should contain "trending" as the replacement
        assert "trending" in system_content.lower()

    @pytest.mark.unit
    async def test_regular_topic_used_as_is(self, orchestrator):
        """Regular topics should be used as-is in the system prompt."""
        messages = await orchestrator._build_messages(
            uuid.uuid4(),
            "Hello",
            user_id=uuid.uuid4(),
            topic="technology",
        )
        system_content = messages[0].content
        assert "technology" in system_content

    @pytest.mark.unit
    async def test_build_messages_includes_user_message(self, orchestrator):
        """The user's current message should be the last message."""
        messages = await orchestrator._build_messages(
            uuid.uuid4(),
            "Tell me about AI",
            user_id=uuid.uuid4(),
            topic="suggested",
        )
        assert messages[-1].role == "user"
        assert messages[-1].content == "Tell me about AI"

    @pytest.mark.unit
    async def test_build_messages_includes_history(self, orchestrator, mock_turn_repo):
        """Previous turns should be included in the message list."""
        prev_user = MagicMock()
        prev_user.role = "user"
        prev_user.text = "Hi there"

        prev_ai = MagicMock()
        prev_ai.role = "ai"
        prev_ai.text = "Hello! Nice to meet you."

        mock_turn_repo.get_by_conversation_id = AsyncMock(
            return_value=[prev_user, prev_ai]
        )

        messages = await orchestrator._build_messages(
            uuid.uuid4(),
            "What about sports?",
            user_id=uuid.uuid4(),
            topic="suggested",
        )
        # system + 2 history + current user = 4
        assert len(messages) == 4
        assert messages[1].role == "user"
        assert messages[1].content == "Hi there"
        assert messages[2].role == "assistant"
        assert messages[2].content == "Hello! Nice to meet you."
