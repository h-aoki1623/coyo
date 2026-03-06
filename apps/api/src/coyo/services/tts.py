"""Text-to-speech service using OpenAI TTS API."""

import base64

import structlog
from openai import AsyncOpenAI

from coyo.config import get_settings
from coyo.exceptions import ExternalServiceError

logger = structlog.get_logger()


class TTSService:
    """Generates speech audio from text using OpenAI TTS.

    Phase 1 returns a base64 data URL for the MP3 audio.
    Phase 2 will upload to GCS and return a signed URL instead.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.tts_model
        self._voice = settings.tts_voice

    async def synthesize(self, text: str) -> str:
        """Generate speech from text and return a data URL.

        Args:
            text: The text to synthesize into speech.

        Returns:
            A base64 data URL containing the MP3 audio
            (format: ``data:audio/mpeg;base64,{encoded}``).

        Raises:
            ExternalServiceError: If the TTS API call fails.
        """
        logger.info("tts_synthesize_start", text_length=len(text))

        try:
            response = await self._client.audio.speech.create(
                model=self._model,
                voice=self._voice,
                input=text,
                response_format="mp3",
            )
            audio_bytes = response.content
        except Exception as exc:
            logger.error("tts_synthesize_failed", error=str(exc))
            raise ExternalServiceError("TTS", str(exc)) from exc

        encoded = base64.b64encode(audio_bytes).decode("ascii")
        data_url = f"data:audio/mpeg;base64,{encoded}"

        logger.info(
            "tts_synthesize_done",
            audio_bytes=len(audio_bytes),
            data_url_length=len(data_url),
        )
        return data_url
