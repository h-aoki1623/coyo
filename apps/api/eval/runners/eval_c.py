"""Evaluation C runner: Process C dedup accuracy."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from coyo.config import get_settings
from coyo.services.embedding import EmbeddingService
from eval.loader import load_dedup_pairs
from eval.metrics.dedup_accuracy import compute_dedup_accuracy

if TYPE_CHECKING:
    from eval.config import EvalConfig
    from eval.models import EvalCResult

logger = structlog.get_logger()


async def run_eval_c(config: EvalConfig) -> EvalCResult:
    """Run Evaluation C: measure dedup accuracy at the configured threshold.

    Loads should_merge and should_not_merge pair sets, embeds all keywords,
    and computes false merge / false split rates.

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
    threshold = settings.keyword_dedup_threshold

    embedding_service = EmbeddingService()

    logger.info(
        "eval_c_running",
        merge_pairs=len(should_merge_set.pairs),
        split_pairs=len(should_not_merge_set.pairs),
        threshold=threshold,
    )

    result = await compute_dedup_accuracy(
        should_merge=should_merge_set.pairs,
        should_not_merge=should_not_merge_set.pairs,
        threshold=threshold,
        embedding_service=embedding_service,
    )

    logger.info(
        "eval_c_complete",
        false_merge_rate=result.false_merge_rate,
        false_split_rate=result.false_split_rate,
    )

    return result
