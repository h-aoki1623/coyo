"""Integration tests for error handling middleware and exception handlers."""

import uuid

import pytest
from httpx import AsyncClient


class TestErrorResponseFormat:
    """Tests for the consistent error response envelope."""

    @pytest.mark.integration
    async def test_not_found_error_format(self, client: AsyncClient):
        """Verify that NotFoundError returns the correct JSON envelope."""
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/conversations/{fake_id}")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert data["error"]["code"] == "NOT_FOUND"

    @pytest.mark.integration
    async def test_validation_error_from_pydantic(self, client: AsyncClient):
        """Verify that Pydantic validation errors return 422."""
        response = await client.post(
            "/api/conversations",
            json={"topic": "invalid_topic"},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    async def test_state_error_format(self, client: AsyncClient, completed_conversation):
        """Verify that ConversationStateError returns the correct JSON envelope."""
        response = await client.post(
            f"/api/conversations/{completed_conversation.id}/end"
        )
        assert response.status_code == 409
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "INVALID_STATE"
        assert "message" in data["error"]


class TestRequestIdMiddleware:
    """Tests for the X-Request-Id middleware."""

    @pytest.mark.integration
    async def test_response_includes_request_id(self, client: AsyncClient):
        """Verify that every response includes an X-Request-Id header."""
        response = await client.get("/health")
        assert "x-request-id" in response.headers

    @pytest.mark.integration
    async def test_custom_request_id_is_echoed(self, client: AsyncClient):
        """Verify that a client-provided X-Request-Id is echoed back."""
        custom_id = "my-custom-request-id-12345"
        response = await client.get(
            "/health",
            headers={"x-request-id": custom_id},
        )
        assert response.headers["x-request-id"] == custom_id

    @pytest.mark.integration
    async def test_generated_request_id_is_uuid_like(self, client: AsyncClient):
        """Verify that auto-generated request IDs look like UUIDs."""
        response = await client.get("/health")
        request_id = response.headers["x-request-id"]
        # UUID format: 8-4-4-4-12 hex chars
        assert len(request_id) == 36
        parts = request_id.split("-")
        assert len(parts) == 5


class TestCORSMiddleware:
    """Tests for CORS middleware configuration."""

    @pytest.mark.integration
    async def test_cors_allows_configured_origin(self, client: AsyncClient):
        """Verify that CORS allows configured origins."""
        response = await client.options(
            "/health",
            headers={
                "origin": "http://localhost:8081",
                "access-control-request-method": "GET",
            },
        )
        # OPTIONS preflight should succeed
        assert response.status_code in (200, 204)
