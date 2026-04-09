"""Unit tests for the MemoryExtractionService."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.conversation import Conversation
from coyo.models.conversation_summary import ConversationSummary
from coyo.models.turn import Turn
from coyo.models.user import User
from coyo.models.user_profile_attribute import UserProfileAttribute
from coyo.services.memory_extraction import (
    KeywordItem,
    MemoryExtractionResult,
    MemoryExtractionService,
    MemoryItem,
    is_semantically_same,
    trim_to_word_boundary,
)


@pytest.fixture(autouse=True)
def _mock_embedding_service() -> Generator[MagicMock, None, None]:
    """Stub ``get_embedding_service`` so tests never hit the real OpenAI API.

    ``memory_extraction`` lazily imports ``get_embedding_service`` inside
    ``_save_conversation_summary`` and ``_regenerate_interest_summaries``;
    patching the source module here covers both call sites. Returns a
    1536-dim zero vector regardless of input length.
    """
    fake_service = MagicMock()

    async def _embed(texts: list[str]) -> list[list[float]]:
        return [[0.0] * 1536 for _ in texts]

    fake_service.embed = AsyncMock(side_effect=_embed)
    with patch(
        "coyo.services.embedding.get_embedding_service",
        return_value=fake_service,
    ):
        yield fake_service

# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestIsSemanticallySame:
    """Tests for the is_semantically_same helper."""

    @pytest.mark.unit
    def test_identical_strings(self):
        assert is_semantically_same("hello", "hello") is True

    @pytest.mark.unit
    def test_case_insensitive(self):
        assert is_semantically_same("Engineer", "engineer") is True

    @pytest.mark.unit
    def test_whitespace_normalized(self):
        assert is_semantically_same("  hello  ", "hello") is True

    @pytest.mark.unit
    def test_different_values(self):
        assert is_semantically_same("hello", "world") is False

    @pytest.mark.unit
    def test_empty_strings(self):
        assert is_semantically_same("", "") is True

    @pytest.mark.unit
    def test_case_and_whitespace(self):
        assert is_semantically_same("  Software Engineer  ", "software engineer") is True


class TestTrimToWordBoundary:
    """Tests for the trim_to_word_boundary helper."""

    @pytest.mark.unit
    def test_short_text_unchanged(self):
        text = "Short text"
        assert trim_to_word_boundary(text, max_chars=200) == text

    @pytest.mark.unit
    def test_exact_length_unchanged(self):
        text = "a" * 200
        assert trim_to_word_boundary(text, max_chars=200) == text

    @pytest.mark.unit
    def test_trims_at_word_boundary(self):
        text = "Hello world this is a test"
        result = trim_to_word_boundary(text, max_chars=15)
        # "Hello world thi" -> trims at last space -> "Hello world"
        assert result == "Hello world"
        assert len(result) <= 15

    @pytest.mark.unit
    def test_no_spaces_returns_full_trimmed(self):
        text = "a" * 300
        result = trim_to_word_boundary(text, max_chars=200)
        assert result == "a" * 200

    @pytest.mark.unit
    def test_default_max_chars(self):
        # Default is 200 chars
        text = "word " * 100  # 500 chars
        result = trim_to_word_boundary(text)
        assert len(result) <= 200


# ---------------------------------------------------------------------------
# Pydantic model tests
# ---------------------------------------------------------------------------


class TestKeywordItem:
    """Tests for KeywordItem keyword normalization."""

    @pytest.mark.unit
    def test_keyword_lowercased(self):
        item = KeywordItem(keyword="Tennis", is_news_relevant=True)
        assert item.keyword == "tennis"

    @pytest.mark.unit
    def test_keyword_stripped(self):
        item = KeywordItem(keyword="  tennis  ", is_news_relevant=True)
        assert item.keyword == "tennis"

    @pytest.mark.unit
    def test_keyword_truncated_at_max_length(self):
        long_kw = "a" * 200
        item = KeywordItem(keyword=long_kw, is_news_relevant=False)
        assert len(item.keyword) == 100


class TestMemoryExtractionResult:
    """Tests for MemoryExtractionResult schema."""

    @pytest.mark.unit
    def test_default_empty_lists(self):
        result = MemoryExtractionResult(conversation_summary="test")
        assert result.memories == []
        assert result.categories == []
        assert result.entities == []

    @pytest.mark.unit
    def test_parse_valid_json(self):
        result = MemoryExtractionResult.model_validate_json(
            '{"conversation_summary": "Talked about work",'
            '"memories": [{"key": "job_industry", "value": "IT", "confidence": 0.9}],'
            '"categories": [{"keyword": "technology", "is_news_relevant": true}],'
            '"entities": []}'
        )
        assert result.conversation_summary == "Talked about work"
        assert len(result.memories) == 1
        assert result.memories[0].key == "job_industry"


# ---------------------------------------------------------------------------
# Core extraction logic tests
# ---------------------------------------------------------------------------


class TestExtractSkips:
    """Tests for idempotency and skip logic."""

    @pytest.mark.unit
    async def test_extract_skips_when_already_extracted(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should skip when memory_extracted is already True."""
        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
            memory_extracted=True,
        )
        db_session.add(conversation)
        await db_session.flush()

        await MemoryExtractionService._extract(
            db_session, conversation.id, test_user.id
        )

        # conversation_count should NOT be incremented
        await db_session.refresh(test_user)
        assert test_user.conversation_count == 0

    @pytest.mark.unit
    async def test_extract_skips_nonexistent_conversation(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should return without error for missing conversation."""
        await MemoryExtractionService._extract(
            db_session, uuid.uuid4(), test_user.id
        )

    @pytest.mark.unit
    async def test_extract_skips_user_mismatch(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should abort if conversation.user_id != provided user_id."""
        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        other_user_id = uuid.uuid4()
        await MemoryExtractionService._extract(
            db_session, conversation.id, other_user_id
        )

        await db_session.refresh(test_user)
        assert test_user.conversation_count == 0
        await db_session.refresh(conversation)
        assert conversation.memory_extracted is False

    @pytest.mark.unit
    async def test_extract_skips_empty_transcript(
        self, db_session: AsyncSession, test_user: User
    ):
        """Empty transcript should mark as extracted without calling LLM."""
        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        await MemoryExtractionService._extract(
            db_session, conversation.id, test_user.id
        )

        await db_session.refresh(conversation)
        assert conversation.memory_extracted is True
        assert conversation.interests_extracted is True
        await db_session.refresh(test_user)
        assert test_user.conversation_count == 1


class TestExtractConversationSummary:
    """Tests for conversation summary extraction."""

    @pytest.mark.unit
    async def test_extract_processes_conversation_summary(
        self, db_session: AsyncSession, test_user: User
    ):
        """Conversation summary should be saved."""
        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        turn = Turn(
            conversation_id=conversation.id,
            role="user",
            text="I work in the IT industry.",
            sequence=1,
            correction_status="none",
        )
        db_session.add(turn)
        await db_session.flush()

        mock_result = MemoryExtractionResult(
            conversation_summary="User discussed their work in IT.",
            memories=[],
            categories=[],
            entities=[],
        )

        with patch.object(
            MemoryExtractionService,
            "_call_llm",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            await MemoryExtractionService._extract(
                db_session, conversation.id, test_user.id
            )

        stmt = select(ConversationSummary).where(
            ConversationSummary.conversation_id == conversation.id
        )
        result = await db_session.execute(stmt)
        summary = result.scalar_one_or_none()
        assert summary is not None
        assert summary.summary == "User discussed their work in IT."
        assert summary.topic_title == "Free conversation"


class TestExtractMemories:
    """Tests for profile attribute processing."""

    @pytest.mark.unit
    async def test_extract_processes_memories_add(
        self, db_session: AsyncSession, test_user: User
    ):
        """New profile attribute should be added when confidence >= threshold."""
        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        turn = Turn(
            conversation_id=conversation.id,
            role="user",
            text="I work as a software engineer.",
            sequence=1,
            correction_status="none",
        )
        db_session.add(turn)
        await db_session.flush()

        mock_result = MemoryExtractionResult(
            conversation_summary="User mentioned their job.",
            memories=[
                MemoryItem(
                    key="job_industry",
                    value="Software Engineer",
                    confidence=0.9,
                )
            ],
            categories=[],
            entities=[],
        )

        with patch.object(
            MemoryExtractionService,
            "_call_llm",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            await MemoryExtractionService._extract(
                db_session, conversation.id, test_user.id
            )

        stmt = select(UserProfileAttribute).where(
            UserProfileAttribute.user_id == test_user.id,
            UserProfileAttribute.key == "job_industry",
        )
        result = await db_session.execute(stmt)
        attr = result.scalar_one_or_none()
        assert attr is not None
        assert attr.value == "Software Engineer"
        assert attr.confidence == 0.9

    @pytest.mark.unit
    async def test_extract_processes_memories_update(
        self, db_session: AsyncSession, test_user: User
    ):
        """Existing attribute should be updated when new confidence is higher."""
        # Pre-create an attribute with lower confidence
        attr = UserProfileAttribute(
            user_id=test_user.id,
            key="job_industry",
            value="IT Worker",
            confidence=0.6,
        )
        db_session.add(attr)
        await db_session.flush()

        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        turn = Turn(
            conversation_id=conversation.id,
            role="user",
            text="I am a software engineer.",
            sequence=1,
            correction_status="none",
        )
        db_session.add(turn)
        await db_session.flush()

        mock_result = MemoryExtractionResult(
            conversation_summary="User clarified their job.",
            memories=[
                MemoryItem(
                    key="job_industry",
                    value="Software Engineer",
                    confidence=0.9,
                )
            ],
            categories=[],
            entities=[],
        )

        with patch.object(
            MemoryExtractionService,
            "_call_llm",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            await MemoryExtractionService._extract(
                db_session, conversation.id, test_user.id
            )

        stmt = select(UserProfileAttribute).where(
            UserProfileAttribute.user_id == test_user.id,
            UserProfileAttribute.key == "job_industry",
        )
        result = await db_session.execute(stmt)
        updated_attr = result.scalar_one()
        assert updated_attr.value == "Software Engineer"
        assert updated_attr.confidence == 0.9

    @pytest.mark.unit
    async def test_extract_processes_memories_noop_same_value(
        self, db_session: AsyncSession, test_user: User
    ):
        """NOOP when value is semantically the same."""
        attr = UserProfileAttribute(
            user_id=test_user.id,
            key="job_industry",
            value="Software Engineer",
            confidence=0.9,
        )
        db_session.add(attr)
        await db_session.flush()

        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        turn = Turn(
            conversation_id=conversation.id,
            role="user",
            text="I work as a software engineer.",
            sequence=1,
            correction_status="none",
        )
        db_session.add(turn)
        await db_session.flush()

        mock_result = MemoryExtractionResult(
            conversation_summary="User mentioned their job again.",
            memories=[
                MemoryItem(
                    key="job_industry",
                    value="software engineer",  # Same value, different case
                    confidence=1.0,
                )
            ],
            categories=[],
            entities=[],
        )

        with patch.object(
            MemoryExtractionService,
            "_call_llm",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            await MemoryExtractionService._extract(
                db_session, conversation.id, test_user.id
            )

        stmt = select(UserProfileAttribute).where(
            UserProfileAttribute.user_id == test_user.id,
            UserProfileAttribute.key == "job_industry",
        )
        result = await db_session.execute(stmt)
        unchanged_attr = result.scalar_one()
        # Value should remain unchanged (NOOP)
        assert unchanged_attr.value == "Software Engineer"
        assert unchanged_attr.confidence == 0.9

    @pytest.mark.unit
    async def test_extract_processes_memories_noop_low_confidence(
        self, db_session: AsyncSession, test_user: User
    ):
        """NOOP when new confidence is lower than existing."""
        attr = UserProfileAttribute(
            user_id=test_user.id,
            key="job_industry",
            value="Software Engineer",
            confidence=0.9,
        )
        db_session.add(attr)
        await db_session.flush()

        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        turn = Turn(
            conversation_id=conversation.id,
            role="user",
            text="Maybe I do marketing.",
            sequence=1,
            correction_status="none",
        )
        db_session.add(turn)
        await db_session.flush()

        mock_result = MemoryExtractionResult(
            conversation_summary="User vaguely mentioned marketing.",
            memories=[
                MemoryItem(
                    key="job_industry",
                    value="Marketing",
                    confidence=0.5,
                )
            ],
            categories=[],
            entities=[],
        )

        with patch.object(
            MemoryExtractionService,
            "_call_llm",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            await MemoryExtractionService._extract(
                db_session, conversation.id, test_user.id
            )

        stmt = select(UserProfileAttribute).where(
            UserProfileAttribute.user_id == test_user.id,
            UserProfileAttribute.key == "job_industry",
        )
        result = await db_session.execute(stmt)
        unchanged_attr = result.scalar_one()
        assert unchanged_attr.value == "Software Engineer"
        assert unchanged_attr.confidence == 0.9

    @pytest.mark.unit
    async def test_extract_processes_memories_delete_negation(
        self, db_session: AsyncSession, test_user: User
    ):
        """DELETE when is_negation=True and attribute exists."""
        attr = UserProfileAttribute(
            user_id=test_user.id,
            key="family_status",
            value="Married",
            confidence=0.8,
        )
        db_session.add(attr)
        await db_session.flush()

        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        turn = Turn(
            conversation_id=conversation.id,
            role="user",
            text="Actually, I am not married.",
            sequence=1,
            correction_status="none",
        )
        db_session.add(turn)
        await db_session.flush()

        mock_result = MemoryExtractionResult(
            conversation_summary="User corrected family status.",
            memories=[
                MemoryItem(
                    key="family_status",
                    value="Not married",
                    confidence=1.0,
                    is_negation=True,
                )
            ],
            categories=[],
            entities=[],
        )

        with patch.object(
            MemoryExtractionService,
            "_call_llm",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            await MemoryExtractionService._extract(
                db_session, conversation.id, test_user.id
            )

        stmt = select(UserProfileAttribute).where(
            UserProfileAttribute.user_id == test_user.id,
            UserProfileAttribute.key == "family_status",
        )
        result = await db_session.execute(stmt)
        deleted_attr = result.scalar_one_or_none()
        assert deleted_attr is None


class TestExtractInterests:
    """Tests for interest upsert during extraction."""

    @pytest.mark.unit
    async def test_extract_upserts_interests_with_summary(
        self, db_session: AsyncSession, test_user: User
    ):
        """Interests should be upserted with summary from LLM."""
        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        turn = Turn(
            conversation_id=conversation.id,
            role="user",
            text="I love watching NBA basketball.",
            sequence=1,
            correction_status="none",
        )
        db_session.add(turn)
        await db_session.flush()

        mock_result = MemoryExtractionResult(
            conversation_summary="User discussed basketball.",
            memories=[],
            categories=[
                KeywordItem(
                    keyword="basketball",
                    is_news_relevant=True,
                    summary="User enjoys watching NBA games.",
                )
            ],
            entities=[
                KeywordItem(
                    keyword="nba",
                    is_news_relevant=True,
                    summary="User follows NBA league.",
                )
            ],
        )

        with (
            patch.object(
                MemoryExtractionService,
                "_call_llm",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch.object(
                MemoryExtractionService,
                "_upsert_interests",
                new_callable=AsyncMock,
                return_value={"basketball", "nba"},
            ) as mock_upsert,
        ):
            await MemoryExtractionService._extract(
                db_session, conversation.id, test_user.id
            )

        # Verify _upsert_interests was called with correct extraction data
        mock_upsert.assert_called_once()
        call_args = mock_upsert.call_args
        assert call_args[0][1] == test_user.id  # user_id
        extraction_arg = call_args[0][2]  # extraction result
        assert len(extraction_arg.categories) == 1
        assert extraction_arg.categories[0].keyword == "basketball"
        assert len(extraction_arg.entities) == 1
        assert extraction_arg.entities[0].keyword == "nba"


class TestExtractBatchInterval:
    """Tests for batch regeneration trigger logic."""

    @pytest.mark.unit
    async def test_extract_triggers_batch_at_interval(
        self, db_session: AsyncSession, test_user: User
    ):
        """Batch regeneration should trigger when conv_count % 5 == 0."""
        # Set conversation_count to 4, so after increment it will be 5
        test_user.conversation_count = 4
        await db_session.flush()

        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        turn = Turn(
            conversation_id=conversation.id,
            role="user",
            text="I like tennis.",
            sequence=1,
            correction_status="none",
        )
        db_session.add(turn)
        await db_session.flush()

        mock_result = MemoryExtractionResult(
            conversation_summary="User talked about tennis.",
            memories=[],
            categories=[KeywordItem(keyword="tennis", is_news_relevant=True)],
            entities=[],
        )

        with (
            patch.object(
                MemoryExtractionService,
                "_call_llm",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch.object(
                MemoryExtractionService,
                "_upsert_interests",
                new_callable=AsyncMock,
                return_value={"tennis"},
            ),
            patch.object(
                MemoryExtractionService,
                "_regenerate_interest_summaries",
                new_callable=AsyncMock,
            ) as mock_regen_interests,
            patch.object(
                MemoryExtractionService,
                "_regenerate_profile_summary",
                new_callable=AsyncMock,
            ) as mock_regen_profile,
        ):
            await MemoryExtractionService._extract(
                db_session, conversation.id, test_user.id
            )

        mock_regen_interests.assert_called_once()
        mock_regen_profile.assert_called_once()

    @pytest.mark.unit
    async def test_extract_skips_batch_when_not_interval(
        self, db_session: AsyncSession, test_user: User
    ):
        """Batch regeneration should NOT trigger when conv_count % 5 != 0."""
        # conversation_count starts at 0, after increment it will be 1
        conversation = Conversation(
            user_id=test_user.id,
            status="completed",
            time_limit_seconds=1800,
            started_at=datetime.now(UTC),
        )
        db_session.add(conversation)
        await db_session.flush()

        turn = Turn(
            conversation_id=conversation.id,
            role="user",
            text="I like tennis.",
            sequence=1,
            correction_status="none",
        )
        db_session.add(turn)
        await db_session.flush()

        mock_result = MemoryExtractionResult(
            conversation_summary="User talked about tennis.",
            memories=[],
            categories=[KeywordItem(keyword="tennis", is_news_relevant=True)],
            entities=[],
        )

        with (
            patch.object(
                MemoryExtractionService,
                "_call_llm",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch.object(
                MemoryExtractionService,
                "_upsert_interests",
                new_callable=AsyncMock,
                return_value={"tennis"},
            ),
            patch.object(
                MemoryExtractionService,
                "_regenerate_interest_summaries",
                new_callable=AsyncMock,
            ) as mock_regen_interests,
            patch.object(
                MemoryExtractionService,
                "_regenerate_profile_summary",
                new_callable=AsyncMock,
            ) as mock_regen_profile,
        ):
            await MemoryExtractionService._extract(
                db_session, conversation.id, test_user.id
            )

        mock_regen_interests.assert_not_called()
        mock_regen_profile.assert_not_called()
