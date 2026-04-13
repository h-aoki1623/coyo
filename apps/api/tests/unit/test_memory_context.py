"""Unit tests for the MemoryContextService."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.conversation_summary import ConversationSummary
from coyo.models.user import User
from coyo.models.user_attribute import UserAttribute
from coyo.models.user_profile_summary import UserProfileSummary
from coyo.repositories.conversation_summary import (
    ConversationSummaryEmbeddingRow,
)
from coyo.repositories.interest import (
    InterestEmbeddingRow,
    InterestWithWeight,
)
from coyo.services.memory_context import (
    MemoryContextService,
    _format_memory_block,
    _min_max_normalize,
    _rank_interests,
    _rank_summaries,
)
from coyo.services.theme_context import ThemeContext

# ---------------------------------------------------------------------------
# MemoryContextService.build_context tests
# ---------------------------------------------------------------------------


class TestBuildContext:
    """Tests for MemoryContextService.build_context."""

    @pytest.fixture(autouse=True)
    def mock_memory_context(self):
        """Override the global autouse mock to allow real build_context calls."""
        yield  # no-op — disables the conftest autouse mock for this class

    @pytest.mark.unit
    async def test_build_context_returns_none_for_missing_user(self, db_session: AsyncSession):
        """Should return None when user does not exist."""
        result = await MemoryContextService.build_context(db_session, uuid.uuid4())
        assert result is None

    @pytest.mark.unit
    async def test_build_context_returns_none_for_empty_memory(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should return None when user exists but has no memory data."""
        result = await MemoryContextService.build_context(db_session, test_user.id)
        assert result is None

    @pytest.mark.unit
    async def test_build_context_formats_full_memory(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should return formatted block when all sections are present."""
        # Create profile summary
        profile_summary = UserProfileSummary(
            user_id=test_user.id,
            summary="This user is a software engineer who enjoys tennis.",
            conversation_count_at_update=5,
        )
        db_session.add(profile_summary)

        # Create profile attribute
        attr = UserAttribute(
            user_id=test_user.id,
            key="job_industry",
            value="Software Engineer",
            confidence=0.9,
        )
        db_session.add(attr)
        await db_session.flush()

        # Mock interest repository since it uses computed weights
        mock_interests = [
            InterestWithWeight(
                keyword="tennis",
                keyword_type="category",
                is_news_relevant=True,
                total_mentions=3,
                effective_weight=1.5,
                last_mentioned_conv_idx=5,
                summary="User plays tennis on weekends.",
            ),
        ]

        # Mock conversation summary repository
        mock_conv_summary = MagicMock(spec=ConversationSummary)
        mock_conv_summary.created_at = datetime(2025, 3, 1, tzinfo=UTC)
        mock_conv_summary.source_keyword = "tennis"
        mock_conv_summary.topic_title = "Weekend Activities"
        mock_conv_summary.summary = "Discussed playing tennis."

        with (
            patch("coyo.services.memory_context.InterestRepository") as MockInterestRepo,
            patch(
                "coyo.services.memory_context.ConversationSummaryRepository"
            ) as MockConvSummaryRepo,
        ):
            mock_interest_inst = MockInterestRepo.return_value
            mock_interest_inst.get_top_interests = AsyncMock(return_value=mock_interests)

            mock_conv_inst = MockConvSummaryRepo.return_value
            mock_conv_inst.get_latest_for_user = AsyncMock(return_value=[mock_conv_summary])

            result = await MemoryContextService.build_context(db_session, test_user.id)

        assert result is not None
        assert "[WHAT YOU KNOW ABOUT THIS USER]" in result
        assert "User Profile" in result
        assert "software engineer" in result.lower()
        assert "tennis" in result.lower()
        assert "Background" in result
        assert "job_industry" in result
        assert "Recent Conversations" in result

    @pytest.mark.unit
    async def test_build_context_theme_path_uses_embeddings_repo(
        self, db_session: AsyncSession, test_user: User
    ):
        """When theme has an embedding, get_all_with_embeddings is used."""
        theme = ThemeContext(
            theme_text="tennis tournament",
            theme_embedding=[1.0, 0.0, 0.0],
        )
        embedding_rows = [
            InterestEmbeddingRow(
                user_id=test_user.id,
                keyword="tennis",
                summary="plays weekends",
                iab_category_id="483",
                embedding=[1.0, 0.0, 0.0],
                total_mentions=2,
                short_term_stored=1.0,
                last_mentioned_conv_idx=0,
            ),
            InterestEmbeddingRow(
                user_id=test_user.id,
                keyword="ai",
                summary="ml work",
                iab_category_id="610",
                embedding=[0.0, 1.0, 0.0],
                total_mentions=10,
                short_term_stored=3.0,
                last_mentioned_conv_idx=0,
            ),
        ]

        with (
            patch("coyo.services.memory_context.InterestRepository") as MockInterestRepo,
            patch(
                "coyo.services.memory_context.ConversationSummaryRepository"
            ) as MockConvSummaryRepo,
        ):
            mock_interest_inst = MockInterestRepo.return_value
            mock_interest_inst.get_all_with_embeddings = AsyncMock(
                return_value=embedding_rows,
            )
            mock_interest_inst.get_top_interests = AsyncMock(return_value=[])

            mock_conv_inst = MockConvSummaryRepo.return_value
            mock_conv_inst.get_all_with_embeddings = AsyncMock(return_value=[])
            mock_conv_inst.get_latest_for_user = AsyncMock(return_value=[])

            result = await MemoryContextService.build_context(
                db_session,
                test_user.id,
                theme=theme,
            )

        assert result is not None
        # Tennis (theme-aligned) should appear before AI in the block.
        tennis_pos = result.find("tennis")
        ai_pos = result.find("ai")
        assert tennis_pos != -1 and ai_pos != -1
        assert tennis_pos < ai_pos
        mock_interest_inst.get_all_with_embeddings.assert_awaited_once()

    @pytest.mark.unit
    async def test_build_context_theme_none_falls_back_to_legacy(
        self, db_session: AsyncSession, test_user: User
    ):
        """ThemeContext with embedding=None must use the legacy path."""
        theme = ThemeContext(
            theme_text="general",
            theme_embedding=None,
        )
        with (
            patch("coyo.services.memory_context.InterestRepository") as MockInterestRepo,
            patch(
                "coyo.services.memory_context.ConversationSummaryRepository"
            ) as MockConvSummaryRepo,
        ):
            mock_interest_inst = MockInterestRepo.return_value
            mock_interest_inst.get_top_interests = AsyncMock(return_value=[])
            mock_interest_inst.get_all_with_embeddings = AsyncMock(
                return_value=[],
            )

            mock_conv_inst = MockConvSummaryRepo.return_value
            mock_conv_inst.get_latest_for_user = AsyncMock(return_value=[])
            mock_conv_inst.get_all_with_embeddings = AsyncMock(return_value=[])

            await MemoryContextService.build_context(
                db_session,
                test_user.id,
                theme=theme,
            )

        mock_interest_inst.get_top_interests.assert_awaited_once()
        mock_interest_inst.get_all_with_embeddings.assert_not_awaited()

    @pytest.mark.unit
    async def test_build_context_omits_empty_sections(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should include only populated sections."""
        mock_interests = [
            InterestWithWeight(
                keyword="cooking",
                keyword_type="category",
                is_news_relevant=False,
                total_mentions=1,
                effective_weight=0.8,
                last_mentioned_conv_idx=1,
                summary=None,
            ),
        ]

        with (
            patch("coyo.services.memory_context.InterestRepository") as MockInterestRepo,
            patch(
                "coyo.services.memory_context.ConversationSummaryRepository"
            ) as MockConvSummaryRepo,
        ):
            mock_interest_inst = MockInterestRepo.return_value
            mock_interest_inst.get_top_interests = AsyncMock(return_value=mock_interests)

            mock_conv_inst = MockConvSummaryRepo.return_value
            mock_conv_inst.get_latest_for_user = AsyncMock(return_value=[])

            result = await MemoryContextService.build_context(db_session, test_user.id)

        assert result is not None
        assert "Interests" in result
        assert "cooking" in result
        # No profile summary, no attrs, no recent conversations
        assert "User Profile" not in result
        assert "Background" not in result
        assert "Recent Conversations" not in result


# ---------------------------------------------------------------------------
# _format_memory_block tests
# ---------------------------------------------------------------------------


class TestFormatMemoryBlock:
    """Tests for the _format_memory_block helper."""

    @pytest.mark.unit
    def test_format_interest_with_summary(self):
        """Interest with summary should show keyword: summary."""
        interests = [
            InterestWithWeight(
                keyword="tennis",
                keyword_type="category",
                is_news_relevant=True,
                total_mentions=3,
                effective_weight=1.5,
                last_mentioned_conv_idx=5,
                summary="User plays tennis regularly.",
            ),
        ]
        result = _format_memory_block(
            profile_summary=None,
            profile_attrs=[],
            top_interests=interests,
            recent_summaries=[],
        )
        assert "- tennis: <user_data>User plays tennis regularly.</user_data>" in result

    @pytest.mark.unit
    def test_format_interest_without_summary(self):
        """Interest without summary should show keyword only."""
        interests = [
            InterestWithWeight(
                keyword="cooking",
                keyword_type="category",
                is_news_relevant=False,
                total_mentions=1,
                effective_weight=0.5,
                last_mentioned_conv_idx=1,
                summary=None,
            ),
        ]
        result = _format_memory_block(
            profile_summary=None,
            profile_attrs=[],
            top_interests=interests,
            recent_summaries=[],
        )
        assert "- cooking" in result
        assert "- cooking:" not in result

    @pytest.mark.unit
    def test_format_profile_attributes(self):
        """Attributes should be formatted with key, value, and confidence."""
        attrs = [
            MagicMock(
                spec=UserAttribute,
                key="job_industry",
                value="Software Engineer",
                confidence=0.9,
            ),
            MagicMock(
                spec=UserAttribute,
                key="hometown_or_location",
                value="Tokyo",
                confidence=0.8,
            ),
        ]
        result = _format_memory_block(
            profile_summary=None,
            profile_attrs=attrs,
            top_interests=[],
            recent_summaries=[],
        )
        assert "job_industry: <user_data>Software Engineer</user_data>" in result
        assert "hometown_or_location: <user_data>Tokyo</user_data>" in result
        assert "confidence" not in result
        assert "--- Background ---" in result

    @pytest.mark.unit
    def test_format_recent_conversations(self):
        """Conversation summaries should be formatted with date."""
        conv_summary = MagicMock(spec=ConversationSummary)
        conv_summary.created_at = datetime(2025, 3, 15, 10, 0, 0, tzinfo=UTC)
        conv_summary.source_keyword = "tennis"
        conv_summary.topic_title = "Sports Discussion"
        conv_summary.summary = "Talked about recent matches."

        result = _format_memory_block(
            profile_summary=None,
            profile_attrs=[],
            top_interests=[],
            recent_summaries=[conv_summary],
        )
        assert "--- Recent Conversations ---" in result
        assert "2025-03-15" in result
        assert "[tennis]" in result
        assert '"Sports Discussion"' in result
        assert "Talked about recent matches." in result

    @pytest.mark.unit
    def test_format_recent_conversations_no_source_keyword(self):
        """Conversation summary without source_keyword should omit bracket."""
        conv_summary = MagicMock(spec=ConversationSummary)
        conv_summary.created_at = datetime(2025, 3, 15, 10, 0, 0, tzinfo=UTC)
        conv_summary.source_keyword = None
        conv_summary.topic_title = "Free conversation"
        conv_summary.summary = "General chat."

        result = _format_memory_block(
            profile_summary=None,
            profile_attrs=[],
            top_interests=[],
            recent_summaries=[conv_summary],
        )
        assert "[" not in result.split("Recent Conversations")[1].split('"Free conversation"')[0]

    @pytest.mark.unit
    def test_min_max_normalize_all_equal_returns_half(self):
        """All-equal inputs map to 0.5 to avoid divide-by-zero."""
        assert _min_max_normalize([2.0, 2.0, 2.0]) == [0.5, 0.5, 0.5]

    @pytest.mark.unit
    def test_min_max_normalize_basic(self):
        """Standard min-max normalization to [0, 1]."""
        result = _min_max_normalize([1.0, 2.0, 4.0])
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(1.0 / 3.0)
        assert result[2] == pytest.approx(1.0)

    @pytest.mark.unit
    def test_min_max_normalize_empty(self):
        assert _min_max_normalize([]) == []

    @pytest.mark.unit
    def test_rank_interests_orders_by_similarity(self):
        """Rows aligned with the theme vector should rank above unrelated."""
        theme_vec = [1.0, 0.0, 0.0]
        rows = [
            InterestEmbeddingRow(
                user_id=uuid.uuid4(),
                keyword="ai",
                summary="ML stuff",
                iab_category_id="610",
                embedding=[0.0, 1.0, 0.0],  # orthogonal
                total_mentions=10,
                short_term_stored=2.5,
                last_mentioned_conv_idx=0,
            ),
            InterestEmbeddingRow(
                user_id=uuid.uuid4(),
                keyword="tennis",
                summary="plays weekends",
                iab_category_id="483",
                embedding=[0.99, 0.01, 0.0],  # nearly aligned
                total_mentions=2,
                short_term_stored=1.0,
                last_mentioned_conv_idx=0,
            ),
        ]
        ranked = _rank_interests(
            rows,
            theme_vec=theme_vec,
            current_conv_idx=5,
            alpha=0.7,
            beta=0.3,
        )
        assert ranked[0].keyword == "tennis"
        assert ranked[1].keyword == "ai"

    @pytest.mark.unit
    def test_rank_summaries_recency_decay(self):
        """Newer summaries should outrank older ones at equal similarity."""
        theme_vec = [1.0, 0.0]
        now = datetime.now(UTC)
        rows = [
            ConversationSummaryEmbeddingRow(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                source_keyword="x",
                topic_title="Old",
                summary="...",
                embedding=[1.0, 0.0],
                created_at=now - timedelta(days=30),
            ),
            ConversationSummaryEmbeddingRow(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                source_keyword="x",
                topic_title="New",
                summary="...",
                embedding=[1.0, 0.0],
                created_at=now,
            ),
        ]
        ranked = _rank_summaries(
            rows,
            theme_vec=theme_vec,
            alpha=0.7,
            beta=0.3,
            half_life_days=14,
        )
        assert ranked[0].topic_title == "New"

    @pytest.mark.unit
    def test_format_includes_usage_instructions(self):
        """Memory block should always include usage instructions."""
        result = _format_memory_block(
            profile_summary=None,
            profile_attrs=[],
            top_interests=[
                InterestWithWeight(
                    keyword="test",
                    keyword_type="category",
                    is_news_relevant=False,
                    total_mentions=1,
                    effective_weight=0.5,
                    last_mentioned_conv_idx=1,
                    summary=None,
                ),
            ],
            recent_summaries=[],
        )
        assert "HOW TO USE THIS INFORMATION" in result
