"""Compute is_news_relevant classification metrics with confusion matrix."""

from __future__ import annotations

import structlog

from eval.models import ConfusionMatrix, NewsRelevantByType, NewsRelevantResult

logger = structlog.get_logger()


def _metrics_from_confusion(cm: ConfusionMatrix) -> NewsRelevantResult:
    """Derive precision, recall, and F1 from a confusion matrix."""
    tp, fp, fn = cm.tp, cm.fp, cm.fn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return NewsRelevantResult(
        precision=precision,
        recall=recall,
        f1=f1,
        confusion=cm,
    )


def _classify(predicted: bool, gold: bool) -> str:
    """Return the confusion matrix bucket for a single observation."""
    if predicted and gold:
        return "tp"
    if predicted and not gold:
        return "fp"
    if not predicted and gold:
        return "fn"
    return "tn"


def compute_news_relevant_metrics(
    predicted_keywords: list[dict[str, object]],
    gold_keywords: list[dict[str, object]],
    matched_pairs: list[tuple[str, str]],
) -> NewsRelevantByType:
    """Compute is_news_relevant metrics for matched keyword pairs.

    Args:
        predicted_keywords: List of dicts with keys
            ``keyword``, ``is_news_relevant``, ``keyword_type``.
        gold_keywords: Same structure as *predicted_keywords*.
        matched_pairs: (predicted_keyword, gold_keyword) string pairs
            that were matched during embedding-based TP matching.

    Returns:
        ``NewsRelevantByType`` containing per-type and overall results.
    """
    pred_lookup: dict[str, dict[str, object]] = {
        str(kw["keyword"]): kw for kw in predicted_keywords
    }
    gold_lookup: dict[str, dict[str, object]] = {str(kw["keyword"]): kw for kw in gold_keywords}

    # Accumulate counts in plain dicts (immutable — no Pydantic mutation)
    buckets: dict[str, dict[str, int]] = {
        "category": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        "entity": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
    }
    overall: dict[str, int] = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}

    for pred_kw, gold_kw in matched_pairs:
        pred_entry = pred_lookup.get(pred_kw)
        gold_entry = gold_lookup.get(gold_kw)

        if pred_entry is None or gold_entry is None:
            logger.warning(
                "news_relevant_lookup_miss",
                pred_kw=pred_kw,
                gold_kw=gold_kw,
                pred_found=pred_entry is not None,
                gold_found=gold_entry is not None,
            )
            continue

        pred_flag = bool(pred_entry.get("is_news_relevant", False))
        gold_flag = bool(gold_entry.get("is_news_relevant", False))
        kw_type = str(gold_entry.get("keyword_type", "entity"))
        bucket_key = _classify(pred_flag, gold_flag)

        bucket = buckets.get(kw_type)
        if bucket is None:
            logger.warning("unknown_keyword_type", keyword_type=kw_type)
            bucket = buckets.setdefault(kw_type, {"tp": 0, "fp": 0, "fn": 0, "tn": 0})

        bucket[bucket_key] += 1
        overall[bucket_key] += 1

    category_result = _metrics_from_confusion(ConfusionMatrix(**buckets["category"]))
    entity_result = _metrics_from_confusion(ConfusionMatrix(**buckets["entity"]))
    overall_result = _metrics_from_confusion(ConfusionMatrix(**overall))

    logger.debug(
        "news_relevant_metrics_computed",
        category=category_result.model_dump(),
        entity=entity_result.model_dump(),
        overall=overall_result.model_dump(),
    )

    return NewsRelevantByType(
        category=category_result,
        entity=entity_result,
        overall=overall_result,
    )
