"""Unit tests for coyo.services.keyword_postprocessor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coyo.services.iab_taxonomy import IABMatchResult
from coyo.services.keyword_postprocessor import (
    KeywordPostprocessor,
    ProcessedKeyword,
    RawKeyword,
)


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
    return svc


@pytest.fixture()
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.keyword_dedup_threshold = 0.90
    settings.keyword_normalize_threshold = 0.92
    settings.keyword_validate_threshold = 0.75
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
        self, processor: KeywordPostprocessor, mock_settings: MagicMock,
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
        self, processor: KeywordPostprocessor, mock_settings: MagicMock,
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
        self, processor: KeywordPostprocessor, mock_settings: MagicMock,
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
    """Process B: IAB validation for categories, pass-through for entities."""

    def test_normalizes_category_to_iab_name(
        self, processor: KeywordPostprocessor, mock_iab_service: MagicMock,
    ) -> None:
        keywords = [_make_raw("tech stuff", keyword_type="category")]
        embeddings = [[1.0, 0.0, 0.0]]

        mock_iab_service.match.return_value = IABMatchResult(
            action="normalize",
            iab_id="1.10",
            iab_name="Auto Technology",
            similarity=0.95,
        )

        result_kw, result_emb = processor._process_b(keywords, embeddings)

        assert len(result_kw) == 1
        assert result_kw[0].keyword == "auto technology"  # lowercased
        assert result_kw[0].iab_category_id == "1.10"
        assert result_kw[0].keyword_type == "category"

    def test_validates_category_without_normalization(
        self, processor: KeywordPostprocessor, mock_iab_service: MagicMock,
    ) -> None:
        keywords = [_make_raw("custom tech", keyword_type="category")]
        embeddings = [[1.0, 0.0, 0.0]]

        mock_iab_service.match.return_value = IABMatchResult(
            action="valid",
            iab_id=None,
            iab_name=None,
            similarity=0.80,
        )

        result_kw, _emb = processor._process_b(keywords, embeddings)

        assert len(result_kw) == 1
        assert result_kw[0].keyword == "custom tech"
        assert result_kw[0].iab_category_id is None

    def test_rejects_invalid_category(
        self, processor: KeywordPostprocessor, mock_iab_service: MagicMock,
    ) -> None:
        keywords = [_make_raw("gibberish xyz", keyword_type="category")]
        embeddings = [[1.0, 0.0, 0.0]]

        mock_iab_service.match.return_value = IABMatchResult(
            action="invalid",
            iab_id=None,
            iab_name=None,
            similarity=0.30,
        )

        result_kw, result_emb = processor._process_b(keywords, embeddings)

        assert len(result_kw) == 0
        assert len(result_emb) == 0

    def test_entities_pass_through_without_iab_validation(
        self, processor: KeywordPostprocessor, mock_iab_service: MagicMock,
    ) -> None:
        keywords = [_make_raw("Elon Musk", keyword_type="entity")]
        embeddings = [[1.0, 0.0, 0.0]]

        result_kw, _emb = processor._process_b(keywords, embeddings)

        assert len(result_kw) == 1
        assert result_kw[0].keyword == "Elon Musk"
        assert result_kw[0].keyword_type == "entity"
        assert result_kw[0].iab_category_id is None
        # IAB match should NOT be called for entities
        mock_iab_service.match.assert_not_called()

    def test_mixed_categories_and_entities(
        self, processor: KeywordPostprocessor, mock_iab_service: MagicMock,
    ) -> None:
        keywords = [
            _make_raw("tech", keyword_type="category"),
            _make_raw("Google", keyword_type="entity"),
        ]
        embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]

        mock_iab_service.match.return_value = IABMatchResult(
            action="valid",
            iab_id=None,
            iab_name=None,
            similarity=0.80,
        )

        result_kw, _emb = processor._process_b(keywords, embeddings)

        assert len(result_kw) == 2
        # Entity passes through, category validated
        assert mock_iab_service.match.call_count == 1


class TestProcessC:
    """Process C: Deduplicate against existing DB keywords."""

    def test_merges_when_similar_to_existing(
        self, processor: KeywordPostprocessor, mock_settings: MagicMock,
    ) -> None:
        keywords = [
            ProcessedKeyword(
                keyword="tech",
                keyword_type="category",
                is_news_relevant=True,
                summary=None,
                iab_category_id=None,
                merge_target=None,
            ),
        ]
        keyword_embeddings = [[1.0, 0.0, 0.0]]
        existing_keywords = ["technology"]
        existing_embeddings = [[0.99, 0.1, 0.0]]  # very similar

        with patch(
            "coyo.services.keyword_postprocessor.get_settings",
            return_value=mock_settings,
        ):
            result = processor._process_c(
                keywords, keyword_embeddings, existing_keywords, existing_embeddings,
            )

        assert len(result) == 1
        assert result[0].merge_target == "technology"

    def test_inserts_when_below_threshold(
        self, processor: KeywordPostprocessor, mock_settings: MagicMock,
    ) -> None:
        keywords = [
            ProcessedKeyword(
                keyword="cooking",
                keyword_type="category",
                is_news_relevant=True,
                summary=None,
                iab_category_id=None,
                merge_target=None,
            ),
        ]
        keyword_embeddings = [[1.0, 0.0, 0.0]]
        existing_keywords = ["sports"]
        existing_embeddings = [[0.0, 1.0, 0.0]]  # orthogonal

        with patch(
            "coyo.services.keyword_postprocessor.get_settings",
            return_value=mock_settings,
        ):
            result = processor._process_c(
                keywords, keyword_embeddings, existing_keywords, existing_embeddings,
            )

        assert len(result) == 1
        assert result[0].merge_target is None

    def test_no_existing_keywords_passes_through(
        self, processor: KeywordPostprocessor,
    ) -> None:
        keywords = [
            ProcessedKeyword(
                keyword="tech",
                keyword_type="category",
                is_news_relevant=True,
                summary=None,
                iab_category_id=None,
                merge_target=None,
            ),
        ]
        result = processor._process_c(keywords, [[1.0, 0.0]], [], [])

        assert len(result) == 1
        assert result[0].merge_target is None

    def test_empty_keywords_returns_empty(
        self, processor: KeywordPostprocessor,
    ) -> None:
        result = processor._process_c([], [], ["existing"], [[1.0, 0.0]])
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

        # IAB: "tech" category is valid
        mock_iab_service.match.return_value = IABMatchResult(
            action="valid",
            iab_id=None,
            iab_name=None,
            similarity=0.80,
        )

        with patch(
            "coyo.services.keyword_postprocessor.get_settings",
            return_value=mock_settings,
        ):
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
        mock_iab_service.match.return_value = IABMatchResult(
            action="valid", iab_id=None, iab_name=None, similarity=0.80,
        )

        with patch(
            "coyo.services.keyword_postprocessor.get_settings",
            return_value=mock_settings,
        ):
            await processor.process(new_keywords, [])

        mock_iab_service.ensure_embeddings.assert_awaited_once_with(
            mock_embedding_service,
        )
