"""Unit tests for CORS origin validation in Settings."""

import pytest
from pydantic import ValidationError

from coyo.config import Settings, _DEV_CORS_ORIGINS

# Required fields that Settings needs but are irrelevant to CORS validation.
_REQUIRED_FIELDS = {
    "database_url": "sqlite+aiosqlite:///",
    "redis_url": "redis://localhost:6379",
    "openai_api_key": "test-key",
}


def _make_settings(**overrides: object) -> Settings:
    """Create a Settings instance with required fields pre-filled."""
    kwargs = {**_REQUIRED_FIELDS, **overrides}
    return Settings.model_validate(kwargs)


class TestCorsValidationDevelopment:
    """CORS origin validation for non-production environments."""

    @pytest.mark.unit
    def test_development_empty_origins_auto_fills_dev_defaults(self):
        settings = _make_settings(environment="development", cors_allowed_origins=[])

        assert settings.cors_allowed_origins == list(_DEV_CORS_ORIGINS)

    @pytest.mark.unit
    def test_development_no_origins_specified_auto_fills_dev_defaults(self):
        settings = _make_settings(environment="development")

        assert settings.cors_allowed_origins == list(_DEV_CORS_ORIGINS)

    @pytest.mark.unit
    def test_development_explicit_origins_kept_as_is(self):
        custom = ["http://192.168.1.100:3000", "http://my-dev-server:8080"]
        settings = _make_settings(environment="development", cors_allowed_origins=custom)

        assert settings.cors_allowed_origins == custom

    @pytest.mark.unit
    def test_development_allows_http_origins(self):
        origins = ["http://example.com"]
        settings = _make_settings(environment="development", cors_allowed_origins=origins)

        assert settings.cors_allowed_origins == origins

    @pytest.mark.unit
    def test_development_auto_fill_does_not_mutate_module_constant(self):
        settings = _make_settings(environment="development", cors_allowed_origins=[])

        # Mutating the settings list should not affect the module constant.
        settings.cors_allowed_origins.append("http://extra:9999")
        assert _DEV_CORS_ORIGINS == ("http://localhost:8081", "http://localhost:19006")


class TestCorsValidationStaging:
    """Staging environment should behave like development."""

    @pytest.mark.unit
    def test_staging_empty_origins_auto_fills_dev_defaults(self):
        settings = _make_settings(environment="staging", cors_allowed_origins=[])

        assert settings.cors_allowed_origins == list(_DEV_CORS_ORIGINS)

    @pytest.mark.unit
    def test_staging_explicit_origins_kept_as_is(self):
        custom = ["http://staging.example.com"]
        settings = _make_settings(environment="staging", cors_allowed_origins=custom)

        assert settings.cors_allowed_origins == custom


class TestCorsValidationProduction:
    """CORS origin validation for production environment."""

    @pytest.mark.unit
    def test_production_empty_origins_allowed(self):
        settings = _make_settings(environment="production", cors_allowed_origins=[])

        assert settings.cors_allowed_origins == []

    @pytest.mark.unit
    def test_production_https_origins_allowed(self):
        origins = ["https://app.example.com", "https://admin.example.com"]
        settings = _make_settings(
            environment="production", cors_allowed_origins=origins
        )

        assert settings.cors_allowed_origins == origins

    @pytest.mark.unit
    def test_production_single_https_origin_allowed(self):
        origins = ["https://myapp.com"]
        settings = _make_settings(
            environment="production", cors_allowed_origins=origins
        )

        assert settings.cors_allowed_origins == origins

    @pytest.mark.unit
    def test_production_http_origin_rejected(self):
        with pytest.raises(ValidationError, match="HTTPS"):
            _make_settings(
                environment="production",
                cors_allowed_origins=["http://insecure.example.com"],
            )

    @pytest.mark.unit
    def test_production_localhost_http_rejected(self):
        with pytest.raises(ValidationError, match="HTTPS"):
            _make_settings(
                environment="production",
                cors_allowed_origins=["http://localhost:8081"],
            )

    @pytest.mark.unit
    def test_production_localhost_https_allowed(self):
        origins = ["https://localhost:8081"]
        settings = _make_settings(
            environment="production", cors_allowed_origins=origins
        )

        assert settings.cors_allowed_origins == origins

    @pytest.mark.unit
    def test_production_mixed_https_and_http_rejected(self):
        with pytest.raises(ValidationError, match="HTTPS"):
            _make_settings(
                environment="production",
                cors_allowed_origins=[
                    "https://good.example.com",
                    "http://bad.example.com",
                ],
            )

    @pytest.mark.unit
    def test_production_error_message_lists_invalid_origins(self):
        bad_origin = "http://insecure.example.com"
        with pytest.raises(ValidationError, match=bad_origin):
            _make_settings(
                environment="production",
                cors_allowed_origins=[bad_origin],
            )

    @pytest.mark.unit
    def test_production_origin_without_scheme_rejected(self):
        with pytest.raises(ValidationError, match="HTTPS"):
            _make_settings(
                environment="production",
                cors_allowed_origins=["example.com"],
            )

    @pytest.mark.unit
    def test_production_wildcard_origin_rejected(self):
        with pytest.raises(ValidationError, match="HTTPS"):
            _make_settings(
                environment="production",
                cors_allowed_origins=["*"],
            )
