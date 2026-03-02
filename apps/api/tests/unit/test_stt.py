"""Unit tests for the STT (Speech-to-Text) service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coto.exceptions import ExternalServiceError, STTRecognitionError
from coto.services.stt import STTService


class TestSTTService:
    """Tests for the STTService.transcribe method."""

    @pytest.fixture
    def stt_service(self, mock_openai_client):
        """Create an STTService with a mocked OpenAI client."""
        with patch("coto.services.stt.AsyncOpenAI", return_value=mock_openai_client):
            service = STTService()
            service._client = mock_openai_client
            return service

    @pytest.mark.unit
    async def test_transcribe_returns_text(self, stt_service, mock_openai_client):
        """Verify that transcribe returns the transcribed text."""
        result = await stt_service.transcribe(b"audio-data", filename="test.m4a")
        assert result == "I went to the store yesterday."
        mock_openai_client.audio.transcriptions.create.assert_called_once()

    @pytest.mark.unit
    async def test_transcribe_strips_whitespace(self, stt_service, mock_openai_client):
        """Verify that leading/trailing whitespace is stripped."""
        transcription = MagicMock()
        transcription.text = "  Hello there!  "
        mock_openai_client.audio.transcriptions.create = AsyncMock(
            return_value=transcription,
        )
        result = await stt_service.transcribe(b"audio-data")
        assert result == "Hello there!"

    @pytest.mark.unit
    async def test_transcribe_empty_result_raises_stt_recognition_error(
        self, stt_service, mock_openai_client
    ):
        """Verify that empty transcription raises STTRecognitionError."""
        transcription = MagicMock()
        transcription.text = ""
        mock_openai_client.audio.transcriptions.create = AsyncMock(
            return_value=transcription,
        )
        with pytest.raises(STTRecognitionError):
            await stt_service.transcribe(b"silence")

    @pytest.mark.unit
    async def test_transcribe_whitespace_only_raises_stt_recognition_error(
        self, stt_service, mock_openai_client
    ):
        """Verify that whitespace-only transcription raises STTRecognitionError."""
        transcription = MagicMock()
        transcription.text = "   "
        mock_openai_client.audio.transcriptions.create = AsyncMock(
            return_value=transcription,
        )
        with pytest.raises(STTRecognitionError):
            await stt_service.transcribe(b"silence")

    @pytest.mark.unit
    async def test_transcribe_api_failure_raises_external_service_error(
        self, stt_service, mock_openai_client
    ):
        """Verify that API failures raise ExternalServiceError."""
        mock_openai_client.audio.transcriptions.create = AsyncMock(
            side_effect=Exception("Connection timeout"),
        )
        with pytest.raises(ExternalServiceError) as exc_info:
            await stt_service.transcribe(b"audio-data")
        assert "STT" in exc_info.value.message
        assert exc_info.value.status_code == 502

    @pytest.mark.unit
    async def test_content_type_m4a(self, stt_service, mock_openai_client):
        """Verify correct content type for .m4a files."""
        await stt_service.transcribe(b"audio-data", filename="recording.m4a")
        call_args = mock_openai_client.audio.transcriptions.create.call_args
        file_tuple = call_args.kwargs["file"]
        assert file_tuple[0] == "recording.m4a"
        assert file_tuple[2] == "audio/mp4"

    @pytest.mark.unit
    async def test_content_type_webm(self, stt_service, mock_openai_client):
        """Verify correct content type for .webm files."""
        await stt_service.transcribe(b"audio-data", filename="recording.webm")
        call_args = mock_openai_client.audio.transcriptions.create.call_args
        file_tuple = call_args.kwargs["file"]
        assert file_tuple[2] == "audio/webm"

    @pytest.mark.unit
    async def test_content_type_wav(self, stt_service, mock_openai_client):
        """Verify correct content type for .wav files."""
        await stt_service.transcribe(b"audio-data", filename="recording.wav")
        call_args = mock_openai_client.audio.transcriptions.create.call_args
        file_tuple = call_args.kwargs["file"]
        assert file_tuple[2] == "audio/wav"

    @pytest.mark.unit
    async def test_content_type_mp3(self, stt_service, mock_openai_client):
        """Verify correct content type for .mp3 files."""
        await stt_service.transcribe(b"audio-data", filename="recording.mp3")
        call_args = mock_openai_client.audio.transcriptions.create.call_args
        file_tuple = call_args.kwargs["file"]
        assert file_tuple[2] == "audio/mpeg"

    @pytest.mark.unit
    async def test_content_type_mp4(self, stt_service, mock_openai_client):
        """Verify correct content type for .mp4 files."""
        await stt_service.transcribe(b"audio-data", filename="recording.mp4")
        call_args = mock_openai_client.audio.transcriptions.create.call_args
        file_tuple = call_args.kwargs["file"]
        assert file_tuple[2] == "audio/mp4"

    @pytest.mark.unit
    async def test_content_type_unknown_defaults_to_mp4(
        self, stt_service, mock_openai_client
    ):
        """Verify that unknown extensions default to audio/mp4."""
        await stt_service.transcribe(b"audio-data", filename="recording.ogg")
        call_args = mock_openai_client.audio.transcriptions.create.call_args
        file_tuple = call_args.kwargs["file"]
        assert file_tuple[2] == "audio/mp4"

    @pytest.mark.unit
    async def test_content_type_no_extension_defaults_to_mp4(
        self, stt_service, mock_openai_client
    ):
        """Verify that files without extensions default to audio/mp4."""
        await stt_service.transcribe(b"audio-data", filename="audio")
        call_args = mock_openai_client.audio.transcriptions.create.call_args
        file_tuple = call_args.kwargs["file"]
        assert file_tuple[2] == "audio/mp4"

    @pytest.mark.unit
    async def test_default_filename(self, stt_service, mock_openai_client):
        """Verify that default filename is audio.m4a."""
        await stt_service.transcribe(b"audio-data")
        call_args = mock_openai_client.audio.transcriptions.create.call_args
        file_tuple = call_args.kwargs["file"]
        assert file_tuple[0] == "audio.m4a"

    @pytest.mark.unit
    async def test_transcribe_uses_whisper_model(self, stt_service, mock_openai_client):
        """Verify that the Whisper model is used for transcription."""
        await stt_service.transcribe(b"audio-data")
        call_args = mock_openai_client.audio.transcriptions.create.call_args
        assert call_args.kwargs["model"] == "whisper-1"
