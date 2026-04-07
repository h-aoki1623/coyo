"""CLI entry point for the evaluation framework.

Usage:
    cd apps/api
    python -m eval run-a
    python -m eval run-b
    python -m eval run-c
    python -m eval run-all
    python -m eval run-a --dry-run
    python -m eval run-a --verbose
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import replace
from pathlib import Path

import structlog

from eval.config import EvalConfig, load_eval_config
from eval.loader import load_test_cases
from eval.report import (
    print_eval_a_summary,
    print_eval_b_summary,
    print_eval_c_summary,
    save_result,
)
from eval.runners import run_eval_a, run_eval_b, run_eval_c

logger = structlog.get_logger()


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="python -m eval",
        description="Keyword extraction evaluation framework",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Load test cases and validate schemas only"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print per-case details after the summary"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None, help="Override results output directory"
    )
    parser.add_argument(
        "--concurrency", type=int, default=None, help="Override concurrent LLM calls (default: 5)"
    )
    parser.add_argument(
        "--max-cases", type=int, default=None, help="Limit number of test cases (for quick checks)"
    )

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run-a", help="Run Evaluation A")
    sub.add_parser("run-b", help="Run Evaluation B")
    sub.add_parser("run-c", help="Run Evaluation C")
    sub.add_parser("run-all", help="Run all evaluations sequentially")
    return parser


def _apply_overrides(config: EvalConfig, args: argparse.Namespace) -> EvalConfig:
    """Return a new EvalConfig with CLI overrides applied."""
    overrides: dict[str, object] = {}
    if args.output_dir is not None:
        overrides["results_dir"] = args.output_dir
    if args.concurrency is not None:
        overrides["concurrency"] = args.concurrency
    if args.max_cases is not None:
        overrides["max_cases"] = args.max_cases
    if overrides:
        return replace(config, **overrides)  # type: ignore[arg-type]
    return config


def _handle_dry_run(config: EvalConfig) -> None:
    """Load and validate test cases without making any API calls."""
    cases = load_test_cases(config.cases_dir)
    print(f"Loaded {len(cases)} test case(s) from {config.cases_dir}")
    for case in cases:
        print(f"  - {case.id} ({case.domain}, {case.source})")
    print("Schema validation passed. No LLM calls made (--dry-run).")


def _print_verbose_details(result: object) -> None:
    """Print per-case details if the result has them."""
    details = getattr(result, "per_case_details", None)
    if not details:
        return
    print("\n### Per-Case Details")
    for detail in details:
        print(f"\n**{detail.case_id}** ({detail.domain})")
        print(f"  Predicted categories: {detail.predicted_categories}")
        print(f"  Gold categories:      {detail.gold_categories}")
        print(f"  Predicted entities:   {detail.predicted_entities}")
        print(f"  Gold entities:        {detail.gold_entities}")
        if detail.niche_keywords:
            print(f"  Niche keywords:       {detail.niche_keywords}")
        if detail.type_confused_keywords:
            print(f"  Type confused:        {detail.type_confused_keywords}")


async def _run_a(config: EvalConfig, verbose: bool) -> None:
    result = await run_eval_a(config)
    save_result(result, config.results_dir, "eval_a")
    print_eval_a_summary(result)
    if verbose:
        _print_verbose_details(result)


async def _run_b(config: EvalConfig, verbose: bool) -> None:
    result = await run_eval_b(config)
    save_result(result, config.results_dir, "eval_b")
    print_eval_b_summary(result)
    if verbose:
        _print_verbose_details(result)


async def _run_c(config: EvalConfig, verbose: bool) -> None:
    result = await run_eval_c(config)
    save_result(result, config.results_dir, "eval_c")
    print_eval_c_summary(result)


async def _run_all(config: EvalConfig, verbose: bool) -> None:
    await _run_a(config, verbose)
    await _run_b(config, verbose)
    await _run_c(config, verbose)


_COMMANDS = {
    "run-a": _run_a,
    "run-b": _run_b,
    "run-c": _run_c,
    "run-all": _run_all,
}


def main() -> None:
    """Parse arguments and dispatch to the appropriate runner."""
    parser = _build_parser()
    args = parser.parse_args()

    config = load_eval_config()
    config = _apply_overrides(config, args)

    if args.dry_run:
        _handle_dry_run(config)
        return

    handler = _COMMANDS[args.command]
    try:
        asyncio.run(handler(config, args.verbose))
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)
    except Exception as exc:
        logger.exception("eval_failed", command=args.command)
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
