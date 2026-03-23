"""Unit tests for the verify_cloud_task_token dependency."""

from unittest.mock import patch

import pytest

from coyo.dependencies import verify_cloud_task_token
from coyo.exceptions import AuthenticationError


class TestVerifyCloudTaskToken:
    """Tests for OIDC token verification dependency."""

    @pytest.mark.unit
    async def test_skips_when_service_url_not_configured(self, mock_settings):
        """When cloud_run_service_url is None, returns without error."""
        mock_settings.cloud_run_service_url = None

        # Should not raise even without Authorization header
        await verify_cloud_task_token(authorization=None)

    @pytest.mark.unit
    async def test_raises_when_no_auth_header_in_production(self, mock_settings):
        """When cloud_run_service_url is set but no Authorization header, raises."""
        mock_settings.cloud_run_service_url = "https://my-service.run.app"

        with pytest.raises(AuthenticationError, match="Missing Authorization header"):
            await verify_cloud_task_token(authorization=None)

    @pytest.mark.unit
    async def test_raises_on_invalid_bearer_format_no_space(self, mock_settings):
        """When Authorization header has no space separator, raises."""
        mock_settings.cloud_run_service_url = "https://my-service.run.app"

        with pytest.raises(AuthenticationError, match="Invalid Authorization header format"):
            await verify_cloud_task_token(authorization="BearerNoSpace")

    @pytest.mark.unit
    async def test_raises_on_invalid_bearer_format_wrong_scheme(self, mock_settings):
        """When Authorization header uses wrong scheme, raises."""
        mock_settings.cloud_run_service_url = "https://my-service.run.app"

        with pytest.raises(AuthenticationError, match="Invalid Authorization header format"):
            await verify_cloud_task_token(authorization="Basic some-creds")

    @pytest.mark.unit
    async def test_raises_on_invalid_oidc_token(self, mock_settings):
        """When token verification fails, raises AuthenticationError."""
        mock_settings.cloud_run_service_url = "https://my-service.run.app"

        with (
            patch(
                "coyo.dependencies._verify_oidc_token",
                side_effect=ValueError("Token expired"),
            ),
            pytest.raises(AuthenticationError, match="Invalid OIDC token"),
        ):
            await verify_cloud_task_token(authorization="Bearer invalid-token")

    @pytest.mark.unit
    async def test_passes_with_valid_token(self, mock_settings):
        """When token is valid, returns without error."""
        mock_settings.cloud_run_service_url = "https://my-service.run.app"

        with patch(
            "coyo.dependencies._verify_oidc_token",
            return_value=None,
        ):
            # Should not raise
            await verify_cloud_task_token(authorization="Bearer valid-token-123")

    @pytest.mark.unit
    async def test_bearer_case_insensitive(self, mock_settings):
        """Bearer prefix should be case-insensitive."""
        mock_settings.cloud_run_service_url = "https://my-service.run.app"

        with patch(
            "coyo.dependencies._verify_oidc_token",
            return_value=None,
        ):
            await verify_cloud_task_token(authorization="bearer valid-token-123")

    @pytest.mark.unit
    async def test_empty_authorization_string_raises(self, mock_settings):
        """Empty string Authorization header raises."""
        mock_settings.cloud_run_service_url = "https://my-service.run.app"

        with pytest.raises(AuthenticationError, match="Invalid Authorization header format"):
            await verify_cloud_task_token(authorization="")
