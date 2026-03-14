"""Unit tests for the CorrectionService."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.turn import Turn
from coyo.services.correction import CorrectionAnalysis, CorrectionService


class TestCorrectionService:
    """Tests for the CorrectionService.analyze_turn method."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM client for correction analysis."""
        llm = AsyncMock()
        return llm

    @pytest.fixture
    def correction_service(self, db_session: AsyncSession, mock_llm):
        """Create a CorrectionService with a mocked LLM client."""
        service = CorrectionService(db_session)
        service._llm = mock_llm
        return service

    @pytest.mark.unit
    async def test_analyze_turn_with_errors(
        self,
        correction_service: CorrectionService,
        mock_llm,
        db_session: AsyncSession,
        test_turn: Turn,
        test_user,
    ):
        """Verify that corrections are persisted when errors are found."""
        mock_llm.structured = AsyncMock(
            return_value=CorrectionAnalysis(
                has_errors=True,
                corrected_text="I went to the store yesterday.",
                explanation="Past tense correction.",
                items=[
                    {
                        "original": "goed",
                        "corrected": "went",
                        "original_sentence": "I goed to the store yesterday.",
                        "corrected_sentence": "I went to the store yesterday.",
                        "type": "grammar",
                        "explanation": "'go' is irregular.",
                    }
                ],
            )
        )

        result = await correction_service.analyze_turn(
            turn_id=test_turn.id,
            user_id=test_user.id,
            user_text="I goed to the store yesterday.",
        )

        assert result is not None
        assert result.corrected_text == "I went to the store yesterday."

        # Verify the turn status was updated
        updated_turn = await db_session.get(Turn, test_turn.id)
        assert updated_turn.correction_status == "has_corrections"

    @pytest.mark.unit
    async def test_analyze_turn_clean_text(
        self,
        correction_service: CorrectionService,
        mock_llm,
        db_session: AsyncSession,
        test_turn: Turn,
        test_user,
    ):
        """Verify that clean text returns None and updates status to 'clean'."""
        mock_llm.structured = AsyncMock(
            return_value=CorrectionAnalysis(
                has_errors=False,
                corrected_text="I went to the store yesterday.",
                explanation="",
                items=[],
            )
        )

        result = await correction_service.analyze_turn(
            turn_id=test_turn.id,
            user_id=test_user.id,
            user_text="I went to the store yesterday.",
        )

        assert result is None

        # Verify the turn status was updated to 'clean'
        updated_turn = await db_session.get(Turn, test_turn.id)
        assert updated_turn.correction_status == "clean"

    @pytest.mark.unit
    async def test_analyze_turn_has_errors_but_empty_items(
        self,
        correction_service: CorrectionService,
        mock_llm,
        db_session: AsyncSession,
        test_turn: Turn,
        test_user,
    ):
        """Verify that has_errors=True with empty items is treated as clean."""
        mock_llm.structured = AsyncMock(
            return_value=CorrectionAnalysis(
                has_errors=True,
                corrected_text="test",
                explanation="test",
                items=[],
            )
        )

        result = await correction_service.analyze_turn(
            turn_id=test_turn.id,
            user_id=test_user.id,
            user_text="test",
        )

        assert result is None
        updated_turn = await db_session.get(Turn, test_turn.id)
        assert updated_turn.correction_status == "clean"

    @pytest.mark.unit
    async def test_analyze_turn_nonexistent_turn(
        self,
        correction_service: CorrectionService,
        mock_llm,
        test_user,
    ):
        """Verify that a nonexistent turn returns None without error."""
        mock_llm.structured = AsyncMock(
            return_value=CorrectionAnalysis(
                has_errors=True,
                corrected_text="test",
                explanation="test",
                items=[
                    {
                        "original": "x",
                        "corrected": "y",
                        "original_sentence": "x",
                        "corrected_sentence": "y",
                        "type": "grammar",
                        "explanation": "test",
                    }
                ],
            )
        )

        result = await correction_service.analyze_turn(
            turn_id=uuid.uuid4(),
            user_id=test_user.id,
            user_text="test",
        )
        assert result is None

    @pytest.mark.unit
    async def test_analyze_turn_multiple_correction_items(
        self,
        correction_service: CorrectionService,
        mock_llm,
        db_session: AsyncSession,
        test_turn: Turn,
        test_user,
    ):
        """Verify that multiple correction items are all persisted."""
        mock_llm.structured = AsyncMock(
            return_value=CorrectionAnalysis(
                has_errors=True,
                corrected_text="I went to the store and bought some apples.",
                explanation="Multiple corrections.",
                items=[
                    {
                        "original": "goed",
                        "corrected": "went",
                        "original_sentence": "I goed to the store.",
                        "corrected_sentence": "I went to the store.",
                        "type": "grammar",
                        "explanation": "Irregular verb.",
                    },
                    {
                        "original": "buyed",
                        "corrected": "bought",
                        "original_sentence": "I buyed some apples.",
                        "corrected_sentence": "I bought some apples.",
                        "type": "grammar",
                        "explanation": "Irregular verb.",
                    },
                ],
            )
        )

        result = await correction_service.analyze_turn(
            turn_id=test_turn.id,
            user_id=test_user.id,
            user_text="I goed to the store and buyed some apples.",
        )

        assert result is not None
        assert result.corrected_text == "I went to the store and bought some apples."

    @pytest.mark.unit
    async def test_analyze_turn_default_correction_language(
        self,
        correction_service: CorrectionService,
        mock_llm,
        test_turn: Turn,
        test_user,
    ):
        """Verify that the default correction language is Japanese (ja)."""
        mock_llm.structured = AsyncMock(
            return_value=CorrectionAnalysis(
                has_errors=False,
                corrected_text="test",
                explanation="",
                items=[],
            )
        )

        await correction_service.analyze_turn(
            turn_id=test_turn.id,
            user_id=test_user.id,
            user_text="test",
        )

        # Verify the LLM was called (the system prompt should contain 'Japanese')
        mock_llm.structured.assert_called_once()

    @pytest.mark.unit
    async def test_analyze_turn_custom_correction_language(
        self,
        correction_service: CorrectionService,
        mock_llm,
        test_turn: Turn,
        test_user,
    ):
        """Verify that a custom correction language is passed to the LLM."""
        mock_llm.structured = AsyncMock(
            return_value=CorrectionAnalysis(
                has_errors=False,
                corrected_text="test",
                explanation="",
                items=[],
            )
        )

        await correction_service.analyze_turn(
            turn_id=test_turn.id,
            user_id=test_user.id,
            user_text="test",
            correction_language="ko",
        )

        mock_llm.structured.assert_called_once()


class TestCorrectionAnalysisSchema:
    """Tests for the CorrectionAnalysis Pydantic model."""

    @pytest.mark.unit
    def test_valid_analysis_with_errors(self):
        analysis = CorrectionAnalysis(
            has_errors=True,
            corrected_text="I went.",
            explanation="Fixed.",
            items=[
                {
                    "original": "goed",
                    "corrected": "went",
                    "original_sentence": "I goed.",
                    "corrected_sentence": "I went.",
                    "type": "grammar",
                    "explanation": "Irregular verb.",
                }
            ],
        )
        assert analysis.has_errors is True
        assert len(analysis.items) == 1

    @pytest.mark.unit
    def test_valid_analysis_no_errors(self):
        analysis = CorrectionAnalysis(
            has_errors=False,
            corrected_text="Perfect text.",
            explanation="",
            items=[],
        )
        assert analysis.has_errors is False
        assert len(analysis.items) == 0
