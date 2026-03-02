"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the Coto API.

    All values are loaded from environment variables or a .env file.
    """

    # App
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # Database
    database_url: str
    redis_url: str

    # External APIs
    openai_api_key: str

    # LLM Config
    llm_conversation_model: str = "gpt-4.1-mini"
    llm_correction_model: str = "gpt-4.1-mini"

    # TTS Config
    tts_voice: str = "nova"
    tts_model: str = "tts-1"

    # GCS
    gcs_bucket_name: str = "coto-audio-dev"
    gcs_audio_ttl_seconds: int = 3600

    # CORS
    cors_allowed_origins: list[str] = ["http://localhost:8081", "http://localhost:19006"]

    # Upload limits
    max_audio_size_bytes: int = 10 * 1024 * 1024  # 10 MB

    # Rate Limiting
    rate_limit_per_minute: int = 30

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Lazily instantiate and cache application settings.

    Defers environment variable validation until first access,
    allowing module imports to succeed without a .env file.
    """
    return Settings()  # type: ignore[call-arg]
