"""Report generation for evaluation results."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from pathlib import Path

    from eval.models import EvalAResult, EvalBResult, EvalCResult

logger = structlog.get_logger()


def save_result(
    result: EvalAResult | EvalBResult | EvalCResult,
    output_dir: Path,
    prefix: str,
) -> Path:
    """Save an evaluation result as JSON.

    Creates output_dir if it does not exist.  Returns the path to the
    written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H-%M-%S")
    filename = f"{prefix}_{timestamp}.json"
    filepath = output_dir / filename

    filepath.write_text(
        json.dumps(result.model_dump(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    logger.info("result_saved", path=str(filepath))
    return filepath


# ---------------------------------------------------------------------------
# Eval A summary
# ---------------------------------------------------------------------------


def print_eval_a_summary(result: EvalAResult) -> None:
    """Print a Markdown-formatted summary of Eval A results to stdout."""
    print()
    print("## Evaluation A -- LLM Raw Output Quality")
    print()
    print(
        f"Model: {result.model} | "
        f"Test cases: {result.test_case_count} | "
        f"Timestamp: {result.timestamp}"
    )

    _print_category_metrics(result)
    _print_entity_metrics(result)
    _print_news_relevant(result)


# ---------------------------------------------------------------------------
# Eval B summary
# ---------------------------------------------------------------------------


def print_eval_b_summary(result: EvalBResult) -> None:
    """Print a Markdown-formatted summary of Eval B results to stdout."""
    print()
    print("## Evaluation B -- End-to-End Pipeline Quality")
    print()
    print(
        f"Model: {result.model} | "
        f"Test cases: {result.test_case_count} | "
        f"Timestamp: {result.timestamp}"
    )

    _print_category_metrics(result)
    _print_entity_metrics(result)
    _print_news_relevant(result)

    # IAB matching is inside category_metrics for Eval B
    iab = result.category_metrics.iab_match
    if iab is not None:
        print()
        print("### IAB Matching (Pipeline-specific)")
        print("| Metric | Value |")
        print("|--------|-------|")
        print(f"| IAB Match Rate | {_pct(iab.iab_match_rate)} |")
        norm = result.category_metrics.normalization_accuracy
        if norm is not None and norm.accuracy is not None:
            print(f"| Normalization Accuracy | {_pct(norm.accuracy)} |")


# ---------------------------------------------------------------------------
# Eval C summary
# ---------------------------------------------------------------------------


def print_eval_c_summary(result: EvalCResult) -> None:
    """Print a Markdown-formatted summary of Eval C results to stdout."""
    print()
    print("## Evaluation C -- Process C Dedup Accuracy")
    print()
    print(
        f"Threshold: {result.threshold_used:.2f} | "
        f"Merge pairs: {result.merge_pair_count} | "
        f"Split pairs: {result.split_pair_count}"
    )
    print()
    print("| Metric | Value | Target |")
    print("|--------|-------|--------|")
    print(f"| False Merge Rate | {_pct(result.false_merge_rate)} | < 2% |")
    print(f"| False Split Rate | {_pct(result.false_split_rate)} | < 10% |")

    if result.false_merge_pairs:
        print()
        print("### False Merges (should NOT have merged)")
        print("| Pair A | Pair B | Similarity |")
        print("|--------|--------|-----------|")
        for pair in result.false_merge_pairs:
            print(f"| {pair.a} | {pair.b} | {pair.similarity:.2f} |")

    if result.false_split_pairs:
        print()
        print("### False Splits (should have merged)")
        print("| Pair A | Pair B | Similarity |")
        print("|--------|--------|-----------|")
        for pair in result.false_split_pairs:
            print(f"| {pair.a} | {pair.b} | {pair.similarity:.2f} |")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _pct(value: float) -> str:
    """Format a 0-1 float as a percentage string (e.g. '85.0%')."""
    return f"{value * 100:.1f}%"


def _fmt(value: float) -> str:
    """Format a 0-1 float to two decimal places (e.g. '0.85')."""
    return f"{value:.2f}"


def _print_category_metrics(result: EvalAResult | EvalBResult) -> None:
    """Print the Category Metrics table."""
    cat = result.category_metrics
    print()
    print("### Category Metrics")
    print("| Metric | Value |")
    print("|--------|-------|")
    print(f"| Precision | {_fmt(cat.precision)} |")
    print(f"| Recall | {_fmt(cat.recall)} |")
    print(f"| F1 | {_fmt(cat.f1)} |")
    niche = getattr(cat, "niche_rate", None)
    if niche is not None and niche.total_count > 0:
        print(f"| Niche Rate | {_pct(niche.niche_rate)} |")


def _print_entity_metrics(result: EvalAResult | EvalBResult) -> None:
    """Print the Entity Metrics table."""
    ent = result.entity_metrics
    print()
    print("### Entity Metrics")
    print("| Metric | Value |")
    print("|--------|-------|")
    print(f"| Precision | {_fmt(ent.precision)} |")
    print(f"| Recall | {_fmt(ent.recall)} |")
    print(f"| F1 | {_fmt(ent.f1)} |")
    print(f"| Type Confusion | {_pct(ent.type_confusion.type_confusion_rate)} |")
    print(f"| Wikidata Hit Rate | {_pct(ent.wikidata_hit.wikidata_hit_rate)} |")


def _print_news_relevant(result: EvalAResult | EvalBResult) -> None:
    """Print the is_news_relevant table."""
    nr = result.news_relevant
    print()
    print("### is_news_relevant")
    print("|  | Precision | Recall | F1 |")
    print("|--|-----------|--------|-----|")
    print(
        f"| Category | {_fmt(nr.category.precision)} "
        f"| {_fmt(nr.category.recall)} | {_fmt(nr.category.f1)} |"
    )
    print(
        f"| Entity | {_fmt(nr.entity.precision)} "
        f"| {_fmt(nr.entity.recall)} | {_fmt(nr.entity.f1)} |"
    )
    print(
        f"| Overall | {_fmt(nr.overall.precision)} "
        f"| {_fmt(nr.overall.recall)} | {_fmt(nr.overall.f1)} |"
    )
