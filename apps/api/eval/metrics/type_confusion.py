"""Compute keyword type confusion rate (entity vs. category misclassification)."""

from __future__ import annotations

import structlog

from eval.models import TypeConfusionResult

logger = structlog.get_logger()


def compute_type_confusion(
    predicted_keywords: list[dict[str, object]],
    gold_keywords: list[dict[str, object]],
    matched_pairs: list[tuple[str, str]],
) -> TypeConfusionResult:
    """Compute the type confusion rate for matched keyword pairs.

    For each matched (predicted, gold) pair, compare the ``keyword_type``
    field. If they differ (e.g. gold says "entity" but predicted says
    "category"), the pair is counted as a type confusion.

    Args:
        predicted_keywords: List of dicts with keys
            ``keyword``, ``is_news_relevant``, ``keyword_type``.
        gold_keywords: Same structure as *predicted_keywords*.
        matched_pairs: (predicted_keyword, gold_keyword) string pairs
            from embedding-based TP matching.

    Returns:
        ``TypeConfusionResult`` with confused count, total, and rate.
    """
    pred_lookup: dict[str, dict[str, object]] = {
        str(kw["keyword"]): kw for kw in predicted_keywords
    }
    gold_lookup: dict[str, dict[str, object]] = {str(kw["keyword"]): kw for kw in gold_keywords}

    confused_count = 0
    total_count = 0

    for pred_kw, gold_kw in matched_pairs:
        pred_entry = pred_lookup.get(pred_kw)
        gold_entry = gold_lookup.get(gold_kw)

        if pred_entry is None or gold_entry is None:
            logger.warning(
                "type_confusion_lookup_miss",
                pred_kw=pred_kw,
                gold_kw=gold_kw,
                pred_found=pred_entry is not None,
                gold_found=gold_entry is not None,
            )
            continue

        total_count += 1
        pred_type = str(pred_entry.get("keyword_type", ""))
        gold_type = str(gold_entry.get("keyword_type", ""))

        if pred_type != gold_type:
            confused_count += 1
            logger.debug(
                "type_confused_pair",
                predicted=pred_kw,
                gold=gold_kw,
                pred_type=pred_type,
                gold_type=gold_type,
            )

    rate = confused_count / total_count if total_count > 0 else 0.0

    logger.debug(
        "type_confusion_computed",
        confused=confused_count,
        total=total_count,
        rate=round(rate, 4),
    )

    return TypeConfusionResult(
        confused_count=confused_count,
        total_count=total_count,
        type_confusion_rate=rate,
    )
