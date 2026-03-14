"""Unit tests for the FastAPI application lifespan."""

from unittest.mock import MagicMock, patch

import pytest


class TestLifespanFirebaseGuard:
    """Tests for Firebase initialization guards in the lifespan function."""

    @pytest.mark.unit
    async def test_production_without_firebase_project_id_raises(self):
        """Production must have FIREBASE_PROJECT_ID set."""
        mock_settings = MagicMock()
        mock_settings.firebase_project_id = None

        with (
            patch("coyo.main._is_prod", new=True),
            patch("coyo.config.get_settings", return_value=mock_settings),
            pytest.raises(RuntimeError, match="FIREBASE_PROJECT_ID must be set in production"),
        ):
            from coyo.main import app, lifespan

            async with lifespan(app):
                pass

    @pytest.mark.unit
    async def test_non_production_without_firebase_project_id_succeeds(self):
        """Non-production environments can run without FIREBASE_PROJECT_ID."""
        mock_settings = MagicMock()
        mock_settings.firebase_project_id = None

        with (
            patch("coyo.main._is_prod", new=False),
            patch("coyo.config.get_settings", return_value=mock_settings),
        ):
            from coyo.main import app, lifespan

            async with lifespan(app):
                pass

    @pytest.mark.unit
    async def test_production_with_firebase_project_id_calls_initialize(self):
        """Production with FIREBASE_PROJECT_ID calls initialize_firebase."""
        mock_settings = MagicMock()
        mock_settings.firebase_project_id = "test-project"
        mock_settings.firebase_service_account_path = "/path/to/sa.json"

        with (
            patch("coyo.main._is_prod", new=True),
            patch("coyo.config.get_settings", return_value=mock_settings),
            patch("coyo.services.firebase.initialize_firebase") as mock_init,
        ):
            from coyo.main import app, lifespan

            async with lifespan(app):
                pass

            mock_init.assert_called_once_with(
                "test-project",
                service_account_path="/path/to/sa.json",
                fail_on_error=True,
            )
