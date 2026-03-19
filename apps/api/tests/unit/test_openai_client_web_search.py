"""Unit tests for OpenAIClient.chat_with_tools() web search integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coyo.exceptions import ExternalServiceError
from coyo.services.llm.base import ChatMessage, ChatOptions, TextChunk, WebSearchStarted
from coyo.services.llm.openai_client import OpenAIClient


class TestChatWithTools:
    """Tests for OpenAIClient.chat_with_tools()."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock AsyncOpenAI client."""
        return AsyncMock()

    @pytest.fixture
    def openai_client(self, mock_openai_client):
        """Create an OpenAIClient with a mocked underlying client."""
        with patch(
            "coyo.services.llm.openai_client.AsyncOpenAI",
            return_value=mock_openai_client,
        ):
            client = OpenAIClient(model="gpt-5-mini")
            client._client = mock_openai_client
            return client

    def _make_event(self, event_type: str, **kwargs):
        """Create a mock SSE event with the given type."""
        event = MagicMock()
        event.type = event_type
        for key, value in kwargs.items():
            setattr(event, key, value)
        return event

    def _setup_stream(self, mock_openai_client, events):
        """Configure mock to yield the given events from responses.stream()."""

        async def async_event_iter():
            for e in events:
                yield e

        # responses.stream() returns a context manager that yields events
        stream_cm = AsyncMock()
        stream_cm.__aenter__ = AsyncMock(return_value=async_event_iter())
        mock_openai_client.responses.stream = MagicMock(return_value=stream_cm)

    @pytest.mark.unit
    async def test_web_search_started_yielded_once(
        self, openai_client, mock_openai_client
    ):
        """WebSearchStarted is yielded at most once even with multiple in_progress events."""
        events = [
            self._make_event("response.web_search_call.in_progress"),
            self._make_event("response.web_search_call.in_progress"),
            self._make_event("response.output_text.delta", delta="Hello"),
        ]
        self._setup_stream(mock_openai_client, events)

        results = []
        async for event in openai_client.chat_with_tools(
            [ChatMessage(role="user", content="test")]
        ):
            results.append(event)

        web_search_events = [e for e in results if isinstance(e, WebSearchStarted)]
        assert len(web_search_events) == 1

    @pytest.mark.unit
    async def test_text_chunks_yielded_for_delta_events(
        self, openai_client, mock_openai_client
    ):
        """TextChunk events are yielded for response.output_text.delta events."""
        events = [
            self._make_event("response.output_text.delta", delta="Hello"),
            self._make_event("response.output_text.delta", delta=" world"),
        ]
        self._setup_stream(mock_openai_client, events)

        results = []
        async for event in openai_client.chat_with_tools(
            [ChatMessage(role="user", content="test")]
        ):
            results.append(event)

        assert len(results) == 2
        assert all(isinstance(e, TextChunk) for e in results)
        assert results[0].text == "Hello"
        assert results[1].text == " world"

    @pytest.mark.unit
    async def test_system_message_extracted_to_instructions(
        self, openai_client, mock_openai_client
    ):
        """System messages are extracted to the instructions parameter."""
        events = [
            self._make_event("response.output_text.delta", delta="Hi"),
        ]
        self._setup_stream(mock_openai_client, events)

        messages = [
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="Hello"),
        ]

        # Consume the generator
        async for _ in openai_client.chat_with_tools(messages):
            pass

        # Verify the stream was called with instructions extracted from system message
        call_kwargs = mock_openai_client.responses.stream.call_args
        assert call_kwargs.kwargs["instructions"] == "You are helpful."
        # System message should NOT appear in input messages
        input_msgs = call_kwargs.kwargs["input"]
        assert all(m["role"] != "system" for m in input_msgs)
        assert len(input_msgs) == 1
        assert input_msgs[0]["role"] == "user"

    @pytest.mark.unit
    async def test_no_system_message_uses_empty_instructions(
        self, openai_client, mock_openai_client
    ):
        """When no system message is provided, instructions defaults to empty string."""
        events = [
            self._make_event("response.output_text.delta", delta="Hi"),
        ]
        self._setup_stream(mock_openai_client, events)

        messages = [ChatMessage(role="user", content="Hello")]

        async for _ in openai_client.chat_with_tools(messages):
            pass

        call_kwargs = mock_openai_client.responses.stream.call_args
        assert call_kwargs.kwargs["instructions"] == ""

    @pytest.mark.unit
    async def test_api_failure_raises_external_service_error(
        self, openai_client, mock_openai_client
    ):
        """ExternalServiceError is raised on API failure."""
        mock_openai_client.responses.stream = MagicMock(
            side_effect=Exception("API connection failed"),
        )

        with pytest.raises(ExternalServiceError) as exc_info:
            async for _ in openai_client.chat_with_tools(
                [ChatMessage(role="user", content="test")]
            ):
                pass
        assert "OpenAI" in exc_info.value.message

    @pytest.mark.unit
    async def test_mixed_events_order_preserved(
        self, openai_client, mock_openai_client
    ):
        """WebSearchStarted comes before TextChunks when search is triggered."""
        events = [
            self._make_event("response.web_search_call.in_progress"),
            self._make_event("response.output_text.delta", delta="Result: "),
            self._make_event("response.output_text.delta", delta="answer"),
        ]
        self._setup_stream(mock_openai_client, events)

        results = []
        async for event in openai_client.chat_with_tools(
            [ChatMessage(role="user", content="What is the news?")]
        ):
            results.append(event)

        assert len(results) == 3
        assert isinstance(results[0], WebSearchStarted)
        assert isinstance(results[1], TextChunk)
        assert isinstance(results[2], TextChunk)
        assert results[1].text == "Result: "
        assert results[2].text == "answer"

    @pytest.mark.unit
    async def test_unknown_event_types_ignored(
        self, openai_client, mock_openai_client
    ):
        """Events with unknown types are silently skipped."""
        events = [
            self._make_event("response.created"),
            self._make_event("response.output_text.delta", delta="Hi"),
            self._make_event("response.completed"),
        ]
        self._setup_stream(mock_openai_client, events)

        results = []
        async for event in openai_client.chat_with_tools(
            [ChatMessage(role="user", content="test")]
        ):
            results.append(event)

        assert len(results) == 1
        assert isinstance(results[0], TextChunk)

    @pytest.mark.unit
    async def test_custom_options_passed_to_stream(
        self, openai_client, mock_openai_client
    ):
        """ChatOptions values are forwarded to the responses.stream call."""
        events = [
            self._make_event("response.output_text.delta", delta="ok"),
        ]
        self._setup_stream(mock_openai_client, events)

        opts = ChatOptions(temperature=0.3, max_tokens=512)
        async for _ in openai_client.chat_with_tools(
            [ChatMessage(role="user", content="test")],
            options=opts,
        ):
            pass

        call_kwargs = mock_openai_client.responses.stream.call_args
        assert call_kwargs.kwargs["temperature"] == 0.3
        assert call_kwargs.kwargs["max_output_tokens"] == 512
