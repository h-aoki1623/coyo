"""Unit tests for the auth router (POST /api/auth/session)."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.services.firebase import FirebaseTokenPayload


def _firebase_payload(
    uid: str = "fb-test-uid",
    email: str = "user@test.com",
    display_name: str = "Test User",
    sign_in_provider: str = "password",
) -> FirebaseTokenPayload:
    return FirebaseTokenPayload(
        uid=uid,
        email=email,
        email_verified=True,
        display_name=display_name,
        sign_in_provider=sign_in_provider,
    )


@pytest.fixture
async def auth_client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client that does NOT override get_current_user.

    Only overrides get_db so the auth dependency chain is tested end-to-end.
    """
    from coyo.dependencies import get_db
    from coyo.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


class TestSessionEndpoint:
    """Tests for POST /api/auth/session."""

    @pytest.mark.unit
    async def test_create_session_success(
        self,
        auth_client: AsyncClient,
    ):
        payload = _firebase_payload()

        with patch(
            "coyo.dependencies.verify_firebase_token",
            return_value=payload,
        ):
            response = await auth_client.post(
                "/api/auth/session",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "userId" in data
        assert data["email"] == "user@test.com"
        assert data["displayName"] == "Test User"
        assert data["authProvider"] == "email"

    @pytest.mark.unit
    async def test_create_session_no_token_returns_401(
        self,
        auth_client: AsyncClient,
    ):
        response = await auth_client.post("/api/auth/session")

        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "AUTHENTICATION_ERROR"

    @pytest.mark.unit
    async def test_create_session_invalid_bearer_returns_401(
        self,
        auth_client: AsyncClient,
    ):
        response = await auth_client.post(
            "/api/auth/session",
            headers={"Authorization": "InvalidFormat"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "AUTHENTICATION_ERROR"
