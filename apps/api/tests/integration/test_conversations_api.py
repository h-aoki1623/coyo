"""Integration tests for the conversations API endpoints."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from coto.models.conversation import Conversation
from coto.models.correction import CorrectionItem, TurnCorrection
from coto.models.turn import Turn
from coto.models.user import User


# ---------------------------------------------------------------------------
# POST /api/conversations
# ---------------------------------------------------------------------------


class TestCreateConversation:
    """Tests for POST /api/conversations."""

    @pytest.mark.integration
    async def test_create_conversation_returns_201(self, client: AsyncClient):
        response = await client.post(
            "/api/conversations",
            json={"topic": "technology"},
        )
        assert response.status_code == 201

    @pytest.mark.integration
    async def test_create_conversation_response_body(self, client: AsyncClient):
        response = await client.post(
            "/api/conversations",
            json={"topic": "technology"},
        )
        data = response.json()
        assert data["topic"] == "technology"
        assert data["status"] == "active"
        assert data["durationSeconds"] is None
        assert data["endedAt"] is None
        assert data["totalCorrections"] == 0
        assert "id" in data
        assert "timeLimitSeconds" in data
        assert "startedAt" in data

    @pytest.mark.integration
    async def test_create_conversation_all_valid_topics(self, client: AsyncClient):
        for topic in ["sports", "business", "technology", "politics", "entertainment"]:
            response = await client.post(
                "/api/conversations",
                json={"topic": topic},
            )
            assert response.status_code == 201
            assert response.json()["topic"] == topic

    @pytest.mark.integration
    async def test_create_conversation_invalid_topic_returns_422(
        self, client: AsyncClient
    ):
        response = await client.post(
            "/api/conversations",
            json={"topic": "cooking"},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    async def test_create_conversation_missing_topic_returns_422(
        self, client: AsyncClient
    ):
        response = await client.post(
            "/api/conversations",
            json={},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    async def test_create_conversation_empty_body_returns_422(
        self, client: AsyncClient
    ):
        response = await client.post(
            "/api/conversations",
            content=b"",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    async def test_create_conversation_uses_camel_case(self, client: AsyncClient):
        """Verify that the response uses camelCase keys."""
        response = await client.post(
            "/api/conversations",
            json={"topic": "technology"},
        )
        data = response.json()
        # snake_case keys should NOT appear
        assert "duration_seconds" not in data
        assert "time_limit_seconds" not in data
        assert "started_at" not in data
        assert "ended_at" not in data
        assert "total_corrections" not in data
        # camelCase keys SHOULD appear
        assert "durationSeconds" in data
        assert "timeLimitSeconds" in data
        assert "startedAt" in data
        assert "endedAt" in data
        assert "totalCorrections" in data


# ---------------------------------------------------------------------------
# GET /api/conversations/{conversation_id}
# ---------------------------------------------------------------------------


class TestGetConversation:
    """Tests for GET /api/conversations/{conversation_id}."""

    @pytest.mark.integration
    async def test_get_existing_conversation(
        self, client: AsyncClient, test_conversation: Conversation
    ):
        response = await client.get(f"/api/conversations/{test_conversation.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_conversation.id)
        assert data["topic"] == "technology"
        assert data["status"] == "active"

    @pytest.mark.integration
    async def test_get_nonexistent_conversation_returns_404(
        self, client: AsyncClient
    ):
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/conversations/{fake_id}")
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "NOT_FOUND"

    @pytest.mark.integration
    async def test_get_conversation_invalid_uuid_returns_422(
        self, client: AsyncClient
    ):
        response = await client.get("/api/conversations/not-a-uuid")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/conversations/{conversation_id}/end
# ---------------------------------------------------------------------------


class TestEndConversation:
    """Tests for POST /api/conversations/{conversation_id}/end."""

    @pytest.mark.integration
    async def test_end_active_conversation(
        self, client: AsyncClient, test_conversation: Conversation
    ):
        response = await client.post(
            f"/api/conversations/{test_conversation.id}/end"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["endedAt"] is not None
        assert data["durationSeconds"] is not None

    @pytest.mark.integration
    async def test_end_completed_conversation_returns_409(
        self,
        client: AsyncClient,
        completed_conversation: Conversation,
    ):
        response = await client.post(
            f"/api/conversations/{completed_conversation.id}/end"
        )
        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "INVALID_STATE"

    @pytest.mark.integration
    async def test_end_paused_conversation_succeeds(
        self, client: AsyncClient, paused_conversation: Conversation
    ):
        response = await client.post(
            f"/api/conversations/{paused_conversation.id}/end"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    @pytest.mark.integration
    async def test_end_nonexistent_conversation_returns_404(
        self, client: AsyncClient
    ):
        fake_id = uuid.uuid4()
        response = await client.post(f"/api/conversations/{fake_id}/end")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/conversations/{conversation_id}/resume
# ---------------------------------------------------------------------------


class TestResumeConversation:
    """Tests for POST /api/conversations/{conversation_id}/resume."""

    @pytest.mark.integration
    async def test_resume_paused_conversation(
        self, client: AsyncClient, paused_conversation: Conversation
    ):
        response = await client.post(
            f"/api/conversations/{paused_conversation.id}/resume"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"

    @pytest.mark.integration
    async def test_resume_active_conversation_returns_409(
        self, client: AsyncClient, test_conversation: Conversation
    ):
        response = await client.post(
            f"/api/conversations/{test_conversation.id}/resume"
        )
        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "INVALID_STATE"

    @pytest.mark.integration
    async def test_resume_completed_conversation_returns_409(
        self, client: AsyncClient, completed_conversation: Conversation
    ):
        response = await client.post(
            f"/api/conversations/{completed_conversation.id}/resume"
        )
        assert response.status_code == 409

    @pytest.mark.integration
    async def test_resume_nonexistent_conversation_returns_404(
        self, client: AsyncClient
    ):
        fake_id = uuid.uuid4()
        response = await client.post(f"/api/conversations/{fake_id}/resume")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/conversations/{conversation_id}/feedback
# ---------------------------------------------------------------------------


class TestGetFeedback:
    """Tests for GET /api/conversations/{conversation_id}/feedback."""

    @pytest.mark.integration
    async def test_get_feedback_with_corrections(
        self,
        client: AsyncClient,
        test_conversation: Conversation,
        test_turn: Turn,
        test_correction: TurnCorrection,
    ):
        response = await client.get(
            f"/api/conversations/{test_conversation.id}/feedback"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["totalTurns"] == 1
        assert data["totalCorrections"] == 1
        assert data["totalClean"] == 0
        assert len(data["corrections"]) == 1

    @pytest.mark.integration
    async def test_get_feedback_correction_details(
        self,
        client: AsyncClient,
        test_conversation: Conversation,
        test_turn: Turn,
        test_correction: TurnCorrection,
    ):
        response = await client.get(
            f"/api/conversations/{test_conversation.id}/feedback"
        )
        data = response.json()
        correction = data["corrections"][0]
        assert "correctedText" in correction
        assert "explanation" in correction
        assert "items" in correction
        assert "turnId" in correction
        assert len(correction["items"]) >= 1

    @pytest.mark.integration
    async def test_get_feedback_no_corrections(
        self, client: AsyncClient, test_conversation: Conversation
    ):
        response = await client.get(
            f"/api/conversations/{test_conversation.id}/feedback"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["totalTurns"] == 0
        assert data["totalCorrections"] == 0
        assert data["totalClean"] == 0
        assert data["corrections"] == []

    @pytest.mark.integration
    async def test_get_feedback_nonexistent_conversation_returns_404(
        self, client: AsyncClient
    ):
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/conversations/{fake_id}/feedback")
        assert response.status_code == 404

    @pytest.mark.integration
    async def test_get_feedback_uses_camel_case(
        self, client: AsyncClient, test_conversation: Conversation
    ):
        response = await client.get(
            f"/api/conversations/{test_conversation.id}/feedback"
        )
        data = response.json()
        assert "totalTurns" in data
        assert "totalCorrections" in data
        assert "totalClean" in data
        assert "total_turns" not in data
        assert "total_corrections" not in data
        assert "total_clean" not in data
