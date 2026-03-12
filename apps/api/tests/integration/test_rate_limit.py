"""Integration tests for rate limiting on API endpoints."""

import pytest
from httpx import AsyncClient

from coyo.rate_limit import limiter


@pytest.fixture(autouse=True)
def _reset_limiter():
    """Reset the in-memory rate limiter storage between tests.

    Without this, rate limit counters from one test leak into the next,
    causing false failures since all tests share the same client IP.
    """
    limiter.reset()
    yield
    limiter.reset()


# ---------------------------------------------------------------------------
# Auth endpoints — 10/minute
# ---------------------------------------------------------------------------


class TestAuthSessionRateLimit:
    """Tests for rate limiting on POST /api/auth/session (10/minute)."""

    @pytest.mark.integration
    async def test_auth_session_allows_requests_within_limit(self, client: AsyncClient):
        for _ in range(10):
            response = await client.post("/api/auth/session")
            assert response.status_code == 200

    @pytest.mark.integration
    async def test_auth_session_returns_429_after_exceeding_limit(self, client: AsyncClient):
        # Exhaust the 10/minute limit
        for _ in range(10):
            await client.post("/api/auth/session")

        # The 11th request should be rate limited
        response = await client.post("/api/auth/session")
        assert response.status_code == 429

    @pytest.mark.integration
    async def test_auth_session_429_has_error_envelope(self, client: AsyncClient):
        for _ in range(10):
            await client.post("/api/auth/session")

        response = await client.post("/api/auth/session")
        data = response.json()

        assert "error" in data
        assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert data["error"]["message"] == "Rate limit exceeded"

    @pytest.mark.integration
    async def test_auth_session_429_has_retry_after_header(self, client: AsyncClient):
        for _ in range(10):
            await client.post("/api/auth/session")

        response = await client.post("/api/auth/session")

        assert response.headers["retry-after"] == "60"


class TestAuthAppRedirectRateLimit:
    """Tests for rate limiting on GET /api/auth/app-redirect (10/minute)."""

    @pytest.mark.integration
    async def test_app_redirect_allows_requests_within_limit(self, client: AsyncClient):
        for _ in range(10):
            response = await client.get("/api/auth/app-redirect")
            assert response.status_code == 200

    @pytest.mark.integration
    async def test_app_redirect_returns_429_after_exceeding_limit(self, client: AsyncClient):
        for _ in range(10):
            await client.get("/api/auth/app-redirect")

        response = await client.get("/api/auth/app-redirect")
        assert response.status_code == 429


# ---------------------------------------------------------------------------
# Conversation endpoints — 30/minute
# ---------------------------------------------------------------------------


class TestConversationRateLimit:
    """Tests for rate limiting on POST /api/conversations (30/minute)."""

    @pytest.mark.integration
    async def test_create_conversation_allows_requests_within_limit(
        self, client: AsyncClient
    ):
        for _ in range(30):
            response = await client.post(
                "/api/conversations",
                json={"topic": "technology"},
            )
            assert response.status_code == 201

    @pytest.mark.integration
    async def test_create_conversation_returns_429_after_exceeding_limit(
        self, client: AsyncClient
    ):
        for _ in range(30):
            await client.post(
                "/api/conversations",
                json={"topic": "technology"},
            )

        response = await client.post(
            "/api/conversations",
            json={"topic": "technology"},
        )
        assert response.status_code == 429

    @pytest.mark.integration
    async def test_create_conversation_429_has_error_envelope(self, client: AsyncClient):
        for _ in range(30):
            await client.post(
                "/api/conversations",
                json={"topic": "technology"},
            )

        response = await client.post(
            "/api/conversations",
            json={"topic": "technology"},
        )
        data = response.json()

        assert "error" in data
        assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert data["error"]["message"] == "Rate limit exceeded"


# ---------------------------------------------------------------------------
# History endpoints — 30/minute
# ---------------------------------------------------------------------------


class TestHistoryRateLimit:
    """Tests for rate limiting on GET /api/history (30/minute)."""

    @pytest.mark.integration
    async def test_list_history_allows_requests_within_limit(self, client: AsyncClient):
        for _ in range(30):
            response = await client.get("/api/history")
            assert response.status_code == 200

    @pytest.mark.integration
    async def test_list_history_returns_429_after_exceeding_limit(self, client: AsyncClient):
        for _ in range(30):
            await client.get("/api/history")

        response = await client.get("/api/history")
        assert response.status_code == 429

    @pytest.mark.integration
    async def test_list_history_429_has_retry_after_header(self, client: AsyncClient):
        for _ in range(30):
            await client.get("/api/history")

        response = await client.get("/api/history")

        assert response.headers["retry-after"] == "60"


# ---------------------------------------------------------------------------
# Cross-endpoint isolation
# ---------------------------------------------------------------------------


class TestRateLimitIsolation:
    """Tests that rate limits are tracked per-endpoint, not globally."""

    @pytest.mark.integration
    async def test_different_endpoints_have_separate_limits(self, client: AsyncClient):
        """Hitting one endpoint's limit should not affect another endpoint."""
        # Exhaust auth session limit (10/minute)
        for _ in range(10):
            await client.post("/api/auth/session")

        # Auth should be rate limited
        auth_response = await client.post("/api/auth/session")
        assert auth_response.status_code == 429

        # History should still work (separate limit)
        history_response = await client.get("/api/history")
        assert history_response.status_code == 200
