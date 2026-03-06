"""Unit tests for the LLM client interface and OpenAI implementation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from coyo.exceptions import ExternalServiceError
from coyo.services.llm.base import ChatMessage, ChatOptions, ModelInfo
from coyo.services.llm.openai_client import OpenAIClient


# ---------------------------------------------------------------------------
# ChatMessage / ChatOptions / ModelInfo
# ---------------------------------------------------------------------------


class TestChatMessage:
    """Tests for the ChatMessage Pydantic model."""

    @pytest.mark.unit
    def test_valid_system_message(self):
        msg = ChatMessage(role="system", content="You are a helpful assistant.")
        assert msg.role == "system"
        assert msg.content == "You are a helpful assistant."

    @pytest.mark.unit
    def test_valid_user_message(self):
        msg = ChatMessage(role="user", content="Hello!")
        assert msg.role == "user"

    @pytest.mark.unit
    def test_valid_assistant_message(self):
        msg = ChatMessage(role="assistant", content="Hi there!")
        assert msg.role == "assistant"

    @pytest.mark.unit
    def test_empty_content(self):
        msg = ChatMessage(role="user", content="")
        assert msg.content == ""


class TestChatOptions:
    """Tests for the ChatOptions Pydantic model."""

    @pytest.mark.unit
    def test_default_values(self):
        opts = ChatOptions()
        assert opts.temperature == 0.8
        assert opts.max_tokens == 256

    @pytest.mark.unit
    def test_custom_values(self):
        opts = ChatOptions(temperature=0.3, max_tokens=1024)
        assert opts.temperature == 0.3
        assert opts.max_tokens == 1024


class TestModelInfo:
    """Tests for the ModelInfo Pydantic model."""

    @pytest.mark.unit
    def test_model_info(self):
        info = ModelInfo(provider="openai", model="gpt-5-mini")
        assert info.provider == "openai"
        assert info.model == "gpt-5-mini"


# ---------------------------------------------------------------------------
# OpenAIClient
# ---------------------------------------------------------------------------


class TestOpenAIClient:
    """Tests for the OpenAIClient implementation."""

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

    @pytest.mark.unit
    def test_get_model_returns_openai_info(self, openai_client):
        info = openai_client.get_model()
        assert info.provider == "openai"
        assert info.model == "gpt-5-mini"

    @pytest.mark.unit
    async def test_structured_returns_parsed_model(
        self, openai_client, mock_openai_client
    ):
        """Verify that structured() parses JSON into a Pydantic model."""

        class TestResponse(BaseModel):
            has_errors: bool
            corrected_text: str
            explanation: str
            items: list

        result = await openai_client.structured(
            [ChatMessage(role="system", content="test")],
            response_model=TestResponse,
        )
        assert isinstance(result, TestResponse)
        assert result.has_errors is False

    @pytest.mark.unit
    async def test_structured_api_failure_raises_external_service_error(
        self, openai_client, mock_openai_client
    ):
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API timeout"),
        )
        with pytest.raises(ExternalServiceError) as exc_info:
            await openai_client.structured(
                [ChatMessage(role="system", content="test")],
                response_model=ModelInfo,
            )
        assert "OpenAI" in exc_info.value.message

    @pytest.mark.unit
    async def test_structured_empty_response_raises_external_service_error(
        self, openai_client, mock_openai_client
    ):
        """Verify that an empty response content raises ExternalServiceError."""
        completion_message = MagicMock()
        completion_message.content = None
        completion_choice = MagicMock()
        completion_choice.message = completion_message
        completion_response = MagicMock()
        completion_response.choices = [completion_choice]
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=completion_response,
        )

        with pytest.raises(ExternalServiceError) as exc_info:
            await openai_client.structured(
                [ChatMessage(role="system", content="test")],
                response_model=ModelInfo,
            )
        assert "Empty response" in exc_info.value.message

    @pytest.mark.unit
    async def test_chat_streams_tokens(self, openai_client, mock_openai_client):
        """Verify that chat() yields streamed tokens."""

        # Create mock stream chunks
        class MockDelta:
            def __init__(self, content):
                self.content = content

        class MockChoice:
            def __init__(self, delta):
                self.delta = delta

        class MockChunk:
            def __init__(self, content):
                self.choices = [MockChoice(MockDelta(content))]

        # Create an async iterator for the stream
        async def mock_stream():
            for text in ["Hello", " ", "world"]:
                yield MockChunk(text)

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=mock_stream(),
        )

        messages = [ChatMessage(role="user", content="Hi")]
        tokens = []
        async for token in openai_client.chat(messages):
            tokens.append(token)

        assert tokens == ["Hello", " ", "world"]

    @pytest.mark.unit
    async def test_chat_api_failure_raises_external_service_error(
        self, openai_client, mock_openai_client
    ):
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Rate limit"),
        )

        with pytest.raises(ExternalServiceError) as exc_info:
            async for _ in openai_client.chat(
                [ChatMessage(role="user", content="test")]
            ):
                pass
        assert "OpenAI" in exc_info.value.message

    @pytest.mark.unit
    async def test_chat_skips_none_content(self, openai_client, mock_openai_client):
        """Verify that chat() skips chunks with None content."""

        class MockDelta:
            def __init__(self, content):
                self.content = content

        class MockChoice:
            def __init__(self, delta):
                self.delta = delta

        class MockChunk:
            def __init__(self, content):
                self.choices = [MockChoice(MockDelta(content))]

        async def mock_stream():
            yield MockChunk("Hello")
            yield MockChunk(None)
            yield MockChunk(" world")

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=mock_stream(),
        )

        messages = [ChatMessage(role="user", content="Hi")]
        tokens = []
        async for token in openai_client.chat(messages):
            tokens.append(token)

        assert tokens == ["Hello", " world"]
