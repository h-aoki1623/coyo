"""Unit tests for coyo.services.keyword_postprocessor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coyo.services.iab_taxonomy import IABMatchResult
from coyo.services.keyword_postprocessor import (
    IABClassification,
    KeywordPostprocessor,
    ProcessedKeyword,
    RawKeyword,
)
from coyo.services.synonym_judge import SynonymJudgment


def _make_raw(
    keyword: str,
    keyword_type: str = "category",
    is_news_relevant: bool = True,
    summary: str | None = None,
) -> RawKeyword:
    return RawKeyword(
        keyword=keyword,
        keyword_type=keyword_type,
        is_news_relevant=is_news_relevant,
        summary=summary,
    )


@pytest.fixture()
def mock_embedding_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def mock_iab_service() -> MagicMock:
    svc = MagicMock()
    svc.ensure_embeddings = AsyncMock()
    svc.find_by_name.return_value = None
    return svc


@pytest.fixture()
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.keyword_dedup_threshold = 0.90
    settings.keyword_dedup_candidate_threshold = 0.40
    settings.keyword_normalize_threshold = 0.92
    settings.keyword_validate_threshold = 0.75
    settings.llm_interest_model = "gpt-4o-mini"
    return settings


@pytest.fixture()
def processor(
    mock_embedding_service: AsyncMock,
    mock_iab_service: MagicMock,
) -> KeywordPostprocessor:
    return KeywordPostprocessor(mock_embedding_service, mock_iab_service)


class TestProcessA:
    """Process A: Deduplicate new keywords against each other."""

    def test_deduplicates_similar_keywords_keeps_shorter(
        self,
        processor: KeywordPostprocessor,
        mock_settings: MagicMock,
    ) -> None:
        keywords = [
            _make_raw("artificial intelligence"),
            _make_raw("AI"),  # shorter, should be kept
            _make_raw("sports"),  # unrelated
        ]
        # AI and artificial intelligence are very similar (index 0,1)
        # sports is different (index 2)
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.99, 0.1, 0.0],  # very similar to index 0
            [0.0, 1.0, 0.0],  # orthogonal
        ]

        with patch(
            "coyo.services.keyword_postprocessor.get_settings",
            return_value=mock_settings,
        ):
            result_kw, result_emb = processor._process_a(keywords, embeddings)

        # "AI" (shorter) should be kept, "artificial intelligence" dropped
        result_texts = [kw.keyword for kw in result_kw]
        assert "AI" in result_texts
        assert "sports" in result_texts
        assert "artificial intelligence" not in result_texts
        assert len(result_kw) == 2
        assert len(result_emb) == 2

    def test_no_dedup_when_all_below_threshold(
        self,
        processor: KeywordPostprocessor,
        mock_settings: MagicMock,
    ) -> None:
        keywords = [
            _make_raw("technology"),
            _make_raw("sports"),
            _make_raw("cooking"),
        ]
        # All orthogonal
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]

        with patch(
            "coyo.services.keyword_postprocessor.get_settings",
            return_value=mock_settings,
        ):
            result_kw, result_emb = processor._process_a(keywords, embeddings)

        assert len(result_kw) == 3
        assert len(result_emb) == 3

    def test_single_keyword_passes_through(
        self,
        processor: KeywordPostprocessor,
        mock_settings: MagicMock,
    ) -> None:
        keywords = [_make_raw("tech")]
        embeddings = [[1.0, 0.0]]

        with patch(
            "coyo.services.keyword_postprocessor.get_settings",
            return_value=mock_settings,
        ):
            result_kw, result_emb = processor._process_a(keywords, embeddings)

        assert len(result_kw) == 1
        assert result_kw[0].keyword == "tech"


class TestProcessB:
    """Process B: IAB validation for categories via LLM, pass-through for entities."""

    @pytest.mark.asyncio()
    async def test_normalizes_category_to_iab_name(
        self,
        processor: KeywordPostprocessor,
        mock_iab_service: MagicMock,
    ) -> None:
        keywords = [_make_raw("tech stuff", keyword_type="category")]
        embeddings = [[1.0, 0.0, 0.0]]

        mock_iab_service.format_for_prompt.return_value = "ID | Name\n1.10 | Auto Technology"

        llm_result = IABClassification(
            action="normalize",
            iab_category_id="1.10",
            iab_name="Auto Technology",
        )

        with patch(
            "coyo.services.keyword_postprocessor.OpenAIClient",
        ) as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.structured = AsyncMock(return_value=llm_result)
            mock_llm_cls.return_value = mock_llm

            result_kw, result_emb = await processor._process_b(keywords, embeddings)

        assert len(result_kw) == 1
        assert result_kw[0].keyword == "auto technology"  # lowercased
        assert result_kw[0].iab_category_id == "1.10"
        assert result_kw[0].keyword_type == "category"

    @pytest.mark.asyncio()
    async def test_validates_category_keeps_original_keyword(
        self,
        processor: KeywordPostprocessor,
        mock_iab_service: MagicMock,
    ) -> None:
        keywords = [_make_raw("f1", keyword_type="category")]
        embeddings = [[1.0, 0.0, 0.0]]

        mock_iab_service.format_for_prompt.return_value = "ID | Name\n1.21 | Auto Racing"

        llm_result = IABClassification(
            action="valid",
            iab_category_id="1.21",
            iab_name="Auto Racing",
        )

        with patch(
            "coyo.services.keyword_postprocessor.OpenAIClient",
        ) as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.structured = AsyncMock(return_value=llm_result)
            mock_llm_cls.return_value = mock_llm

            result_kw, _emb = await processor._process_b(keywords, embeddings)

        assert len(result_kw) == 1
        assert result_kw[0].keyword == "f1"
        assert result_kw[0].iab_category_id is None

    @pytest.mark.asyncio()
    async def test_deletes_invalid_category(
        self,
        processor: KeywordPostprocessor,
        mock_iab_service: MagicMock,
    ) -> None:
        keywords = [_make_raw("gibberish xyz", keyword_type="category")]
        embeddings = [[1.0, 0.0, 0.0]]

        mock_iab_service.format_for_prompt.return_value = "ID | Name\n1 | Automotive"

        llm_result = IABClassification(action="delete")

        with patch(
            "coyo.services.keyword_postprocessor.OpenAIClient",
        ) as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.structured = AsyncMock(return_value=llm_result)
            mock_llm_cls.return_value = mock_llm

            result_kw, result_emb = await processor._process_b(keywords, embeddings)

        assert len(result_kw) == 0
        assert len(result_emb) == 0

    @pytest.mark.asyncio()
    async def test_entities_pass_through_without_llm_call(
        self,
        processor: KeywordPostprocessor,
        mock_iab_service: MagicMock,
    ) -> None:
        keywords = [_make_raw("Elon Musk", keyword_type="entity")]
        embeddings = [[1.0, 0.0, 0.0]]

        mock_iab_service.format_for_prompt.return_value = "ID | Name\n1 | Automotive"

        with patch(
            "coyo.services.keyword_postprocessor.OpenAIClient",
        ) as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.structured = AsyncMock()
            mock_llm_cls.return_value = mock_llm

            result_kw, _emb = await processor._process_b(keywords, embeddings)

        assert len(result_kw) == 1
        assert result_kw[0].keyword == "Elon Musk"
        assert result_kw[0].keyword_type == "entity"
        assert result_kw[0].iab_category_id is None
        # LLM should NOT be called for entities
        mock_llm.structured.assert_not_called()

    @pytest.mark.asyncio()
    async def test_falls_back_to_embedding_on_llm_failure(
        self,
        processor: KeywordPostprocessor,
        mock_iab_service: MagicMock,
    ) -> None:
        keywords = [_make_raw("sports", keyword_type="category")]
        embeddings = [[1.0, 0.0, 0.0]]

        mock_iab_service.format_for_prompt.return_value = "ID | Name\n17 | Sports"
        mock_iab_service.match.return_value = IABMatchResult(
            action="normalize",
            iab_id="17",
            iab_name="Sports",
            similarity=0.95,
        )

        with patch(
            "coyo.services.keyword_postprocessor.OpenAIClient",
        ) as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.structured = AsyncMock(side_effect=RuntimeError("LLM down"))
            mock_llm_cls.return_value = mock_llm

            result_kw, _emb = await processor._process_b(keywords, embeddings)

        assert len(result_kw) == 1
        assert result_kw[0].keyword == "sports"
        assert result_kw[0].iab_category_id == "17"
        mock_iab_service.match.assert_called_once()

    @pytest.mark.asyncio()
    async def test_mixed_categories_and_entities(
        self,
        processor: KeywordPostprocessor,
        mock_iab_service: MagicMock,
    ) -> None:
        keywords = [
            _make_raw("tech", keyword_type="category"),
            _make_raw("Google", keyword_type="entity"),
        ]
        embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]

        mock_iab_service.format_for_prompt.return_value = "ID | Name\n2 | Technology"

        llm_result = IABClassification(
            action="valid",
            iab_category_id="2",
            iab_name="Technology",
        )

        with patch(
            "coyo.services.keyword_postprocessor.OpenAIClient",
        ) as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.structured = AsyncMock(return_value=llm_result)
            mock_llm_cls.return_value = mock_llm

            result_kw, _emb = await processor._process_b(keywords, embeddings)

        assert len(result_kw) == 2
        # LLM called once for category, not for entity
        assert mock_llm.structured.call_count == 1


def _make_processed(keyword: str) -> ProcessedKeyword:
    return ProcessedKeyword(
        keyword=keyword,
        keyword_type="category",
        is_news_relevant=True,
        summary=None,
        iab_category_id=None,
        merge_target=None,
    )


class TestProcessC:
    """Process C: Deduplicate against existing DB keywords (hybrid LLM)."""

    @pytest.mark.asyncio()
    async def test_auto_merges_above_dedup_threshold_without_llm(
        self,
        processor: KeywordPostprocessor,
        mock_settings: MagicMock,
    ) -> None:
        """Similarity >= 0.90 should merge without invoking the LLM."""
        keywords = [_make_processed("tech")]
        keyword_embeddings = [[1.0, 0.0, 0.0]]
        existing_keywords = ["technology"]
        existing_embeddings = [[0.99, 0.1, 0.0]]  # sim ~0.995

        with (
            patch(
                "coyo.services.keyword_postprocessor.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "coyo.services.keyword_postprocessor.OpenAIClient",
            ) as mock_llm_cls,
        ):
            mock_llm = MagicMock()
            mock_llm.structured = AsyncMock()
            mock_llm_cls.return_value = mock_llm

            result = await processor._process_c(
                keywords,
                keyword_embeddings,
                existing_keywords,
                existing_embeddings,
            )

        assert len(result) == 1
        assert result[0].merge_target == "technology"
        # No LLM call for the auto-merge path
        assert mock_llm.structured.call_count == 0

    @pytest.mark.asyncio()
    async def test_merges_via_llm_when_in_candidate_zone(
        self,
        processor: KeywordPostprocessor,
        mock_settings: MagicMock,
    ) -> None:
        """0.40 <= sim < 0.90: LLM says synonym → merge."""
        keywords = [_make_processed("AI")]
        keyword_embeddings = [[1.0, 0.0, 0.0]]
        existing_keywords = ["artificial intelligence"]
        existing_embeddings = [[0.6, 0.8, 0.0]]  # sim = 0.6 (candidate zone)

        with (
            patch(
                "coyo.services.keyword_postprocessor.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "coyo.services.keyword_postprocessor.OpenAIClient",
            ) as mock_llm_cls,
        ):
            mock_llm = MagicMock()
            mock_llm.structured = AsyncMock(
                return_value=SynonymJudgment(
                    is_synonym=True,
                    reason="abbreviation",
                ),
            )
            mock_llm_cls.return_value = mock_llm

            result = await processor._process_c(
                keywords,
                keyword_embeddings,
                existing_keywords,
                existing_embeddings,
            )

        assert len(result) == 1
        assert result[0].merge_target == "artificial intelligence"
        assert mock_llm.structured.call_count == 1

    @pytest.mark.asyncio()
    async def test_no_merge_when_llm_rejects(
        self,
        processor: KeywordPostprocessor,
        mock_settings: MagicMock,
    ) -> None:
        """Candidate zone but LLM says not a synonym → keep as new."""
        keywords = [_make_processed("tennis")]
        keyword_embeddings = [[1.0, 0.0, 0.0]]
        existing_keywords = ["badminton"]
        existing_embeddings = [[0.7, 0.71, 0.0]]  # candidate zone

        with (
            patch(
                "coyo.services.keyword_postprocessor.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "coyo.services.keyword_postprocessor.OpenAIClient",
            ) as mock_llm_cls,
        ):
            mock_llm = MagicMock()
            mock_llm.structured = AsyncMock(
                return_value=SynonymJudgment(
                    is_synonym=False,
                    reason="different sports",
                ),
            )
            mock_llm_cls.return_value = mock_llm

            result = await processor._process_c(
                keywords,
                keyword_embeddings,
                existing_keywords,
                existing_embeddings,
            )

        assert len(result) == 1
        assert result[0].merge_target is None
        assert mock_llm.structured.call_count == 1

    @pytest.mark.asyncio()
    async def test_no_merge_below_candidate_threshold_skips_llm(
        self,
        processor: KeywordPostprocessor,
        mock_settings: MagicMock,
    ) -> None:
        """Similarity < 0.40: keep as new without invoking the LLM."""
        keywords = [_make_processed("cooking")]
        keyword_embeddings = [[1.0, 0.0, 0.0]]
        existing_keywords = ["sports"]
        existing_embeddings = [[0.0, 1.0, 0.0]]  # orthogonal, sim = 0

        with (
            patch(
                "coyo.services.keyword_postprocessor.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "coyo.services.keyword_postprocessor.OpenAIClient",
            ) as mock_llm_cls,
        ):
            mock_llm = MagicMock()
            mock_llm.structured = AsyncMock()
            mock_llm_cls.return_value = mock_llm

            result = await processor._process_c(
                keywords,
                keyword_embeddings,
                existing_keywords,
                existing_embeddings,
            )

        assert len(result) == 1
        assert result[0].merge_target is None
        assert mock_llm.structured.call_count == 0

    @pytest.mark.asyncio()
    async def test_falls_back_to_no_merge_on_llm_failure(
        self,
        processor: KeywordPostprocessor,
        mock_settings: MagicMock,
    ) -> None:
        """LLM error in candidate zone: safe default is no merge."""
        keywords = [_make_processed("soccer")]
        keyword_embeddings = [[1.0, 0.0, 0.0]]
        existing_keywords = ["football"]
        existing_embeddings = [[0.6, 0.8, 0.0]]  # candidate zone

        with (
            patch(
                "coyo.services.keyword_postprocessor.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "coyo.services.keyword_postprocessor.OpenAIClient",
            ) as mock_llm_cls,
        ):
            mock_llm = MagicMock()
            mock_llm.structured = AsyncMock(side_effect=RuntimeError("api down"))
            mock_llm_cls.return_value = mock_llm

            result = await processor._process_c(
                keywords,
                keyword_embeddings,
                existing_keywords,
                existing_embeddings,
            )

        assert len(result) == 1
        assert result[0].merge_target is None

    @pytest.mark.asyncio()
    async def test_no_existing_keywords_passes_through(
        self,
        processor: KeywordPostprocessor,
    ) -> None:
        keywords = [_make_processed("tech")]
        result = await processor._process_c(keywords, [[1.0, 0.0]], [], [])

        assert len(result) == 1
        assert result[0].merge_target is None

    @pytest.mark.asyncio()
    async def test_empty_keywords_returns_empty(
        self,
        processor: KeywordPostprocessor,
    ) -> None:
        result = await processor._process_c([], [], ["existing"], [[1.0, 0.0]])
        assert result == []


class TestFullPipeline:
    """End-to-end test of the full process() pipeline."""

    @pytest.mark.asyncio()
    async def test_empty_input_returns_empty(
        self,
        processor: KeywordPostprocessor,
    ) -> None:
        result = await processor.process([], [])
        assert result == []

    @pytest.mark.asyncio()
    async def test_full_pipeline_with_mocked_services(
        self,
        processor: KeywordPostprocessor,
        mock_embedding_service: AsyncMock,
        mock_iab_service: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        new_keywords = [
            _make_raw("tech", keyword_type="category"),
            _make_raw("Google", keyword_type="entity"),
        ]
        existing = ["technology"]

        # Embeddings: [tech_emb, google_emb, technology_emb]
        mock_embedding_service.embed = AsyncMock(
            return_value=[
                [1.0, 0.0, 0.0],  # tech
                [0.0, 1.0, 0.0],  # Google
                [0.99, 0.1, 0.0],  # technology (similar to tech)
            ],
        )

        # LLM: "tech" category is valid
        mock_iab_service.format_for_prompt.return_value = "ID | Name\n2 | Technology"
        llm_result = IABClassification(
            action="valid",
            iab_category_id="2",
            iab_name="Technology",
        )

        with (
            patch(
                "coyo.services.keyword_postprocessor.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "coyo.services.keyword_postprocessor.OpenAIClient",
            ) as mock_llm_cls,
        ):
            mock_llm = MagicMock()
            mock_llm.structured = AsyncMock(return_value=llm_result)
            mock_llm_cls.return_value = mock_llm

            result = await processor.process(new_keywords, existing)

        # tech should merge into "technology" (similar), Google should be new
        assert len(result) == 2
        tech_result = next(r for r in result if r.keyword == "tech")
        google_result = next(r for r in result if r.keyword == "Google")

        assert tech_result.merge_target == "technology"
        assert google_result.merge_target is None
        assert google_result.keyword_type == "entity"

    @pytest.mark.asyncio()
    async def test_pipeline_calls_ensure_embeddings(
        self,
        processor: KeywordPostprocessor,
        mock_embedding_service: AsyncMock,
        mock_iab_service: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        new_keywords = [_make_raw("tech", keyword_type="category")]

        mock_embedding_service.embed = AsyncMock(
            return_value=[[1.0, 0.0, 0.0]],
        )
        mock_iab_service.format_for_prompt.return_value = "ID | Name\n2 | Technology"
        llm_result = IABClassification(
            action="valid",
            iab_category_id="2",
            iab_name="Technology",
        )

        with (
            patch(
                "coyo.services.keyword_postprocessor.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "coyo.services.keyword_postprocessor.OpenAIClient",
            ) as mock_llm_cls,
        ):
            mock_llm = MagicMock()
            mock_llm.structured = AsyncMock(return_value=llm_result)
            mock_llm_cls.return_value = mock_llm

            await processor.process(new_keywords, [])

        mock_iab_service.ensure_embeddings.assert_awaited_once_with(
            mock_embedding_service,
        )
