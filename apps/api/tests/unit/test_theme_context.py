"""Unit tests for theme_context.build_theme_context."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coyo.exceptions import ExternalServiceError
from coyo.services.theme_context import ThemeContext, build_theme_context


def _make_conversation(*, topic_suggestion_id):
    conv = MagicMock()
    conv.id = uuid.uuid4()
    conv.topic_suggestion_id = topic_suggestion_id
    return conv


def _make_topic_suggestion(
    *,
    source_keyword="tennis",
    title="Wimbledon 2026",
    summary="Carlos Alcaraz takes the men's title.",
):
    sug = MagicMock()
    sug.source_keyword = source_keyword
    sug.title = title
    sug.summary = summary
    return sug


@pytest.mark.unit
async def test_build_theme_context_returns_none_when_no_topic_suggestion():
    """Free-form chat with no signal returns None (legacy fallback)."""
    conv = _make_conversation(topic_suggestion_id=None)
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)

    result = await build_theme_context(conv, session)
    assert result is None


@pytest.mark.unit
async def test_build_theme_context_with_suggestion_returns_embedding():
    """Suggestion present → theme_text composed and embedded."""
    topic_id = uuid.uuid4()
    conv = _make_conversation(topic_suggestion_id=topic_id)
    suggestion = _make_topic_suggestion()

    session = AsyncMock()
    session.get = AsyncMock(return_value=suggestion)

    embedding_service = AsyncMock()
    embedding_service.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

    with patch(
        "coyo.services.embedding.get_embedding_service",
        return_value=embedding_service,
    ):
        result = await build_theme_context(conv, session)

    assert isinstance(result, ThemeContext)
    assert "tennis" in result.theme_text.lower()
    assert "wimbledon" in result.theme_text.lower()
    assert result.theme_embedding == [0.1, 0.2, 0.3]


@pytest.mark.unit
async def test_build_theme_context_handles_embed_failure():
    """Embedding API failure should yield ThemeContext with embedding=None,
    not raise — the caller must still receive the theme text for logging."""
    topic_id = uuid.uuid4()
    conv = _make_conversation(topic_suggestion_id=topic_id)
    suggestion = _make_topic_suggestion()

    session = AsyncMock()
    session.get = AsyncMock(return_value=suggestion)

    embedding_service = AsyncMock()
    embedding_service.embed = AsyncMock(
        side_effect=ExternalServiceError("OpenAI Embeddings", "boom"),
    )

    with patch(
        "coyo.services.embedding.get_embedding_service",
        return_value=embedding_service,
    ):
        result = await build_theme_context(conv, session)

    assert result is not None
    assert result.theme_embedding is None
    assert result.theme_text  # not empty
