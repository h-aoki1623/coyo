"""Speech-to-text service using OpenAI transcription API."""

from typing import Any

import structlog
from openai import AsyncOpenAI

from coyo.config import get_settings
from coyo.exceptions import ExternalServiceError, STTRecognitionError

logger = structlog.get_logger()


class STTService:
    """Transcribes audio to text using OpenAI transcription models.

    Accepts raw audio bytes and returns the transcribed text.
    Raises STTRecognitionError if no speech is detected,
    or ExternalServiceError on API failures.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.stt_model

    async def transcribe(
        self,
        audio_data: bytes,
        filename: str = "audio.m4a",
        *,
        prompt: str | None = None,
    ) -> str:
        """Transcribe audio bytes using OpenAI transcription API.

        Args:
            audio_data: Raw audio bytes from the client.
            filename: Filename hint for the audio format (determines content type).
            prompt: Optional context hint to improve transcription accuracy
                (e.g. topic keywords, proper nouns, prior conversation text).

        Returns:
            The transcribed text, stripped of leading/trailing whitespace.

        Raises:
            STTRecognitionError: If the transcription result is empty.
            ExternalServiceError: If the API call fails.
        """
        logger.info("stt_transcribe_start", audio_bytes=len(audio_data), model=self._model)

        # Determine content type from filename extension
        content_types: dict[str, str] = {
            ".webm": "audio/webm",
            ".m4a": "audio/mp4",
            ".mp4": "audio/mp4",
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
        }
        ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
        content_type = content_types.get(ext, "audio/mp4")

        try:
            kwargs: dict[str, Any] = {
                "model": self._model,
                "file": (filename, audio_data, content_type),
                # Coyo targets English conversation practice; hardcoded by design.
                "language": "en",
            }
            if prompt:
                kwargs["prompt"] = prompt

            transcription = await self._client.audio.transcriptions.create(**kwargs)
        except Exception as exc:
            logger.error("stt_transcribe_failed", error=str(exc))
            raise ExternalServiceError("STT", str(exc)) from exc

        text = transcription.text.strip()
        if not text:
            logger.warning("stt_empty_result")
            raise STTRecognitionError()

        logger.info("stt_transcribe_done", text_length=len(text))
        return text
