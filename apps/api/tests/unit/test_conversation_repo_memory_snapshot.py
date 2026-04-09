"""Tests for ConversationRepository memory_context_text setters.

Covers:
- ``set_memory_context_text``: unconditional write used by greeting.
- ``try_set_memory_context_text_if_null``: race-safe lazy write used by
  the turn path. The simulated race uses two sessions on the same
  SQLite engine — one wins, the other reads back the winner's value.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from coyo.models.conversation import Conversation
from coyo.models.user import AuthProvider, User
from coyo.repositories.conversation import ConversationRepository


@pytest.mark.unit
async def test_set_memory_context_text_writes_both_columns(
    db_session: AsyncSession,
) -> None:
    user = User(auth_uid="t1", email="a@b.c", auth_provider=AuthProvider.EMAIL)
    db_session.add(user)
    await db_session.flush()
    conv = Conversation(user_id=user.id, time_limit_seconds=1800)
    db_session.add(conv)
    await db_session.flush()

    repo = ConversationRepository(db_session)
    await repo.set_memory_context_text(conv.id, "hello memory")

    db_session.expire(conv, ["memory_context_text", "memory_context_built_at"])
    await db_session.refresh(conv, ["memory_context_text", "memory_context_built_at"])
    assert conv.memory_context_text == "hello memory"
    assert conv.memory_context_built_at is not None


@pytest.mark.unit
async def test_try_set_memory_context_text_if_null_writes_when_null(
    db_session: AsyncSession,
) -> None:
    user = User(auth_uid="t2", email="a2@b.c", auth_provider=AuthProvider.EMAIL)
    db_session.add(user)
    await db_session.flush()
    conv = Conversation(user_id=user.id, time_limit_seconds=1800)
    db_session.add(conv)
    await db_session.flush()

    repo = ConversationRepository(db_session)
    winner = await repo.try_set_memory_context_text_if_null(conv.id, "first")
    assert winner == "first"


@pytest.mark.unit
async def test_try_set_memory_context_text_if_null_loser_returns_winner_value(
    engine,
) -> None:
    """Two concurrent sessions race; the loser must read the winner's text."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as setup_session:
        user = User(auth_uid="t3", email="a3@b.c", auth_provider=AuthProvider.EMAIL)
        setup_session.add(user)
        await setup_session.flush()
        conv = Conversation(user_id=user.id, time_limit_seconds=1800)
        setup_session.add(conv)
        await setup_session.commit()
        conv_id = conv.id

    # Session A wins.
    async with factory() as session_a:
        repo_a = ConversationRepository(session_a)
        winner_a = await repo_a.try_set_memory_context_text_if_null(conv_id, "winner")
        await session_a.commit()
    assert winner_a == "winner"

    # Session B loses — UPDATE matches 0 rows, re-SELECT returns "winner".
    async with factory() as session_b:
        repo_b = ConversationRepository(session_b)
        loser_value = await repo_b.try_set_memory_context_text_if_null(
            conv_id,
            "loser",
        )
    assert loser_value == "winner"
