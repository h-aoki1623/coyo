"""Integration tests for the history API endpoints."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from coto.models.conversation import Conversation
from coto.models.correction import CorrectionItem, TurnCorrection
from coto.models.turn import Turn
from coto.models.user import User


# ---------------------------------------------------------------------------
# Helper fixtures for history tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def multiple_conversations(
    db_session: AsyncSession,
    test_user: User,
) -> list[Conversation]:
    """Create multiple conversations for pagination testing."""
    conversations = []
    for i in range(5):
        conv = Conversation(
            user_id=test_user.id,
            topic="technology",
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime(2025, 1, 1 + i, 12, 0, 0, tzinfo=UTC),
            ended_at=datetime(2025, 1, 1 + i, 12, 15, 0, tzinfo=UTC),
            duration_seconds=900,
            total_corrections=i,
        )
        db_session.add(conv)
        conversations.append(conv)
    await db_session.commit()
    for conv in conversations:
        await db_session.refresh(conv)
    return conversations


@pytest.fixture
async def conversation_with_turns(
    db_session: AsyncSession,
    test_user: User,
) -> Conversation:
    """Create a conversation with turns and corrections for detail tests."""
    conv = Conversation(
        user_id=test_user.id,
        topic="sports",
        status="completed",
        time_limit_seconds=1800,
        started_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        ended_at=datetime(2025, 1, 1, 12, 15, 0, tzinfo=UTC),
        duration_seconds=900,
        total_corrections=1,
    )
    db_session.add(conv)
    await db_session.flush()

    user_turn = Turn(
        conversation_id=conv.id,
        role="user",
        text="I goed to the park.",
        sequence=1,
        correction_status="has_corrections",
    )
    db_session.add(user_turn)
    await db_session.flush()

    ai_turn = Turn(
        conversation_id=conv.id,
        role="ai",
        text="That sounds fun!",
        sequence=2,
        correction_status="none",
    )
    db_session.add(ai_turn)
    await db_session.flush()

    correction = TurnCorrection(
        turn_id=user_turn.id,
        corrected_text="I went to the park.",
        explanation="Past tense of 'go' is 'went'.",
    )
    db_session.add(correction)
    await db_session.flush()

    item = CorrectionItem(
        turn_correction_id=correction.id,
        user_id=test_user.id,
        original="goed",
        corrected="went",
        original_sentence="I goed to the park.",
        corrected_sentence="I went to the park.",
        type="grammar",
        explanation="Irregular verb.",
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(conv)
    return conv


# ---------------------------------------------------------------------------
# GET /api/history
# ---------------------------------------------------------------------------


class TestListHistory:
    """Tests for GET /api/history."""

    @pytest.mark.integration
    async def test_list_history_empty(self, client: AsyncClient):
        response = await client.get("/api/history")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["perPage"] == 20

    @pytest.mark.integration
    async def test_list_history_with_conversations(
        self, client: AsyncClient, multiple_conversations: list[Conversation]
    ):
        response = await client.get("/api/history")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5

    @pytest.mark.integration
    async def test_list_history_pagination_page_1(
        self, client: AsyncClient, multiple_conversations: list[Conversation]
    ):
        response = await client.get("/api/history?page=1&per_page=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["perPage"] == 2

    @pytest.mark.integration
    async def test_list_history_pagination_page_2(
        self, client: AsyncClient, multiple_conversations: list[Conversation]
    ):
        response = await client.get("/api/history?page=2&per_page=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["page"] == 2

    @pytest.mark.integration
    async def test_list_history_pagination_last_page(
        self, client: AsyncClient, multiple_conversations: list[Conversation]
    ):
        response = await client.get("/api/history?page=3&per_page=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["page"] == 3

    @pytest.mark.integration
    async def test_list_history_pagination_beyond_last_page(
        self, client: AsyncClient, multiple_conversations: list[Conversation]
    ):
        response = await client.get("/api/history?page=100&per_page=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 0
        assert data["total"] == 5

    @pytest.mark.integration
    async def test_list_history_invalid_page_returns_422(
        self, client: AsyncClient
    ):
        response = await client.get("/api/history?page=0")
        assert response.status_code == 422

    @pytest.mark.integration
    async def test_list_history_invalid_per_page_returns_422(
        self, client: AsyncClient
    ):
        response = await client.get("/api/history?per_page=0")
        assert response.status_code == 422

    @pytest.mark.integration
    async def test_list_history_per_page_over_100_returns_422(
        self, client: AsyncClient
    ):
        response = await client.get("/api/history?per_page=101")
        assert response.status_code == 422

    @pytest.mark.integration
    async def test_list_history_uses_camel_case(
        self, client: AsyncClient
    ):
        response = await client.get("/api/history")
        data = response.json()
        assert "perPage" in data
        assert "per_page" not in data

    @pytest.mark.integration
    async def test_list_history_items_use_camel_case(
        self, client: AsyncClient, test_conversation: Conversation
    ):
        response = await client.get("/api/history")
        data = response.json()
        if data["items"]:
            item = data["items"][0]
            assert "startedAt" in item
            assert "endedAt" in item
            assert "durationSeconds" in item
            assert "totalCorrections" in item

    @pytest.mark.integration
    async def test_list_history_ordered_by_most_recent(
        self, client: AsyncClient, multiple_conversations: list[Conversation]
    ):
        """Verify that history items are ordered most-recent-first."""
        response = await client.get("/api/history")
        data = response.json()
        items = data["items"]
        # Items should be in descending order of started_at
        for i in range(len(items) - 1):
            assert items[i]["startedAt"] >= items[i + 1]["startedAt"]


# ---------------------------------------------------------------------------
# GET /api/history/{conversation_id}
# ---------------------------------------------------------------------------


class TestGetHistoryDetail:
    """Tests for GET /api/history/{conversation_id}."""

    @pytest.mark.integration
    async def test_get_history_detail(
        self, client: AsyncClient, conversation_with_turns: Conversation
    ):
        response = await client.get(
            f"/api/history/{conversation_with_turns.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(conversation_with_turns.id)
        assert data["topic"] == "sports"
        assert data["status"] == "completed"

    @pytest.mark.integration
    async def test_get_history_detail_includes_turns(
        self, client: AsyncClient, conversation_with_turns: Conversation
    ):
        response = await client.get(
            f"/api/history/{conversation_with_turns.id}"
        )
        data = response.json()
        assert len(data["turns"]) == 2
        # Verify turn ordering by sequence
        assert data["turns"][0]["sequence"] == 1
        assert data["turns"][1]["sequence"] == 2
        assert data["turns"][0]["role"] == "user"
        assert data["turns"][1]["role"] == "ai"

    @pytest.mark.integration
    async def test_get_history_detail_includes_corrections(
        self, client: AsyncClient, conversation_with_turns: Conversation
    ):
        response = await client.get(
            f"/api/history/{conversation_with_turns.id}"
        )
        data = response.json()
        assert len(data["corrections"]) == 1
        correction = data["corrections"][0]
        assert correction["correctedText"] == "I went to the park."
        assert len(correction["items"]) == 1

    @pytest.mark.integration
    async def test_get_history_detail_nonexistent_returns_404(
        self, client: AsyncClient
    ):
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/history/{fake_id}")
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "NOT_FOUND"

    @pytest.mark.integration
    async def test_get_history_detail_invalid_uuid_returns_422(
        self, client: AsyncClient
    ):
        response = await client.get("/api/history/not-a-uuid")
        assert response.status_code == 422

    @pytest.mark.integration
    async def test_get_history_detail_uses_camel_case(
        self, client: AsyncClient, conversation_with_turns: Conversation
    ):
        response = await client.get(
            f"/api/history/{conversation_with_turns.id}"
        )
        data = response.json()
        assert "durationSeconds" in data
        assert "timeLimitSeconds" in data
        assert "startedAt" in data
        assert "totalCorrections" in data
        if data["turns"]:
            turn = data["turns"][0]
            assert "conversationId" in turn
            assert "correctionStatus" in turn
            assert "createdAt" in turn


# ---------------------------------------------------------------------------
# DELETE /api/history/{conversation_id}
# ---------------------------------------------------------------------------


class TestDeleteHistory:
    """Tests for DELETE /api/history/{conversation_id}."""

    @pytest.mark.integration
    async def test_delete_existing_conversation_returns_204(
        self, client: AsyncClient, test_conversation: Conversation
    ):
        response = await client.delete(
            f"/api/history/{test_conversation.id}"
        )
        assert response.status_code == 204

    @pytest.mark.integration
    async def test_delete_conversation_is_removed(
        self, client: AsyncClient, test_conversation: Conversation
    ):
        # Delete
        response = await client.delete(
            f"/api/history/{test_conversation.id}"
        )
        assert response.status_code == 204

        # Verify it no longer appears in the list
        list_response = await client.get("/api/history")
        data = list_response.json()
        ids = [item["id"] for item in data["items"]]
        assert str(test_conversation.id) not in ids

    @pytest.mark.integration
    async def test_delete_nonexistent_conversation_returns_404(
        self, client: AsyncClient
    ):
        fake_id = uuid.uuid4()
        response = await client.delete(f"/api/history/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.integration
    async def test_delete_invalid_uuid_returns_422(self, client: AsyncClient):
        response = await client.delete("/api/history/not-a-uuid")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/history/batch-delete
# ---------------------------------------------------------------------------


class TestBatchDeleteHistory:
    """Tests for POST /api/history/batch-delete."""

    @pytest.mark.integration
    async def test_batch_delete_returns_204(
        self,
        client: AsyncClient,
        multiple_conversations: list[Conversation],
    ):
        ids = [str(c.id) for c in multiple_conversations[:2]]
        response = await client.post(
            "/api/history/batch-delete",
            json={"ids": ids},
        )
        assert response.status_code == 204

    @pytest.mark.integration
    async def test_batch_delete_removes_conversations(
        self,
        client: AsyncClient,
        multiple_conversations: list[Conversation],
    ):
        ids_to_delete = [str(c.id) for c in multiple_conversations[:3]]
        await client.post(
            "/api/history/batch-delete",
            json={"ids": ids_to_delete},
        )

        # Verify remaining conversations
        list_response = await client.get("/api/history")
        data = list_response.json()
        assert data["total"] == 2

    @pytest.mark.integration
    async def test_batch_delete_nonexistent_ids_still_returns_204(
        self, client: AsyncClient
    ):
        """Batch delete with nonexistent IDs should not error."""
        ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        response = await client.post(
            "/api/history/batch-delete",
            json={"ids": ids},
        )
        assert response.status_code == 204

    @pytest.mark.integration
    async def test_batch_delete_empty_ids_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/api/history/batch-delete",
            json={"ids": []},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    async def test_batch_delete_missing_ids_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/api/history/batch-delete",
            json={},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    async def test_batch_delete_over_100_ids_returns_422(self, client: AsyncClient):
        ids = [str(uuid.uuid4()) for _ in range(101)]
        response = await client.post(
            "/api/history/batch-delete",
            json={"ids": ids},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    async def test_batch_delete_invalid_uuid_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/api/history/batch-delete",
            json={"ids": ["not-a-uuid"]},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    async def test_batch_delete_single_id(
        self,
        client: AsyncClient,
        test_conversation: Conversation,
    ):
        response = await client.post(
            "/api/history/batch-delete",
            json={"ids": [str(test_conversation.id)]},
        )
        assert response.status_code == 204

    @pytest.mark.integration
    async def test_batch_delete_max_100_ids(self, client: AsyncClient):
        """Verify that exactly 100 IDs is accepted."""
        ids = [str(uuid.uuid4()) for _ in range(100)]
        response = await client.post(
            "/api/history/batch-delete",
            json={"ids": ids},
        )
        assert response.status_code == 204
