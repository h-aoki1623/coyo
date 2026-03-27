"""Unit tests for coyo.services.similarity."""

from __future__ import annotations

import math

import pytest

from coyo.services.similarity import cosine_similarity, find_best_match, find_duplicates


class TestCosineSimilarity:
    def test_identical_vectors_returns_one(self) -> None:
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_returns_zero(self) -> None:
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors_returns_negative_one(self) -> None:
        a = [1.0, 0.0, 0.0]
        b = [-1.0, 0.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector_a_returns_zero(self) -> None:
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert cosine_similarity(a, b) == 0.0

    def test_zero_vector_b_returns_zero(self) -> None:
        a = [1.0, 2.0, 3.0]
        b = [0.0, 0.0, 0.0]
        assert cosine_similarity(a, b) == 0.0

    def test_both_zero_vectors_returns_zero(self) -> None:
        a = [0.0, 0.0]
        b = [0.0, 0.0]
        assert cosine_similarity(a, b) == 0.0

    def test_similar_vectors_returns_high_similarity(self) -> None:
        a = [1.0, 0.0, 0.0]
        b = [0.99, 0.1, 0.0]
        result = cosine_similarity(a, b)
        assert result > 0.99

    def test_unit_vectors_45_degrees(self) -> None:
        a = [1.0, 0.0]
        b = [math.cos(math.pi / 4), math.sin(math.pi / 4)]
        assert cosine_similarity(a, b) == pytest.approx(math.cos(math.pi / 4))

    def test_single_dimension(self) -> None:
        assert cosine_similarity([3.0], [5.0]) == pytest.approx(1.0)

    def test_negative_single_dimension(self) -> None:
        assert cosine_similarity([3.0], [-5.0]) == pytest.approx(-1.0)


class TestFindBestMatch:
    def test_finds_most_similar_candidate(self) -> None:
        query = [1.0, 0.0, 0.0]
        candidates = [
            [0.0, 1.0, 0.0],  # orthogonal
            [0.99, 0.1, 0.0],  # very similar
            [0.5, 0.5, 0.0],  # moderate
        ]
        idx, sim = find_best_match(query, candidates)
        assert idx == 1
        assert sim > 0.99

    def test_single_candidate(self) -> None:
        query = [1.0, 0.0]
        candidates = [[0.0, 1.0]]
        idx, sim = find_best_match(query, candidates)
        assert idx == 0
        assert sim == pytest.approx(0.0)

    def test_exact_match_among_candidates(self) -> None:
        query = [0.0, 1.0, 0.0]
        candidates = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],  # exact match
            [0.0, 0.0, 1.0],
        ]
        idx, sim = find_best_match(query, candidates)
        assert idx == 1
        assert sim == pytest.approx(1.0)

    def test_raises_on_empty_candidates(self) -> None:
        with pytest.raises(ValueError, match="candidates must not be empty"):
            find_best_match([1.0, 0.0], [])


class TestFindDuplicates:
    def test_finds_pairs_above_threshold(self) -> None:
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.99, 0.1, 0.0],  # very similar to index 0
            [0.0, 1.0, 0.0],  # orthogonal to both
        ]
        pairs = find_duplicates(embeddings, threshold=0.95)
        assert len(pairs) == 1
        i, j, sim = pairs[0]
        assert i == 0
        assert j == 1
        assert sim > 0.95

    def test_returns_empty_below_threshold(self) -> None:
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
        pairs = find_duplicates(embeddings, threshold=0.5)
        assert pairs == []

    def test_empty_input(self) -> None:
        assert find_duplicates([], threshold=0.5) == []

    def test_single_embedding(self) -> None:
        assert find_duplicates([[1.0, 0.0]], threshold=0.5) == []

    def test_all_identical(self) -> None:
        embeddings = [[1.0, 0.0]] * 3
        pairs = find_duplicates(embeddings, threshold=0.99)
        # 3 choose 2 = 3 pairs
        assert len(pairs) == 3
        for _i, _j, sim in pairs:
            assert sim == pytest.approx(1.0)

    def test_pair_indices_are_ordered(self) -> None:
        embeddings = [[1.0, 0.0], [1.0, 0.0]]
        pairs = find_duplicates(embeddings, threshold=0.5)
        for i, j, _sim in pairs:
            assert i < j
