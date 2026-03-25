"""Unit tests for the MemoryContextService."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.conversation_summary import ConversationSummary
from coyo.models.user import User
from coyo.models.user_profile_attribute import UserProfileAttribute
from coyo.models.user_profile_summary import UserProfileSummary
from coyo.repositories.interest import InterestWithWeight
from coyo.services.memory_context import MemoryContextService, _format_memory_block


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
    async def test_build_context_returns_none_for_missing_user(
        self, db_session: AsyncSession
    ):
        """Should return None when user does not exist."""
        result = await MemoryContextService.build_context(
            db_session, uuid.uuid4()
        )
        assert result is None

    @pytest.mark.unit
    async def test_build_context_returns_none_for_empty_memory(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should return None when user exists but has no memory data."""
        result = await MemoryContextService.build_context(
            db_session, test_user.id
        )
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
        attr = UserProfileAttribute(
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
                keyword_type="topic",
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
            patch(
                "coyo.services.memory_context.InterestRepository"
            ) as MockInterestRepo,
            patch(
                "coyo.services.memory_context.ConversationSummaryRepository"
            ) as MockConvSummaryRepo,
        ):
            mock_interest_inst = MockInterestRepo.return_value
            mock_interest_inst.get_top_interests = AsyncMock(
                return_value=mock_interests
            )

            mock_conv_inst = MockConvSummaryRepo.return_value
            mock_conv_inst.get_latest_for_user = AsyncMock(
                return_value=[mock_conv_summary]
            )

            result = await MemoryContextService.build_context(
                db_session, test_user.id
            )

        assert result is not None
        assert "[WHAT YOU KNOW ABOUT THIS USER]" in result
        assert "User Profile" in result
        assert "software engineer" in result.lower()
        assert "tennis" in result.lower()
        assert "Background" in result
        assert "job_industry" in result
        assert "Recent Conversations" in result

    @pytest.mark.unit
    async def test_build_context_omits_empty_sections(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should include only populated sections."""
        mock_interests = [
            InterestWithWeight(
                keyword="cooking",
                keyword_type="topic",
                is_news_relevant=False,
                total_mentions=1,
                effective_weight=0.8,
                last_mentioned_conv_idx=1,
                summary=None,
            ),
        ]

        with (
            patch(
                "coyo.services.memory_context.InterestRepository"
            ) as MockInterestRepo,
            patch(
                "coyo.services.memory_context.ConversationSummaryRepository"
            ) as MockConvSummaryRepo,
        ):
            mock_interest_inst = MockInterestRepo.return_value
            mock_interest_inst.get_top_interests = AsyncMock(
                return_value=mock_interests
            )

            mock_conv_inst = MockConvSummaryRepo.return_value
            mock_conv_inst.get_latest_for_user = AsyncMock(return_value=[])

            result = await MemoryContextService.build_context(
                db_session, test_user.id
            )

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
                keyword_type="topic",
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
                keyword_type="topic",
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
                spec=UserProfileAttribute,
                key="job_industry",
                value="Software Engineer",
                confidence=0.9,
            ),
            MagicMock(
                spec=UserProfileAttribute,
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
    def test_format_includes_usage_instructions(self):
        """Memory block should always include usage instructions."""
        result = _format_memory_block(
            profile_summary=None,
            profile_attrs=[],
            top_interests=[
                InterestWithWeight(
                    keyword="test",
                    keyword_type="topic",
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
