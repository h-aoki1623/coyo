"""Unit tests for middleware error handlers — client message sanitization."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coyo.exceptions import (
    AuthenticationError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)
from coyo.middleware import setup_middleware


def _create_app() -> FastAPI:
    """Create a minimal FastAPI app with error handlers for testing."""
    app = FastAPI()

    @app.get("/not-found")
    async def _raise_not_found() -> None:
        raise NotFoundError("Conversation", "secret-uuid-123")

    @app.get("/external-error")
    async def _raise_external() -> None:
        raise ExternalServiceError("OpenAI", "rate limit exceeded for org-abc")

    @app.get("/validation-error")
    async def _raise_validation() -> None:
        raise ValidationError("Invalid email format")

    @app.get("/auth-error")
    async def _raise_auth() -> None:
        raise AuthenticationError("Firebase token expired")

    setup_middleware(app)
    return app


@pytest.fixture
def app() -> FastAPI:
    return _create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestErrorResponseSanitization:
    """Verify that error responses do not leak internal details."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_not_found_error_hides_resource_id(self, client: AsyncClient):
        resp = await client.get("/not-found")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "NOT_FOUND"
        assert "secret-uuid-123" not in body["error"]["message"]
        assert "Conversation" not in body["error"]["message"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_external_service_error_hides_service_details(
        self, client: AsyncClient
    ):
        resp = await client.get("/external-error")
        assert resp.status_code == 502
        body = resp.json()
        assert body["error"]["code"] == "EXTERNAL_ERROR"
        assert "OpenAI" not in body["error"]["message"]
        assert "rate limit" not in body["error"]["message"]
        assert "org-abc" not in body["error"]["message"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validation_error_preserves_message(self, client: AsyncClient):
        resp = await client.get("/validation-error")
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["message"] == "Invalid email format"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_auth_error_hides_firebase_details(self, client: AsyncClient):
        resp = await client.get("/auth-error")
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"]["code"] == "AUTHENTICATION_ERROR"
        assert "Firebase" not in body["error"]["message"]
        assert body["error"]["message"] == "Authentication required"
