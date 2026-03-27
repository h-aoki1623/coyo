"""Unit tests for coyo.services.iab_taxonomy."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coyo.services.iab_taxonomy import (
    IABCategory,
    IABMatchResult,
    IABTaxonomyService,
)


@pytest.fixture()
def taxonomy_service() -> IABTaxonomyService:
    """Create a fresh IABTaxonomyService (loads real JSON)."""
    return IABTaxonomyService()


class TestTaxonomyLoading:
    def test_labels_exist(self, taxonomy_service: IABTaxonomyService) -> None:
        labels = taxonomy_service.get_all_labels()
        assert len(labels) > 0

    def test_labels_are_strings(self, taxonomy_service: IABTaxonomyService) -> None:
        labels = taxonomy_service.get_all_labels()
        assert all(isinstance(label, str) for label in labels)

    def test_labels_are_non_empty_strings(self, taxonomy_service: IABTaxonomyService) -> None:
        labels = taxonomy_service.get_all_labels()
        assert all(len(label) > 0 for label in labels)


class TestGetCategory:
    def test_returns_category_for_valid_id(self, taxonomy_service: IABTaxonomyService) -> None:
        cat = taxonomy_service.get_category("1")
        assert cat is not None
        assert isinstance(cat, IABCategory)
        assert cat.id == "1"
        assert cat.name == "Automotive"
        assert cat.tier == 1

    def test_returns_none_for_invalid_id(self, taxonomy_service: IABTaxonomyService) -> None:
        assert taxonomy_service.get_category("nonexistent") is None

    def test_subcategory_has_parent_id(self, taxonomy_service: IABTaxonomyService) -> None:
        cat = taxonomy_service.get_category("1.1")
        assert cat is not None
        assert cat.parent_id == "1"

    def test_top_level_has_no_parent(self, taxonomy_service: IABTaxonomyService) -> None:
        cat = taxonomy_service.get_category("1")
        assert cat is not None
        assert cat.parent_id is None


class TestGetAllLabels:
    def test_returns_list(self, taxonomy_service: IABTaxonomyService) -> None:
        labels = taxonomy_service.get_all_labels()
        assert isinstance(labels, list)

    def test_returns_copy_not_reference(self, taxonomy_service: IABTaxonomyService) -> None:
        labels1 = taxonomy_service.get_all_labels()
        labels2 = taxonomy_service.get_all_labels()
        assert labels1 is not labels2
        assert labels1 == labels2


class TestEnsureEmbeddings:
    @pytest.mark.asyncio()
    async def test_computes_embeddings_on_first_call(
        self, taxonomy_service: IABTaxonomyService,
    ) -> None:
        mock_embedding_service = AsyncMock()
        labels = taxonomy_service.get_all_labels()
        mock_embedding_service.embed = AsyncMock(
            return_value=[[0.1] * 3 for _ in labels],
        )

        await taxonomy_service.ensure_embeddings(mock_embedding_service)

        mock_embedding_service.embed.assert_awaited_once_with(labels)

    @pytest.mark.asyncio()
    async def test_skips_second_call(
        self, taxonomy_service: IABTaxonomyService,
    ) -> None:
        mock_embedding_service = AsyncMock()
        labels = taxonomy_service.get_all_labels()
        mock_embedding_service.embed = AsyncMock(
            return_value=[[0.1] * 3 for _ in labels],
        )

        await taxonomy_service.ensure_embeddings(mock_embedding_service)
        await taxonomy_service.ensure_embeddings(mock_embedding_service)

        # Only called once despite two ensure_embeddings calls
        assert mock_embedding_service.embed.await_count == 1


class TestMatch:
    def test_raises_if_embeddings_not_loaded(
        self, taxonomy_service: IABTaxonomyService,
    ) -> None:
        with pytest.raises(RuntimeError, match="ensure_embeddings"):
            taxonomy_service.match([1.0, 0.0, 0.0])

    def test_returns_normalize_above_normalize_threshold(self) -> None:
        service = IABTaxonomyService()
        # Manually set embeddings to control similarity
        # Use unit vectors: first label gets [1,0,0], rest get [0,1,0]
        n = len(service.get_all_labels())
        embeddings = [[0.0, 1.0, 0.0]] * n
        embeddings[0] = [1.0, 0.0, 0.0]  # first label
        service._label_embeddings = embeddings

        mock_settings = MagicMock()
        mock_settings.keyword_normalize_threshold = 0.90
        mock_settings.keyword_validate_threshold = 0.70

        with patch("coyo.services.iab_taxonomy.get_settings", return_value=mock_settings):
            result = service.match([1.0, 0.0, 0.0])

        assert result.action == "normalize"
        assert result.iab_id is not None
        assert result.iab_name is not None
        assert result.similarity == pytest.approx(1.0)

    def test_returns_valid_between_thresholds(self) -> None:
        service = IABTaxonomyService()
        n = len(service.get_all_labels())
        # All embeddings are somewhat similar but not very
        embeddings = [[0.0, 1.0, 0.0]] * n
        embeddings[0] = [0.8, 0.6, 0.0]  # cos sim with [1,0,0] ~ 0.8
        service._label_embeddings = embeddings

        mock_settings = MagicMock()
        mock_settings.keyword_normalize_threshold = 0.90
        mock_settings.keyword_validate_threshold = 0.70

        with patch("coyo.services.iab_taxonomy.get_settings", return_value=mock_settings):
            result = service.match([1.0, 0.0, 0.0])

        assert result.action == "valid"
        assert result.iab_id is None
        assert result.iab_name is None
        assert result.similarity > 0.70

    def test_returns_invalid_below_validate_threshold(self) -> None:
        service = IABTaxonomyService()
        n = len(service.get_all_labels())
        # All embeddings are orthogonal to query
        embeddings = [[0.0, 1.0, 0.0]] * n
        service._label_embeddings = embeddings

        mock_settings = MagicMock()
        mock_settings.keyword_normalize_threshold = 0.90
        mock_settings.keyword_validate_threshold = 0.70

        with patch("coyo.services.iab_taxonomy.get_settings", return_value=mock_settings):
            result = service.match([1.0, 0.0, 0.0])

        assert result.action == "invalid"
        assert result.iab_id is None
        assert result.iab_name is None
        assert result.similarity == pytest.approx(0.0)

    def test_result_is_iab_match_result(self) -> None:
        service = IABTaxonomyService()
        n = len(service.get_all_labels())
        embeddings = [[1.0, 0.0, 0.0]] * n
        service._label_embeddings = embeddings

        mock_settings = MagicMock()
        mock_settings.keyword_normalize_threshold = 0.90
        mock_settings.keyword_validate_threshold = 0.70

        with patch("coyo.services.iab_taxonomy.get_settings", return_value=mock_settings):
            result = service.match([1.0, 0.0, 0.0])

        assert isinstance(result, IABMatchResult)
