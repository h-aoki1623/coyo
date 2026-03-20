"""Service for generating topic suggestions via LLM + web search."""

import re
from datetime import date

import structlog
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.config import get_settings
from coyo.repositories.topic_suggestion import TopicSuggestionRepository
from coyo.services.llm.base import ChatMessage, ChatOptions, TextChunk
from coyo.services.llm.openai_client import OpenAIClient

logger = structlog.get_logger()

_SEARCH_PROMPT_TEMPLATE = """\
Today is {today}. Search for the latest news and find 3 trending topics \
from TODAY or the past few days that would make great English conversation starters \
for Japanese learners. Topics MUST be from {today} or very recent — do NOT use old news.

Focus on global topics from different categories \
(e.g., sports, technology, entertainment, science, business).

For each topic, provide:
1. A short catchy title (in English, max 10 words)
2. A brief summary (in English, 2 sentences)
3. A single keyword for categorization (e.g., "NBA", "AI", "Oscars")
4. Detailed article content for conversation context (in English, 500-800 characters). \
Include key facts, recent developments, and interesting angles for discussion.

Return your response as valid JSON with this structure:
{{
  "topics": [
    {{
      "title": "...",
      "summary": "...",
      "source_keyword": "...",
      "article_content": "..."
    }}
  ]
}}
"""

_MAX_TOPICS = 3

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class TopicItem(BaseModel):
    """A single topic parsed from the LLM response."""

    title: str
    summary: str
    source_keyword: str
    article_content: str


class TopicSearchResult(BaseModel):
    """Structured LLM response containing trending topics."""

    topics: list[TopicItem]


def _extract_json(text: str) -> str:
    """Strip markdown code fences if present."""
    match = _CODE_FENCE_RE.search(text)
    return match.group(1).strip() if match else text.strip()


class TopicGenerationService:
    """Generates trending topic suggestions using LLM with web search."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = TopicSuggestionRepository(session)
        settings = get_settings()
        self._llm = OpenAIClient(model=settings.llm_topic_model)

    async def generate_common_topics(self) -> int:
        """Generate common trending topics for today.

        Returns the number of topics successfully generated.
        """
        today = date.today()

        # Check if already generated for today
        existing = await self._repo.get_common_suggestions(today)
        if existing:
            logger.info("topics_already_generated", date=str(today), count=len(existing))
            return len(existing)

        # Use web search to find trending topics
        logger.info("topic_generation_start")
        result = await self._fetch_topics()

        count = 0
        for item in result.topics[:_MAX_TOPICS]:
            try:
                await self._repo.create_suggestion(
                    title=item.title,
                    summary=item.summary,
                    source_keyword=item.source_keyword,
                    article_content=item.article_content,
                    article_url=None,
                    pool_type="common",
                    generated_date=today,
                )
                count += 1
            except IntegrityError:
                logger.exception("topic_save_error", title=item.title)

        await self._session.commit()
        logger.info("topic_generation_done", count=count)
        return count

    async def assign_to_users(self) -> int:
        """Assign today's common topics to all users.

        Returns the number of user-suggestion links created.
        """
        today = date.today()
        suggestions = await self._repo.get_common_suggestions(today)
        if not suggestions:
            return 0

        user_ids = await self._repo.get_active_user_ids()
        count = 0
        for user_id in user_ids:
            for rank, suggestion in enumerate(suggestions, start=1):
                try:
                    async with self._session.begin_nested():
                        await self._repo.create_user_suggestion(
                            user_id=user_id,
                            topic_suggestion_id=suggestion.id,
                            relevance_score=1.0 / rank,
                        )
                    count += 1
                except IntegrityError:
                    logger.debug(
                        "user_suggestion_duplicate",
                        user_id=str(user_id),
                        suggestion_id=str(suggestion.id),
                    )

        await self._session.commit()
        logger.info("topic_assignment_done", users=len(user_ids), links=count)
        return count

    async def _fetch_topics(self) -> TopicSearchResult:
        """Fetch trending topics from LLM with web search, with fallback."""
        # Use "user" role so the Responses API receives a non-empty `input`.
        # (Responses API requires at least one input message; system-only
        # messages are extracted into `instructions` leaving `input` empty.)
        prompt = _SEARCH_PROMPT_TEMPLATE.format(today=date.today().isoformat())
        messages = [ChatMessage(role="user", content=prompt)]
        options = ChatOptions(temperature=0.7, max_tokens=2000)

        chunks: list[str] = []
        async for event in self._llm.chat_with_tools(messages, options=options):
            if isinstance(event, TextChunk):
                chunks.append(event.text)
        full_text = "".join(chunks)

        try:
            cleaned = _extract_json(full_text)
            return TopicSearchResult.model_validate_json(cleaned)
        except (PydanticValidationError, ValueError):
            logger.error(
                "topic_generation_parse_error",
                raw_text_length=len(full_text),
            )
            # Fallback: use structured output
            return await self._llm.structured(messages, TopicSearchResult, options=options)
