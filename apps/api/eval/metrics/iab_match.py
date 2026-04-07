"""IAB matching metrics for Eval B."""

from __future__ import annotations

import structlog

from eval.models import IABMatchResult, NormalizationAccuracyResult

logger = structlog.get_logger()


def compute_iab_match_metrics(
    processed_keywords: list[dict[str, object]],
    gold_iab_ids: list[str] | None = None,
) -> tuple[IABMatchResult, NormalizationAccuracyResult | None]:
    """Compute IAB Match Rate and optional Normalization Accuracy.

    Returns:
        A tuple of (IABMatchResult, NormalizationAccuracyResult or None).
    """
    category_keywords = [kw for kw in processed_keywords if kw.get("keyword_type") == "category"]
    total_category_count = len(category_keywords)

    if total_category_count == 0:
        return (
            IABMatchResult(
                iab_matched_count=0,
                total_category_count=0,
                iab_match_rate=0.0,
            ),
            None,
        )

    iab_matched_count = sum(1 for kw in category_keywords if kw.get("iab_category_id") is not None)
    iab_match_rate = iab_matched_count / total_category_count

    iab_result = IABMatchResult(
        iab_matched_count=iab_matched_count,
        total_category_count=total_category_count,
        iab_match_rate=iab_match_rate,
    )

    # -- Normalization accuracy against gold IAB IDs --------------------------
    norm_result: NormalizationAccuracyResult | None = None

    if gold_iab_ids is not None:
        gold_set = set(gold_iab_ids)
        predicted_iab_ids = [
            str(kw["iab_category_id"])
            for kw in category_keywords
            if kw.get("iab_category_id") is not None
        ]
        checked = len(predicted_iab_ids)
        correct = sum(1 for iab_id in predicted_iab_ids if iab_id in gold_set)
        accuracy = correct / checked if checked > 0 else None
        norm_result = NormalizationAccuracyResult(
            checked=checked,
            correct=correct,
            accuracy=accuracy,
        )

    logger.debug(
        "iab_match_computed",
        matched=iab_matched_count,
        total=total_category_count,
        rate=round(iab_match_rate, 4),
        normalization_accuracy=(
            round(norm_result.accuracy, 4)
            if norm_result and norm_result.accuracy is not None
            else None
        ),
    )

    return iab_result, norm_result
