"""Evaluation-specific settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_EVAL_ROOT = Path(__file__).resolve().parent
_DATA_DIR = _EVAL_ROOT / "data"
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


@dataclass(frozen=True)
class EvalConfig:
    """Configuration for evaluation runs.

    Production settings (OPENAI_API_KEY, model thresholds) are loaded from
    coyo.config.get_settings() which reads the .env file.
    This config only manages eval-specific settings.
    """

    # LLM-as-judge (Anthropic)
    anthropic_api_key: str = ""
    judge_model: str = "claude-haiku-4-5-20251001"

    # Concurrency
    concurrency: int = 5

    # Limit number of test cases (0 = no limit)
    max_cases: int = 0

    # Paths
    data_dir: Path = _DATA_DIR
    cases_dir: Path = field(default_factory=lambda: _DATA_DIR / "cases")
    dedup_pairs_dir: Path = field(default_factory=lambda: _DATA_DIR / "dedup_pairs")
    wikidata_dir: Path = field(default_factory=lambda: _DATA_DIR / "wikidata")
    cache_dir: Path = field(default_factory=lambda: _DATA_DIR / ".cache")
    results_dir: Path = field(default_factory=lambda: _EVAL_ROOT / "results")

    # Matching thresholds for P/R/F1 computation
    category_match_threshold: float = 0.90
    entity_match_threshold: float = 0.85

    # Wikidata lookup threshold
    wikidata_match_threshold: float = 0.85


def _read_env_value(key: str) -> str:
    """Read a value from os.environ, falling back to .env file.

    Unlike a full dotenv loader, this only reads the specific key requested
    without injecting all .env values into os.environ. This avoids conflicts
    with pydantic-settings which validates extra environment variables.
    """
    value = os.environ.get(key, "")
    if value:
        return value

    if not _ENV_PATH.exists():
        return ""

    for line in _ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        env_key, _, env_value = line.partition("=")
        if env_key.strip() == key:
            return env_value.strip().strip("\"'")

    return ""


def load_eval_config() -> EvalConfig:
    """Load evaluation config from environment variables and .env file."""
    return EvalConfig(
        anthropic_api_key=_read_env_value("ANTHROPIC_API_KEY"),
        judge_model=_read_env_value("EVAL_JUDGE_MODEL") or "claude-haiku-4-5-20251001",
        concurrency=int(_read_env_value("EVAL_CONCURRENCY") or "5"),
    )
