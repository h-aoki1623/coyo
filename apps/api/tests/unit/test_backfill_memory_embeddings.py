"""Unit tests for the backfill script.

Regression coverage for the production failure where the ``:embedding``
bind parameter in the raw ``sa.text(...)`` UPDATE statements was not
typed, causing asyncpg to attempt encoding the Python ``list[float]``
as text and raising ``DataError: expected str, got list``.

The bug was discovered while running:

    DATABASE_URL='postgresql+asyncpg://...' \\
      .venv/bin/python scripts/backfill_memory_embeddings.py --table all

These tests don't require a live pgvector database — they introspect
the SQLAlchemy ``TextClause`` produced by the helpers and verify that
the ``embedding`` bind parameter carries an explicit ``Vector`` type
annotation. Without that annotation, SQLAlchemy / asyncpg fall back to
the generic text codec and the production failure reproduces.
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy.sql.elements import TextClause

if TYPE_CHECKING:
    from types import ModuleType


def _load_backfill_module() -> ModuleType:
    """Load the backfill script as an importable module by file path.

    The script lives outside the ``coyo`` package and is normally invoked
    as a top-level executable, so it isn't on ``sys.path``. Loading it via
    ``importlib`` keeps the test self-contained without requiring a
    ``conftest.py`` ``sys.path`` hack.
    """
    script_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "backfill_memory_embeddings.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_test_backfill_memory_embeddings", script_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


backfill = _load_backfill_module()


def _captured_text_stmt(execute_mock: AsyncMock) -> TextClause:
    """Pull the second ``execute`` call's first positional arg.

    The first call is always ``SET LOCAL statement_timeout``; the second
    is the typed UPDATE statement we want to inspect.
    """
    assert execute_mock.await_count >= 2, (
        f"expected at least 2 execute calls, got {execute_mock.await_count}"
    )
    update_call = execute_mock.await_args_list[1]
    stmt = update_call.args[0]
    assert isinstance(stmt, TextClause), f"expected TextClause, got {type(stmt)!r}"
    return stmt


def _embedding_bind_type(stmt: TextClause) -> object:
    """Return the SQL type attached to the ``embedding`` bind param."""
    bind = stmt._bindparams.get("embedding")  # noqa: SLF001 — unit-test introspection
    assert bind is not None, "stmt has no :embedding bind param"
    return bind.type


@pytest.mark.unit
async def test_update_interest_embeddings_uses_typed_bindparam():
    """Regression: UPDATE must carry a ``Vector(1536)``-typed bind param.

    Without ``bindparam("embedding", type_=Vector(1536))``, asyncpg
    encodes the list as text and raises ``DataError`` against pgvector.
    """
    session = AsyncMock()
    session.execute = AsyncMock()

    rows = [
        {"user_id": uuid.uuid4(), "keyword": "tennis"},
        {"user_id": uuid.uuid4(), "keyword": "ai"},
    ]
    embeddings = [[0.1] * 1536, [0.2] * 1536]

    await backfill._update_interest_embeddings(session, rows, embeddings)  # noqa: SLF001

    stmt = _captured_text_stmt(session.execute)
    bind_type = _embedding_bind_type(stmt)
    assert isinstance(bind_type, Vector), (
        f"expected Vector type for :embedding, got {type(bind_type).__name__}"
    )
    assert bind_type.dim == 1536


@pytest.mark.unit
async def test_update_summary_embeddings_uses_typed_bindparam():
    """Regression: same fix on the conversation_summaries UPDATE path."""
    session = AsyncMock()
    session.execute = AsyncMock()

    rows = [
        {"id": uuid.uuid4()},
        {"id": uuid.uuid4()},
    ]
    embeddings = [[0.3] * 1536, [0.4] * 1536]

    await backfill._update_summary_embeddings(session, rows, embeddings)  # noqa: SLF001

    stmt = _captured_text_stmt(session.execute)
    bind_type = _embedding_bind_type(stmt)
    assert isinstance(bind_type, Vector), (
        f"expected Vector type for :embedding, got {type(bind_type).__name__}"
    )
    assert bind_type.dim == 1536


@pytest.mark.unit
async def test_update_interest_embeddings_executes_one_update_per_row():
    """Verify each row results in exactly one UPDATE call."""
    session = AsyncMock()
    session.execute = AsyncMock()

    rows = [
        {"user_id": uuid.uuid4(), "keyword": "tennis"},
        {"user_id": uuid.uuid4(), "keyword": "ai"},
        {"user_id": uuid.uuid4(), "keyword": "cooking"},
    ]
    embeddings = [[float(i)] * 1536 for i in range(3)]

    await backfill._update_interest_embeddings(session, rows, embeddings)  # noqa: SLF001

    # 1 SET LOCAL + 3 UPDATEs = 4 total
    assert session.execute.await_count == 4
    # Each UPDATE call should bind the matching keyword
    for call_idx, expected_keyword in enumerate(["tennis", "ai", "cooking"], start=1):
        params = session.execute.await_args_list[call_idx].args[1]
        assert params["keyword"] == expected_keyword


@pytest.mark.unit
async def test_update_summary_embeddings_normalises_string_uuid():
    """If a row's ``id`` arrives as a string it should be coerced to UUID."""
    session = AsyncMock()
    session.execute = AsyncMock()

    string_id = "c088e999-87de-4573-ac41-f56e46da8841"
    rows = [{"id": string_id}]
    embeddings = [[0.0] * 1536]

    await backfill._update_summary_embeddings(session, rows, embeddings)  # noqa: SLF001

    update_call = session.execute.await_args_list[1]
    bound_id = update_call.args[1]["id"]
    assert isinstance(bound_id, uuid.UUID)
    assert str(bound_id) == string_id


@pytest.mark.unit
async def test_compose_helpers_match_production_format():
    """Embedded text format must match what the live write path uses.

    If these strings drift the backfill will produce embeddings that
    rank differently from rows written by the production write path,
    silently degrading retrieval quality.
    """
    assert backfill._compose_interest_text("tennis", None) == "tennis"  # noqa: SLF001
    assert (
        backfill._compose_interest_text("tennis", "plays weekends")  # noqa: SLF001
        == "tennis: plays weekends"
    )
    assert (
        backfill._compose_summary_text("kw", "Title", "Body")  # noqa: SLF001
        == "kw\nBody"
    )
    assert (
        backfill._compose_summary_text(None, "Title", "Body")  # noqa: SLF001
        == "Title\nBody"
    )
