"""Evaluation C runner: Process C dedup accuracy (hybrid LLM approach)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from coyo.config import get_settings
from coyo.services.embedding import EmbeddingService
from coyo.services.llm.openai_client import OpenAIClient
from eval.loader import load_dedup_pairs
from eval.metrics.dedup_accuracy import compute_dedup_accuracy_hybrid

if TYPE_CHECKING:
    from eval.config import EvalConfig
    from eval.models import EvalCResult

logger = structlog.get_logger()


async def run_eval_c(config: EvalConfig) -> EvalCResult:
    """Run Evaluation C: measure dedup accuracy with the hybrid approach.

    Loads should_merge and should_not_merge pair sets and evaluates them
    using the same two-stage (embedding + LLM) logic as production Process C:
    pairs above the dedup threshold auto-merge, pairs in the candidate zone
    are confirmed by an LLM, and pairs below the candidate threshold are
    treated as new.

    Args:
        config: Evaluation configuration with paths and settings.

    Returns:
        EvalCResult with accuracy metrics and per-pair details.
    """
    should_merge_path = config.dedup_pairs_dir / "should_merge.yaml"
    should_not_merge_path = config.dedup_pairs_dir / "should_not_merge.yaml"

    logger.info(
        "eval_c_loading_pairs",
        merge_path=str(should_merge_path),
        split_path=str(should_not_merge_path),
    )

    should_merge_set = load_dedup_pairs(should_merge_path)
    should_not_merge_set = load_dedup_pairs(should_not_merge_path)

    settings = get_settings()
    dedup_threshold = settings.keyword_dedup_threshold
    candidate_threshold = settings.keyword_dedup_candidate_threshold

    embedding_service = EmbeddingService()
    llm = OpenAIClient(model=settings.llm_interest_model)

    logger.info(
        "eval_c_running",
        merge_pairs=len(should_merge_set.pairs),
        split_pairs=len(should_not_merge_set.pairs),
        dedup_threshold=dedup_threshold,
        candidate_threshold=candidate_threshold,
    )

    result = await compute_dedup_accuracy_hybrid(
        should_merge=should_merge_set.pairs,
        should_not_merge=should_not_merge_set.pairs,
        dedup_threshold=dedup_threshold,
        candidate_threshold=candidate_threshold,
        embedding_service=embedding_service,
        llm=llm,
    )

    logger.info(
        "eval_c_complete",
        false_merge_rate=result.false_merge_rate,
        false_split_rate=result.false_split_rate,
    )

    return result
