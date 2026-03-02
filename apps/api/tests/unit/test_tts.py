"""Unit tests for the TTS (Text-to-Speech) service."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coto.exceptions import ExternalServiceError
from coto.services.tts import TTSService


class TestTTSService:
    """Tests for the TTSService.synthesize method."""

    @pytest.fixture
    def tts_service(self, mock_openai_client):
        """Create a TTSService with a mocked OpenAI client."""
        with patch("coto.services.tts.AsyncOpenAI", return_value=mock_openai_client):
            service = TTSService()
            service._client = mock_openai_client
            return service

    @pytest.mark.unit
    async def test_synthesize_returns_data_url(self, tts_service):
        """Verify that synthesize returns a base64 data URL."""
        result = await tts_service.synthesize("Hello world")
        assert result.startswith("data:audio/mpeg;base64,")

    @pytest.mark.unit
    async def test_synthesize_data_url_is_valid_base64(self, tts_service):
        """Verify that the base64 portion of the data URL is decodable."""
        result = await tts_service.synthesize("Hello world")
        base64_part = result.split(",", 1)[1]
        decoded = base64.b64decode(base64_part)
        assert decoded == b"fake-audio-bytes"

    @pytest.mark.unit
    async def test_synthesize_calls_openai_tts(
        self, tts_service, mock_openai_client
    ):
        """Verify that synthesize calls the OpenAI TTS API."""
        await tts_service.synthesize("Hello world")
        mock_openai_client.audio.speech.create.assert_called_once()

    @pytest.mark.unit
    async def test_synthesize_passes_correct_params(
        self, tts_service, mock_openai_client
    ):
        """Verify correct model, voice, input, and format are passed to the API."""
        await tts_service.synthesize("Hello world")
        call_args = mock_openai_client.audio.speech.create.call_args
        assert call_args.kwargs["input"] == "Hello world"
        assert call_args.kwargs["response_format"] == "mp3"
        assert call_args.kwargs["model"] == "tts-1"
        assert call_args.kwargs["voice"] == "nova"

    @pytest.mark.unit
    async def test_synthesize_api_failure_raises_external_service_error(
        self, tts_service, mock_openai_client
    ):
        """Verify that API failures raise ExternalServiceError."""
        mock_openai_client.audio.speech.create = AsyncMock(
            side_effect=Exception("Rate limit exceeded"),
        )
        with pytest.raises(ExternalServiceError) as exc_info:
            await tts_service.synthesize("Hello world")
        assert "TTS" in exc_info.value.message
        assert exc_info.value.status_code == 502

    @pytest.mark.unit
    async def test_synthesize_with_empty_text(self, tts_service, mock_openai_client):
        """Verify that synthesize handles empty text without error."""
        result = await tts_service.synthesize("")
        assert result.startswith("data:audio/mpeg;base64,")
        mock_openai_client.audio.speech.create.assert_called_once()

    @pytest.mark.unit
    async def test_synthesize_with_long_text(self, tts_service, mock_openai_client):
        """Verify that synthesize handles long text."""
        long_text = "Hello world. " * 100
        result = await tts_service.synthesize(long_text)
        assert result.startswith("data:audio/mpeg;base64,")

    @pytest.mark.unit
    async def test_synthesize_with_unicode(self, tts_service, mock_openai_client):
        """Verify that synthesize handles Unicode text."""
        result = await tts_service.synthesize("Caf\u00e9 and na\u00efve")
        assert result.startswith("data:audio/mpeg;base64,")

    @pytest.mark.unit
    async def test_synthesize_with_special_characters(
        self, tts_service, mock_openai_client
    ):
        """Verify that synthesize handles special characters."""
        result = await tts_service.synthesize("Hello! How's it going? #awesome")
        assert result.startswith("data:audio/mpeg;base64,")
