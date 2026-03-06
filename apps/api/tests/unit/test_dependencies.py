"""Unit tests for FastAPI dependency injection providers."""

import pytest
from httpx import AsyncClient


class TestGetDeviceIdDependency:
    """Tests for the get_device_id dependency via API integration."""

    @pytest.mark.unit
    async def test_missing_device_id_header_returns_422(self, engine, db_session):
        """Verify that missing X-Device-Id header returns 422.

        This test uses a fresh client without the get_current_user override
        to test the real dependency chain.
        """
        from httpx import ASGITransport, AsyncClient as AC

        from coyo.dependencies import get_db
        from coyo.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        # Do NOT override get_current_user, so get_device_id is actually called

        try:
            transport = ASGITransport(app=app)
            async with AC(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/history")
                assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.unit
    async def test_device_id_header_creates_user(self, engine, db_session):
        """Verify that providing a valid UUID X-Device-Id creates a user and succeeds."""
        from httpx import ASGITransport, AsyncClient as AC

        from coyo.dependencies import get_db
        from coyo.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            transport = ASGITransport(app=app)
            async with AC(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/history",
                    headers={"X-Device-Id": "11111111-1111-4111-a111-111111111111"},
                )
                assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.unit
    async def test_invalid_device_id_returns_422(self, engine, db_session):
        """Verify that an invalid (non-UUID) X-Device-Id returns 422."""
        from httpx import ASGITransport, AsyncClient as AC

        from coyo.dependencies import get_db
        from coyo.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            transport = ASGITransport(app=app)
            async with AC(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/history",
                    headers={"X-Device-Id": "not-a-valid-uuid"},
                )
                assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()
