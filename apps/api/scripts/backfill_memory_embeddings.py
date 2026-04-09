"""One-shot backfill of pgvector embedding columns.

Backfills ``user_interests.embedding`` and
``conversation_summaries.embedding`` for rows that were created before
the theme-relevant memory feature shipped (or whose embedding write
failed at the time).

Idempotent: re-running the script picks up only rows where
``embedding IS NULL``. Safe to run repeatedly until the NULL count
hits zero.

Embedding API calls happen OUTSIDE the DB transaction so a slow OpenAI
call cannot hold a write lock. Each batch executes in its own short
transaction with ``SET LOCAL statement_timeout = '60s'`` as a guard
against runaway statements.

Usage:
    python apps/api/scripts/backfill_memory_embeddings.py \\
        --table {user_interests|conversation_summaries|all} \\
        --batch-size 100 [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from typing import TYPE_CHECKING, Literal

import sqlalchemy as sa

from coyo.db import get_session_factory
from coyo.services.embedding import get_embedding_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("backfill")


TableName = Literal["user_interests", "conversation_summaries"]


def _compose_interest_text(keyword: str, summary: str | None) -> str:
    """Mirror the production embedding text for an interest row."""
    if summary:
        return f"{keyword}: {summary}"
    return keyword


def _compose_summary_text(
    source_keyword: str | None,
    topic_title: str,
    summary: str,
) -> str:
    """Mirror the production embedding text for a conversation summary."""
    head = source_keyword or topic_title
    return f"{head}\n{summary}"


_NULL_COUNT_SQL: dict[TableName, str] = {
    "user_interests": ("SELECT count(*) FROM user_interests WHERE embedding IS NULL"),
    "conversation_summaries": (
        "SELECT count(*) FROM conversation_summaries WHERE embedding IS NULL"
    ),
}


async def _count_nulls(session: AsyncSession, table: TableName) -> int:
    """Count rows still missing an embedding for the given table.

    Uses a static SQL dispatch table so the table name is never built
    via string interpolation — defense-in-depth even though the
    ``TableName`` Literal already constrains callers.
    """
    result = await session.execute(sa.text(_NULL_COUNT_SQL[table]))
    return int(result.scalar_one())


async def _fetch_interest_batch(session: AsyncSession, batch_size: int) -> list[dict[str, object]]:
    stmt = sa.text(
        "SELECT user_id, keyword, summary FROM user_interests WHERE embedding IS NULL LIMIT :limit"
    )
    result = await session.execute(stmt, {"limit": batch_size})
    return [dict(row._mapping) for row in result.all()]


async def _fetch_summary_batch(session: AsyncSession, batch_size: int) -> list[dict[str, object]]:
    stmt = sa.text(
        "SELECT id, source_keyword, topic_title, summary "
        "FROM conversation_summaries "
        "WHERE embedding IS NULL LIMIT :limit"
    )
    result = await session.execute(stmt, {"limit": batch_size})
    return [dict(row._mapping) for row in result.all()]


async def _update_interest_embeddings(
    session: AsyncSession,
    rows: list[dict[str, object]],
    embeddings: list[list[float]],
) -> None:
    """Write embeddings back, matching on the composite (user_id, keyword)."""
    await session.execute(sa.text("SET LOCAL statement_timeout = '60s'"))
    stmt = sa.text(
        "UPDATE user_interests SET embedding = :embedding "
        "WHERE user_id = :user_id AND keyword = :keyword"
    )
    for row, vec in zip(rows, embeddings, strict=True):
        await session.execute(
            stmt,
            {
                "embedding": vec,
                "user_id": row["user_id"],
                "keyword": row["keyword"],
            },
        )


async def _update_summary_embeddings(
    session: AsyncSession,
    rows: list[dict[str, object]],
    embeddings: list[list[float]],
) -> None:
    """Write embeddings back, matching on the conversation summary id."""
    await session.execute(sa.text("SET LOCAL statement_timeout = '60s'"))
    stmt = sa.text("UPDATE conversation_summaries SET embedding = :embedding WHERE id = :id")
    for row, vec in zip(rows, embeddings, strict=True):
        row_id = row["id"]
        if isinstance(row_id, str):
            row_id = uuid.UUID(row_id)
        await session.execute(stmt, {"embedding": vec, "id": row_id})


async def _backfill_interests(batch_size: int, dry_run: bool) -> None:
    factory = get_session_factory()
    embedding_service = get_embedding_service()

    async with factory() as session:
        initial_null = await _count_nulls(session, "user_interests")
    logger.info("user_interests: %d rows need embeddings", initial_null)

    if initial_null == 0:
        return

    processed = 0
    while True:
        async with factory() as session:
            rows = await _fetch_interest_batch(session, batch_size)
        if not rows:
            break

        texts = [
            _compose_interest_text(
                str(r["keyword"]),
                None if r["summary"] is None else str(r["summary"]),
            )
            for r in rows
        ]

        if dry_run:
            logger.info(
                "[dry-run] would embed %d interest rows; sample: %r",
                len(rows),
                texts[0],
            )
            return

        embeddings = await embedding_service.embed(texts)

        async with factory() as session, session.begin():
            await _update_interest_embeddings(session, rows, embeddings)

        processed += len(rows)
        logger.info(
            "user_interests: processed %d / %d",
            processed,
            initial_null,
        )

    async with factory() as session:
        remaining = await _count_nulls(session, "user_interests")
    logger.info("user_interests: %d rows still NULL after backfill", remaining)
    if remaining != 0:
        logger.warning(
            "Some user_interests rows are still missing embeddings — re-run the script to retry."
        )


async def _backfill_summaries(batch_size: int, dry_run: bool) -> None:
    factory = get_session_factory()
    embedding_service = get_embedding_service()

    async with factory() as session:
        initial_null = await _count_nulls(session, "conversation_summaries")
    logger.info(
        "conversation_summaries: %d rows need embeddings",
        initial_null,
    )

    if initial_null == 0:
        return

    processed = 0
    while True:
        async with factory() as session:
            rows = await _fetch_summary_batch(session, batch_size)
        if not rows:
            break

        texts = [
            _compose_summary_text(
                None if r["source_keyword"] is None else str(r["source_keyword"]),
                str(r["topic_title"]),
                str(r["summary"]),
            )
            for r in rows
        ]

        if dry_run:
            logger.info(
                "[dry-run] would embed %d summary rows; sample: %r",
                len(rows),
                texts[0],
            )
            return

        embeddings = await embedding_service.embed(texts)

        async with factory() as session, session.begin():
            await _update_summary_embeddings(session, rows, embeddings)

        processed += len(rows)
        logger.info(
            "conversation_summaries: processed %d / %d",
            processed,
            initial_null,
        )

    async with factory() as session:
        remaining = await _count_nulls(session, "conversation_summaries")
    logger.info(
        "conversation_summaries: %d rows still NULL after backfill",
        remaining,
    )
    if remaining != 0:
        logger.warning(
            "Some conversation_summaries rows are still missing "
            "embeddings — re-run the script to retry."
        )


async def main_async(args: argparse.Namespace) -> int:
    if args.table in ("user_interests", "all"):
        await _backfill_interests(args.batch_size, args.dry_run)
    if args.table in ("conversation_summaries", "all"):
        await _backfill_summaries(args.batch_size, args.dry_run)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--table",
        choices=("user_interests", "conversation_summaries", "all"),
        default="all",
    )
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts and a sample text without writing.",
    )
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
