"""Eval C: Dedup accuracy metrics (False Merge Rate / False Split Rate)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from coyo.services.similarity import cosine_similarity
from eval.models import DedupPair, EvalCResult, PairResult

if TYPE_CHECKING:
    from coyo.services.embedding import EmbeddingService

logger = structlog.get_logger()


async def compute_dedup_accuracy(
    should_merge: list[DedupPair],
    should_not_merge: list[DedupPair],
    threshold: float,
    embedding_service: EmbeddingService,
) -> EvalCResult:
    """Compute false merge rate and false split rate for dedup threshold.

    Args:
        should_merge: Pairs that represent the same concept (expected merge).
        should_not_merge: Pairs that are different concepts (expected split).
        threshold: Cosine similarity threshold for merging.
        embedding_service: Service to generate embeddings.

    Returns:
        EvalCResult with rates and per-pair details.
    """
    # Collect all unique keywords and build an index for batch embedding
    all_keywords: list[str] = []
    keyword_index: dict[str, int] = {}

    for pair in [*should_merge, *should_not_merge]:
        for kw in (pair.a, pair.b):
            if kw not in keyword_index:
                keyword_index[kw] = len(all_keywords)
                all_keywords.append(kw)

    logger.info(
        "embedding_keywords_for_dedup",
        unique_count=len(all_keywords),
        merge_pairs=len(should_merge),
        split_pairs=len(should_not_merge),
    )

    # Batch embed all unique keywords
    embeddings = await embedding_service.embed(all_keywords)

    # Evaluate each pair
    all_results: list[PairResult] = []
    false_merge_pairs: list[PairResult] = []
    false_split_pairs: list[PairResult] = []

    for pair in should_merge:
        sim = cosine_similarity(
            embeddings[keyword_index[pair.a]],
            embeddings[keyword_index[pair.b]],
        )
        actual_merge = sim >= threshold
        result = PairResult(
            a=pair.a,
            b=pair.b,
            similarity=round(sim, 4),
            expected_merge=True,
            actual_merge=actual_merge,
            correct=actual_merge,
        )
        all_results.append(result)
        if not actual_merge:
            false_split_pairs.append(result)

    for pair in should_not_merge:
        sim = cosine_similarity(
            embeddings[keyword_index[pair.a]],
            embeddings[keyword_index[pair.b]],
        )
        actual_merge = sim >= threshold
        result = PairResult(
            a=pair.a,
            b=pair.b,
            similarity=round(sim, 4),
            expected_merge=False,
            actual_merge=actual_merge,
            correct=not actual_merge,
        )
        all_results.append(result)
        if actual_merge:
            false_merge_pairs.append(result)

    merge_count = len(should_merge)
    split_count = len(should_not_merge)
    false_merge_rate = len(false_merge_pairs) / split_count if split_count else 0.0
    false_split_rate = len(false_split_pairs) / merge_count if merge_count else 0.0

    logger.info(
        "dedup_accuracy_computed",
        threshold=threshold,
        false_merge_rate=round(false_merge_rate, 4),
        false_split_rate=round(false_split_rate, 4),
        false_merges=len(false_merge_pairs),
        false_splits=len(false_split_pairs),
    )

    return EvalCResult(
        timestamp=datetime.now(UTC).isoformat(),
        threshold_used=threshold,
        false_merge_rate=round(false_merge_rate, 4),
        false_split_rate=round(false_split_rate, 4),
        merge_pair_count=merge_count,
        split_pair_count=split_count,
        false_merge_pairs=false_merge_pairs,
        false_split_pairs=false_split_pairs,
        all_results=all_results,
    )
