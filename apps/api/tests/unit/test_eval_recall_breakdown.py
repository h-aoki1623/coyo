"""Unit tests for RecallBreakdown model and _compute_recall_breakdown function.

The eval.runners.eval_a module has heavy transitive dependencies (anthropic,
scipy, etc.) that are not installed in the dev venv. We extract the pure
function logic inline to test it in isolation, and a drift-detection test
ensures the inline copy stays in sync with the source.
"""

from __future__ import annotations

import inspect
from typing import Literal

import pytest
from pydantic import ValidationError

from eval.models import GoldKeyword, KeywordMetrics, RecallBreakdown

MentionType = Literal["explicit", "implicit"]

# ---------------------------------------------------------------------------
# Inline copy of _compute_recall_breakdown for testing without heavy imports.
# A drift-detection test below ensures this stays in sync with the source.
# ---------------------------------------------------------------------------


def _compute_recall_breakdown(
    mention_types: list[Literal["explicit", "implicit"]],
    fn_gold_indices: list[int],
) -> RecallBreakdown:
    """Compute recall split by mention type using match results."""
    explicit_total = 0
    implicit_total = 0
    explicit_tp = 0
    implicit_tp = 0

    fn_set = set(fn_gold_indices)
    for i, mt in enumerate(mention_types):
        if mt == "explicit":
            explicit_total += 1
            if i not in fn_set:
                explicit_tp += 1
        else:
            implicit_total += 1
            if i not in fn_set:
                implicit_tp += 1

    total = explicit_total + implicit_total
    total_recall = (explicit_tp + implicit_tp) / total if total > 0 else 1.0
    explicit_recall = explicit_tp / explicit_total if explicit_total > 0 else 1.0
    implicit_recall = implicit_tp / implicit_total if implicit_total > 0 else 1.0

    return RecallBreakdown(
        total=total_recall,
        explicit=explicit_recall,
        implicit=implicit_recall,
        explicit_tp=explicit_tp,
        explicit_total=explicit_total,
        implicit_tp=implicit_tp,
        implicit_total=implicit_total,
    )


# ---------------------------------------------------------------------------
# Drift detection helpers
# ---------------------------------------------------------------------------


def _extract_function_code(source: str, func_name: str) -> str:
    """Extract the executable code body of a function from source text.

    Strips signature, docstring, comments, and blank lines to produce
    a normalized form suitable for equality comparison.
    """
    lines = source.split("\n")

    # Find function start
    start_idx = None
    for i, line in enumerate(lines):
        if func_name in line and line.strip().startswith("def "):
            start_idx = i
            break
    assert start_idx is not None, f"{func_name} not found in source"

    # Collect the full function body (indented lines after the def)
    func_lines: list[str] = []
    for line in lines[start_idx + 1 :]:
        stripped = line.strip()
        # Stop at next top-level definition or non-indented non-blank line
        if line and not line[0].isspace() and stripped:
            break
        func_lines.append(line)

    # Skip past the docstring and return only executable code
    code_lines: list[str] = []
    in_docstring = False
    past_docstring = False
    for line in func_lines:
        stripped = line.strip()
        if not past_docstring:
            if in_docstring:
                if '"""' in stripped:
                    in_docstring = False
                    past_docstring = True
                continue
            if stripped.startswith('"""'):
                in_docstring = True
                if stripped.count('"""') >= 2:
                    in_docstring = False
                    past_docstring = True
                continue
            # Skip blank/comment lines before docstring
            if not stripped or stripped.startswith("#"):
                continue
            # Code before any docstring means no docstring
            past_docstring = True
        if not stripped or stripped.startswith("#"):
            continue
        code_lines.append(stripped)

    return "\n".join(code_lines)


# ===========================================================================
# Drift detection test
# ===========================================================================


class TestSourceDrift:
    """Guard against the inline copy drifting from the actual source."""

    def test_inline_copy_matches_source(self) -> None:
        with open("eval/runners/eval_a.py") as f:
            source_text = f.read()

        inline_text = inspect.getsource(_compute_recall_breakdown)

        source_code = _extract_function_code(
            source_text,
            "_compute_recall_breakdown",
        )
        inline_code = _extract_function_code(
            inline_text,
            "_compute_recall_breakdown",
        )

        assert source_code == inline_code, (
            "Inline copy of _compute_recall_breakdown has drifted "
            "from eval_a.py source. "
            "Update the inline copy in test_eval_recall_breakdown.py."
        )


# ===========================================================================
# Model tests
# ===========================================================================


class TestGoldKeywordMentionType:
    """Tests for GoldKeyword.mention_type field."""

    def test_defaults_to_explicit(self) -> None:
        gk = GoldKeyword(
            keyword="AI",
            is_news_relevant=True,
            keyword_type="category",
        )
        assert gk.mention_type == "explicit"

    def test_accepts_explicit(self) -> None:
        gk = GoldKeyword(
            keyword="AI",
            is_news_relevant=True,
            keyword_type="category",
            mention_type="explicit",
        )
        assert gk.mention_type == "explicit"

    def test_accepts_implicit(self) -> None:
        gk = GoldKeyword(
            keyword="AI",
            is_news_relevant=True,
            keyword_type="category",
            mention_type="implicit",
        )
        assert gk.mention_type == "implicit"

    def test_rejects_invalid_mention_type(self) -> None:
        with pytest.raises(ValidationError):
            GoldKeyword(
                keyword="AI",
                is_news_relevant=True,
                keyword_type="category",
                mention_type="unknown",
            )


class TestRecallBreakdownModel:
    """Tests for RecallBreakdown model serialization and defaults."""

    def test_creation_with_all_fields(self) -> None:
        rb = RecallBreakdown(
            total=0.8,
            explicit=0.9,
            implicit=0.5,
            explicit_tp=9,
            explicit_total=10,
            implicit_tp=2,
            implicit_total=4,
        )
        assert rb.total == 0.8
        assert rb.explicit == 0.9
        assert rb.implicit == 0.5
        assert rb.explicit_tp == 9
        assert rb.explicit_total == 10
        assert rb.implicit_tp == 2
        assert rb.implicit_total == 4

    def test_defaults_for_count_fields(self) -> None:
        rb = RecallBreakdown(total=1.0, explicit=1.0, implicit=1.0)
        assert rb.explicit_tp == 0
        assert rb.explicit_total == 0
        assert rb.implicit_tp == 0
        assert rb.implicit_total == 0

    def test_serialization_roundtrip(self) -> None:
        rb = RecallBreakdown(
            total=0.75,
            explicit=0.8,
            implicit=0.5,
            explicit_tp=4,
            explicit_total=5,
            implicit_tp=1,
            implicit_total=2,
        )
        data = rb.model_dump()
        restored = RecallBreakdown(**data)
        assert restored == rb


class TestKeywordMetricsRecallBreakdown:
    """Tests for KeywordMetrics.recall_breakdown optional field."""

    def test_recall_breakdown_defaults_to_none(self) -> None:
        km = KeywordMetrics(precision=0.9, recall=0.8, f1=0.85)
        assert km.recall_breakdown is None

    def test_recall_breakdown_accepts_value(self) -> None:
        rb = RecallBreakdown(
            total=0.8,
            explicit=0.9,
            implicit=0.5,
            explicit_tp=9,
            explicit_total=10,
            implicit_tp=2,
            implicit_total=4,
        )
        km = KeywordMetrics(
            precision=0.9,
            recall=0.8,
            f1=0.85,
            recall_breakdown=rb,
        )
        assert km.recall_breakdown is not None
        assert km.recall_breakdown.total == 0.8


# ===========================================================================
# _compute_recall_breakdown tests
# ===========================================================================


def _mt(*types: MentionType) -> list[MentionType]:
    """Helper to build a typed mention_types list."""
    return list(types)


class TestComputeRecallBreakdown:
    """Tests for _compute_recall_breakdown function."""

    def test_mix_of_explicit_and_implicit_with_some_fn(self) -> None:
        """3 explicit (idx 0,1,2) + 2 implicit (idx 3,4); FN at idx 1,3."""
        types = _mt(
            "explicit",
            "explicit",
            "explicit",
            "implicit",
            "implicit",
        )
        result = _compute_recall_breakdown(types, [1, 3])

        assert result.explicit_total == 3
        assert result.implicit_total == 2
        assert result.explicit_tp == 2
        assert result.implicit_tp == 1
        assert result.total == pytest.approx(3 / 5)
        assert result.explicit == pytest.approx(2 / 3)
        assert result.implicit == pytest.approx(1 / 2)

    def test_all_matched_no_fn(self) -> None:
        types = _mt("explicit", "implicit", "explicit")
        result = _compute_recall_breakdown(types, [])

        assert result.total == 1.0
        assert result.explicit == 1.0
        assert result.implicit == 1.0
        assert result.explicit_tp == 2
        assert result.explicit_total == 2
        assert result.implicit_tp == 1
        assert result.implicit_total == 1

    def test_empty_gold(self) -> None:
        result = _compute_recall_breakdown([], [])

        assert result.total == 1.0
        assert result.explicit == 1.0
        assert result.implicit == 1.0
        assert result.explicit_total == 0
        assert result.implicit_total == 0

    def test_all_fn(self) -> None:
        types = _mt("explicit", "implicit")
        result = _compute_recall_breakdown(types, [0, 1])

        assert result.total == 0.0
        assert result.explicit == 0.0
        assert result.implicit == 0.0

    def test_only_explicit_gold(self) -> None:
        types = _mt("explicit", "explicit")
        result = _compute_recall_breakdown(types, [0])

        assert result.explicit_total == 2
        assert result.implicit_total == 0
        assert result.explicit_tp == 1
        assert result.explicit == pytest.approx(0.5)
        assert result.implicit == 1.0  # vacuous

    def test_only_implicit_gold(self) -> None:
        types = _mt("implicit", "implicit")
        result = _compute_recall_breakdown(types, [1])

        assert result.implicit_total == 2
        assert result.explicit_total == 0
        assert result.implicit_tp == 1
        assert result.implicit == pytest.approx(0.5)
        assert result.explicit == 1.0  # vacuous

    def test_single_explicit_matched(self) -> None:
        result = _compute_recall_breakdown(_mt("explicit"), [])

        assert result.total == 1.0
        assert result.explicit == 1.0
        assert result.explicit_tp == 1
        assert result.explicit_total == 1

    def test_single_implicit_fn(self) -> None:
        result = _compute_recall_breakdown(_mt("implicit"), [0])

        assert result.total == 0.0
        assert result.implicit == 0.0
        assert result.explicit == 1.0  # vacuous

    def test_return_type_is_recall_breakdown(self) -> None:
        result = _compute_recall_breakdown(_mt("explicit"), [])
        assert isinstance(result, RecallBreakdown)

    def test_large_input(self) -> None:
        n = 100
        types: list[MentionType] = ["explicit" if i % 2 == 0 else "implicit" for i in range(n)]
        fn_gold_indices: list[int] = list(range(0, n, 3))

        result = _compute_recall_breakdown(types, fn_gold_indices)

        fn_count = len(fn_gold_indices)
        tp_count = n - fn_count
        assert result.total == pytest.approx(tp_count / n)
        assert result.explicit_total == 50
        assert result.implicit_total == 50

    def test_fn_indices_at_boundaries(self) -> None:
        types = _mt("explicit", "implicit", "explicit", "implicit")
        result = _compute_recall_breakdown(types, [0, 3])

        assert result.explicit_tp == 1
        assert result.implicit_tp == 1
        assert result.total == pytest.approx(0.5)

    def test_all_explicit_all_fn(self) -> None:
        types = _mt("explicit", "explicit", "explicit")
        result = _compute_recall_breakdown(types, [0, 1, 2])

        assert result.explicit == 0.0
        assert result.implicit == 1.0  # vacuous
        assert result.total == 0.0

    def test_all_implicit_all_matched(self) -> None:
        types = _mt("implicit", "implicit", "implicit")
        result = _compute_recall_breakdown(types, [])

        assert result.implicit == 1.0
        assert result.explicit == 1.0  # vacuous
        assert result.total == 1.0
        assert result.implicit_tp == 3
        assert result.implicit_total == 3
