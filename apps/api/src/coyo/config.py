"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal, Self
from urllib.parse import urlparse

from pydantic import ConfigDict, model_validator
from pydantic_settings import BaseSettings

_DEV_CORS_ORIGINS: tuple[str, ...] = ("http://localhost:8081", "http://localhost:19006")


class Settings(BaseSettings):
    """Central configuration for the Coyo API.

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
    gcs_bucket_name: str = "coyo-audio-dev"
    gcs_audio_ttl_seconds: int = 3600

    # Firebase
    firebase_project_id: str | None = None
    firebase_service_account_path: str | None = None

    # CORS
    cors_allowed_origins: list[str] = []

    # Upload limits
    max_audio_size_bytes: int = 10 * 1024 * 1024  # 10 MB

    # Rate Limiting
    rate_limit_per_minute: int = 30

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    @model_validator(mode="after")
    def validate_cors_origins(self) -> Self:
        """Validate CORS origins based on environment.

        - Development/staging: uses default localhost origins if none configured.
        - Production: rejects non-HTTPS origins to prevent insecure access.
        """
        if self.environment != "production":
            if not self.cors_allowed_origins:
                self.cors_allowed_origins = list(_DEV_CORS_ORIGINS)
            return self

        invalid_origins = [
            origin
            for origin in self.cors_allowed_origins
            if urlparse(origin).scheme != "https" or not urlparse(origin).netloc
        ]
        if invalid_origins:
            raise ValueError(
                "In production, all CORS origins must use HTTPS. "
                f"Invalid origins: {invalid_origins}"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Lazily instantiate and cache application settings.

    Defers environment variable validation until first access,
    allowing module imports to succeed without a .env file.
    """
    return Settings()  # type: ignore[call-arg]
