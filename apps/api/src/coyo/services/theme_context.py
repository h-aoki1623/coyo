"""Build the theme context for theme-relevant memory retrieval.

The ``ThemeContext`` carries the textual representation of the current
conversation theme plus its embedding (computed once per conversation).
The embedding is reused by ``MemoryContextService.build_context`` to rank
the user's interests and past summaries by topical relevance.

This module exists separately from ``memory_context.py`` to keep the
embedding-side concerns (text composition, embedding API call, error
handling) decoupled from the ranking-side concerns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from coyo.exceptions import ExternalServiceError
from coyo.models.topic_suggestion import TopicSuggestion

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from coyo.models.conversation import Conversation

logger = structlog.get_logger()


@dataclass(frozen=True)
class ThemeContext:
    """Theme signal for theme-relevant memory retrieval.

    Attributes:
        theme_text: Human-readable theme description used for embedding.
        theme_embedding: 1536-dim embedding of ``theme_text``. ``None``
            when the embedding API failed; callers fall back to the
            legacy non-theme path in that case.
    """

    theme_text: str
    theme_embedding: list[float] | None


async def build_theme_context(
    conversation: Conversation,
    session: AsyncSession,
) -> ThemeContext | None:
    """Construct a ``ThemeContext`` from the conversation, if any signal exists.

    Returns ``None`` for conversations with no theme signal — for example
    a free-form ``topic == "general"`` chat with no topic suggestion.
    Callers fall back to the legacy top-N / recent-N memory injection.

    On embedding API failure, returns a ``ThemeContext`` with
    ``theme_embedding=None``; ranking-side code treats this as the
    no-theme case and falls back to the legacy path.
    """
    theme_text: str | None = None

    if conversation.topic_suggestion_id is not None:
        suggestion = await session.get(
            TopicSuggestion,
            conversation.topic_suggestion_id,
        )
        if suggestion is not None:
            parts: list[str] = []
            if suggestion.source_keyword:
                parts.append(suggestion.source_keyword)
            if suggestion.title:
                parts.append(suggestion.title)
            if suggestion.summary:
                parts.append(suggestion.summary)
            theme_text = "\n".join(parts) if parts else None

    if not theme_text:
        return None

    # Lazy import keeps the embedding service singleton out of import-time
    # cycles with config / db modules.
    from coyo.services.embedding import get_embedding_service

    embedding_service = get_embedding_service()
    try:
        vectors = await embedding_service.embed([theme_text])
        embedding = vectors[0] if vectors else None
    except ExternalServiceError:
        logger.warning(
            "theme_embed_failed",
            conversation_id=str(conversation.id),
        )
        embedding = None

    return ThemeContext(
        theme_text=theme_text,
        theme_embedding=embedding,
    )
