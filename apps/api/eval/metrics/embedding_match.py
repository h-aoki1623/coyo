"""Precision / Recall / F1 via embedding similarity with bipartite matching."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog
from scipy.optimize import linear_sum_assignment

from coyo.services.similarity import cosine_similarity
from eval.models import KeywordMetrics

if TYPE_CHECKING:
    from coyo.services.embedding import EmbeddingService

logger = structlog.get_logger()


@dataclass(frozen=True)
class MatchDetail:
    """A single TP match with similarity score."""

    predicted: str
    gold: str
    similarity: float


@dataclass(frozen=True)
class MatchResult:
    """Full matching result with metrics and per-pair details."""

    metrics: KeywordMetrics
    tp_keywords: list[str]
    fp_keywords: list[str]
    fn_keywords: list[str]
    matched_pairs: list[MatchDetail]
    fn_gold_indices: list[int] = field(default_factory=list)


def _compute_prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Return (precision, recall, f1) from raw counts, handling division by zero."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


async def compute_keyword_metrics(
    predicted: list[str],
    gold: list[str],
    threshold: float,
    embedding_service: EmbeddingService,
) -> MatchResult:
    """Compute keyword extraction metrics using embedding-based bipartite matching.

    Returns a MatchResult with metrics, TP/FP/FN lists, and matched pair details.
    """
    # --- Edge cases -----------------------------------------------------------
    if not predicted and not gold:
        metrics = KeywordMetrics(precision=1.0, recall=1.0, f1=1.0)
        return MatchResult(metrics, [], [], [], [], fn_gold_indices=[])

    if not predicted:
        precision, recall, f1 = _compute_prf(tp=0, fp=0, fn=len(gold))
        metrics = KeywordMetrics(
            precision=precision,
            recall=recall,
            f1=f1,
            fn_count=len(gold),
        )
        return MatchResult(
            metrics,
            [],
            [],
            list(gold),
            [],
            fn_gold_indices=list(range(len(gold))),
        )

    if not gold:
        precision, recall, f1 = _compute_prf(tp=0, fp=len(predicted), fn=0)
        metrics = KeywordMetrics(
            precision=precision,
            recall=recall,
            f1=f1,
            fp_count=len(predicted),
        )
        return MatchResult(metrics, [], list(predicted), [], [], fn_gold_indices=[])

    # --- Embed all keywords in one batch call ---------------------------------
    all_texts = list(predicted) + list(gold)
    all_embeddings = await embedding_service.embed(all_texts)

    pred_embeddings = all_embeddings[: len(predicted)]
    gold_embeddings = all_embeddings[len(predicted) :]

    # --- Build similarity matrix (predicted x gold) ---------------------------
    n_pred = len(predicted)
    n_gold = len(gold)
    sim_matrix: list[list[float]] = []
    for i in range(n_pred):
        row: list[float] = []
        for j in range(n_gold):
            sim = cosine_similarity(pred_embeddings[i], gold_embeddings[j])
            row.append(sim if sim >= threshold else 0.0)
        sim_matrix.append(row)

    # --- Hungarian algorithm (maximize similarity => minimize negative) --------
    cost_matrix = [[-sim for sim in row] for row in sim_matrix]
    row_indices, col_indices = linear_sum_assignment(cost_matrix)

    # --- Classify matches -----------------------------------------------------
    matched_pred: set[int] = set()
    matched_gold: set[int] = set()
    tp_keywords: list[str] = []
    matched_pairs: list[MatchDetail] = []

    for r, c in zip(row_indices, col_indices, strict=False):
        if sim_matrix[r][c] >= threshold:
            matched_pred.add(int(r))
            matched_gold.add(int(c))
            tp_keywords.append(predicted[r])
            matched_pairs.append(
                MatchDetail(
                    predicted=predicted[r],
                    gold=gold[c],
                    similarity=sim_matrix[r][c],
                )
            )

    fp_keywords = [predicted[i] for i in range(n_pred) if i not in matched_pred]
    fn_indices = [j for j in range(n_gold) if j not in matched_gold]
    fn_keywords = [gold[j] for j in fn_indices]

    tp = len(tp_keywords)
    fp = len(fp_keywords)
    fn = len(fn_keywords)

    precision, recall, f1 = _compute_prf(tp, fp, fn)

    logger.debug(
        "keyword_metrics_computed",
        tp=tp,
        fp=fp,
        fn=fn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
    )

    metrics = KeywordMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        tp_count=tp,
        fp_count=fp,
        fn_count=fn,
    )
    return MatchResult(
        metrics,
        tp_keywords,
        fp_keywords,
        fn_keywords,
        matched_pairs,
        fn_gold_indices=fn_indices,
    )
