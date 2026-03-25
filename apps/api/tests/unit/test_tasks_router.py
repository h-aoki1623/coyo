"""Unit tests for the tasks router (Cloud Tasks callback endpoint)."""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.user import User


@pytest.fixture
async def tasks_client(
    db_session: AsyncSession,
    test_user: User,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client with verify_cloud_task_token overridden.

    The standard ``client`` fixture does not override verify_cloud_task_token,
    so this fixture adds that override to allow unauthenticated test requests
    to the /api/tasks/* endpoints.
    """
    from coyo.dependencies import get_current_user, get_db, verify_cloud_task_token
    from coyo.main import app

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return test_user

    async def override_verify_cloud_task_token():
        return None

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[verify_cloud_task_token] = override_verify_cloud_task_token

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


class TestExtractMemoryEndpoint:
    """Tests for POST /api/tasks/extract-memory."""

    @pytest.mark.unit
    async def test_extract_memory_success(self, tasks_client: AsyncClient):
        """POST with valid body returns 200 {"status": "ok"}."""
        conv_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        with patch(
            "coyo.routers.tasks.MemoryExtractionService.extract",
            new_callable=AsyncMock,
        ):
            response = await tasks_client.post(
                "/api/tasks/extract-memory",
                json={"conversation_id": conv_id, "user_id": user_id},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.unit
    async def test_extract_memory_calls_extract(self, tasks_client: AsyncClient):
        """Verify it calls MemoryExtractionService.extract with correct args."""
        conv_id = uuid.uuid4()
        user_id = uuid.uuid4()

        with patch(
            "coyo.routers.tasks.MemoryExtractionService.extract",
            new_callable=AsyncMock,
        ) as mock_extract:
            await tasks_client.post(
                "/api/tasks/extract-memory",
                json={"conversation_id": str(conv_id), "user_id": str(user_id)},
            )

        mock_extract.assert_called_once_with(conv_id, user_id)

    @pytest.mark.unit
    async def test_extract_memory_invalid_body_missing_fields(
        self, tasks_client: AsyncClient
    ):
        """Missing required fields returns 422."""
        response = await tasks_client.post(
            "/api/tasks/extract-memory",
            json={},
        )
        assert response.status_code == 422

    @pytest.mark.unit
    async def test_extract_memory_invalid_body_bad_uuid(
        self, tasks_client: AsyncClient
    ):
        """Invalid UUID format returns 422."""
        response = await tasks_client.post(
            "/api/tasks/extract-memory",
            json={"conversation_id": "not-a-uuid", "user_id": "also-bad"},
        )
        assert response.status_code == 422

    @pytest.mark.unit
    async def test_extract_memory_propagates_errors(
        self, tasks_client: AsyncClient
    ):
        """When extract() raises, the error results in a 500 response.

        The unhandled_error_handler in middleware catches non-CoyoError exceptions
        and returns a 500 JSON response. In some Starlette/middleware configurations
        the exception may propagate through the ASGI transport instead.
        """
        conv_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        with patch(
            "coyo.routers.tasks.MemoryExtractionService.extract",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM timeout"),
        ):
            try:
                response = await tasks_client.post(
                    "/api/tasks/extract-memory",
                    json={"conversation_id": conv_id, "user_id": user_id},
                )
                # If the middleware catches it, we get a 500
                assert response.status_code == 500
            except RuntimeError:
                # If the exception propagates through the ASGI transport,
                # that also confirms the error is not silently swallowed
                pass
