"""YAML test case loader."""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from eval.models import DedupPairSet, TestCase

if TYPE_CHECKING:
    from pathlib import Path


def load_test_cases(cases_dir: Path) -> list[TestCase]:
    """Load all test cases from YAML files in the given directory (recursive)."""
    cases: list[TestCase] = []
    for yaml_path in sorted(cases_dir.rglob("*.yaml")):
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            continue
        cases.append(TestCase.model_validate(data))
    return cases


def load_dedup_pairs(yaml_path: Path) -> DedupPairSet:
    """Load a dedup pair set from a single YAML file."""
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return DedupPairSet.model_validate(data)


def build_transcript_text(case: TestCase) -> str:
    """Build a plain-text transcript from a test case's turns.

    Matches the format used by MemoryExtractionService._build_transcript.
    """
    lines: list[str] = []
    for turn in case.transcript:
        label = "User" if turn.role == "user" else "AI"
        lines.append(f"{label}: {turn.text}")
    return "\n".join(lines)
