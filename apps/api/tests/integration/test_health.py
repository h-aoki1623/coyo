"""Integration tests for the health check endpoint."""

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """Tests for GET /health."""

    @pytest.mark.integration
    async def test_health_check_returns_200(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.integration
    async def test_health_check_returns_ok_status(self, client: AsyncClient):
        response = await client.get("/health")
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.integration
    async def test_health_check_response_structure(self, client: AsyncClient):
        response = await client.get("/health")
        data = response.json()
        assert "status" in data
        assert len(data) == 1
