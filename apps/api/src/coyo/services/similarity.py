"""Vector similarity utilities for keyword deduplication and matching."""

from __future__ import annotations

import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Returns a value in [-1, 1]. Returns 0.0 if either vector is zero.
    """
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0
    return dot / (norm_a * norm_b)


def find_best_match(
    query: list[float],
    candidates: list[list[float]],
) -> tuple[int, float]:
    """Find the candidate most similar to the query.

    Returns (index, similarity) of the best match.
    Raises ValueError if candidates is empty.
    """
    if not candidates:
        raise ValueError("candidates must not be empty")

    best_idx = 0
    best_sim = cosine_similarity(query, candidates[0])
    for i in range(1, len(candidates)):
        sim = cosine_similarity(query, candidates[i])
        if sim > best_sim:
            best_sim = sim
            best_idx = i
    return best_idx, best_sim


def find_duplicates(
    embeddings: list[list[float]],
    threshold: float,
) -> list[tuple[int, int, float]]:
    """Find all pairs of embeddings with similarity >= threshold.

    Returns a list of (i, j, similarity) tuples where i < j.
    """
    pairs: list[tuple[int, int, float]] = []
    n = len(embeddings)
    for i in range(n):
        for j in range(i + 1, n):
            sim = cosine_similarity(embeddings[i], embeddings[j])
            if sim >= threshold:
                pairs.append((i, j, sim))
    return pairs
