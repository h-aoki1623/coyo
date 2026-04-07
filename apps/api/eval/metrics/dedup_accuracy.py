"""Eval C: Dedup accuracy metrics (False Merge Rate / False Split Rate)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from coyo.services.similarity import cosine_similarity
from coyo.services.synonym_judge import (
    build_synonym_system_message,
    judge_synonym_pair,
)
from eval.models import DedupPair, EvalCResult, PairResult

if TYPE_CHECKING:
    from coyo.services.embedding import EmbeddingService
    from coyo.services.llm.openai_client import OpenAIClient

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


async def compute_dedup_accuracy_hybrid(
    should_merge: list[DedupPair],
    should_not_merge: list[DedupPair],
    dedup_threshold: float,
    candidate_threshold: float,
    embedding_service: EmbeddingService,
    llm: OpenAIClient,
) -> EvalCResult:
    """Compute dedup accuracy using the hybrid embedding + LLM approach.

    Mirrors production Process C logic:
    1. similarity >= dedup_threshold -> auto-merge (no LLM).
    2. candidate_threshold <= similarity < dedup_threshold -> LLM confirmation.
    3. similarity < candidate_threshold -> no merge (no LLM).
    """
    # Collect unique keywords for batched embedding
    all_keywords: list[str] = []
    keyword_index: dict[str, int] = {}
    for pair in [*should_merge, *should_not_merge]:
        for kw in (pair.a, pair.b):
            if kw not in keyword_index:
                keyword_index[kw] = len(all_keywords)
                all_keywords.append(kw)

    logger.info(
        "embedding_keywords_for_dedup_hybrid",
        unique_count=len(all_keywords),
        merge_pairs=len(should_merge),
        split_pairs=len(should_not_merge),
    )

    embeddings = await embedding_service.embed(all_keywords)
    system_message = build_synonym_system_message()

    # Classify each pair by similarity and collect those that need LLM.
    @dataclass
    class _Staged:
        pair: DedupPair
        expected_merge: bool
        similarity: float
        auto_merge: bool  # True when sim >= dedup_threshold
        needs_llm: bool  # True when candidate_threshold <= sim < dedup_threshold

    staged: list[_Staged] = []
    for pair, expected_merge in [
        *((p, True) for p in should_merge),
        *((p, False) for p in should_not_merge),
    ]:
        sim = cosine_similarity(
            embeddings[keyword_index[pair.a]],
            embeddings[keyword_index[pair.b]],
        )
        staged.append(
            _Staged(
                pair=pair,
                expected_merge=expected_merge,
                similarity=sim,
                auto_merge=sim >= dedup_threshold,
                needs_llm=candidate_threshold <= sim < dedup_threshold,
            )
        )

    # Run all candidate-zone LLM judgments in parallel.
    llm_indices = [i for i, s in enumerate(staged) if s.needs_llm]
    judgments: dict[int, tuple[bool, str | None]] = {}
    if llm_indices:
        tasks = [
            judge_synonym_pair(llm, system_message, staged[i].pair.a, staged[i].pair.b)
            for i in llm_indices
        ]
        results = await asyncio.gather(*tasks)
        for i, judgment in zip(llm_indices, results, strict=True):
            if judgment is None:
                judgments[i] = (False, "llm_error")
            else:
                judgments[i] = (judgment.is_synonym, judgment.reason)

    all_results: list[PairResult] = []
    false_merge_pairs: list[PairResult] = []
    false_split_pairs: list[PairResult] = []

    for i, s in enumerate(staged):
        llm_invoked = s.needs_llm
        if s.auto_merge:
            actual_merge = True
            llm_reason: str | None = None
        elif s.needs_llm:
            actual_merge, llm_reason = judgments[i]
        else:
            actual_merge = False
            llm_reason = None

        result = PairResult(
            a=s.pair.a,
            b=s.pair.b,
            similarity=round(s.similarity, 4),
            expected_merge=s.expected_merge,
            actual_merge=actual_merge,
            correct=(actual_merge == s.expected_merge),
            llm_invoked=llm_invoked,
            llm_reason=llm_reason,
        )
        all_results.append(result)
        if s.expected_merge and not actual_merge:
            false_split_pairs.append(result)
        elif not s.expected_merge and actual_merge:
            false_merge_pairs.append(result)

    merge_count = len(should_merge)
    split_count = len(should_not_merge)
    false_merge_rate = len(false_merge_pairs) / split_count if split_count else 0.0
    false_split_rate = len(false_split_pairs) / merge_count if merge_count else 0.0

    logger.info(
        "dedup_accuracy_hybrid_computed",
        dedup_threshold=dedup_threshold,
        candidate_threshold=candidate_threshold,
        false_merge_rate=round(false_merge_rate, 4),
        false_split_rate=round(false_split_rate, 4),
        false_merges=len(false_merge_pairs),
        false_splits=len(false_split_pairs),
        llm_invocations=sum(1 for r in all_results if r.llm_invoked),
    )

    return EvalCResult(
        timestamp=datetime.now(UTC).isoformat(),
        threshold_used=dedup_threshold,
        candidate_threshold_used=candidate_threshold,
        false_merge_rate=round(false_merge_rate, 4),
        false_split_rate=round(false_split_rate, 4),
        merge_pair_count=merge_count,
        split_pair_count=split_count,
        false_merge_pairs=false_merge_pairs,
        false_split_pairs=false_split_pairs,
        all_results=all_results,
    )
