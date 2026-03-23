"""Service for generating topic suggestions via LLM + web search."""

from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import IntegrityError

from coyo.config import get_settings
from coyo.repositories.interest import InterestRepository
from coyo.repositories.topic_suggestion import TopicSuggestionRepository
from coyo.services.llm.base import ChatMessage, ChatOptions, TextChunk
from coyo.services.llm.openai_client import OpenAIClient

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

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

_PERSONAL_SEARCH_PROMPT_TEMPLATE = """\
Today is {today}. Search for the latest news about "{keyword}" \
from TODAY or the past few days that would make a great English \
conversation starter for Japanese learners.

For the topic, provide:
1. A short catchy title (in English, max 10 words)
2. A brief summary (in English, 2 sentences)
3. Detailed article content for conversation context \
(in English, 500-800 characters). Include key facts, recent \
developments, and interesting angles for discussion.

Return your response as valid JSON:
{{
  "title": "...",
  "summary": "...",
  "article_content": "..."
}}
"""

_MAX_TOPICS = 3
_PERSONAL_MAX_KEYWORDS = 7

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_SAFE_KEYWORD_RE = re.compile(r"^[\w\s\-'/&.,()]+$", re.UNICODE)
_MAX_KEYWORD_LENGTH = 100


class TopicItem(BaseModel):
    """A single topic parsed from the LLM response."""

    title: str
    summary: str
    source_keyword: str
    article_content: str


class TopicSearchResult(BaseModel):
    """Structured LLM response containing trending topics."""

    topics: list[TopicItem]


class PersonalTopicItem(BaseModel):
    """A single personal topic parsed from the LLM response."""

    title: str
    summary: str
    article_content: str


def _extract_json(text: str) -> str:
    """Strip markdown code fences if present."""
    match = _CODE_FENCE_RE.search(text)
    return match.group(1).strip() if match else text.strip()


def _sanitize_keyword(keyword: str) -> str | None:
    """Return the keyword if safe for LLM prompt interpolation, else None."""
    keyword = keyword.strip()
    if not keyword or len(keyword) > _MAX_KEYWORD_LENGTH:
        return None
    if not _SAFE_KEYWORD_RE.match(keyword):
        return None
    return keyword


class TopicGenerationService:
    """Generates trending topic suggestions using LLM with web search."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = TopicSuggestionRepository(session)
        self._interest_repo = InterestRepository(session)
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

    async def generate_personal_topics(self) -> int:
        """Generate personal topics for all users based on their interests.

        Returns the number of personal topics generated.
        """
        today = date.today()

        # Idempotency: skip if personal topics already exist for today
        existing = await self._repo.get_personal_suggestions(today)
        if existing:
            logger.info(
                "personal_topics_already_generated",
                date=str(today),
                count=len(existing),
            )
            return len(existing)

        keyword_to_users = await self._collect_personal_keywords(today)
        if not keyword_to_users:
            return 0

        # Fetch, store, and assign each keyword's topic
        logger.info(
            "personal_topic_keywords_to_process",
            count=len(keyword_to_users),
        )
        count = 0
        for keyword, user_list in keyword_to_users.items():
            if await self._store_and_assign_personal_topic(
                keyword, user_list, today
            ):
                count += 1

        await self._session.commit()
        logger.info("personal_topic_generation_done", count=count)
        return count

    async def _collect_personal_keywords(
        self, today: date
    ) -> dict[str, list[tuple[uuid.UUID, float]]]:
        """Collect and deduplicate personal keywords across all users."""
        users = await self._repo.get_active_users_with_conv_count()
        if not users:
            return {}

        # Step 1: Collect top keywords per user
        user_keywords: dict[uuid.UUID, list[tuple[str, float]]] = {}
        for user_id, conv_count in users:
            interests = await self._interest_repo.get_top_interests(
                user_id,
                conv_count,
                keyword_type="topic",
                is_news_relevant=True,
                limit=_PERSONAL_MAX_KEYWORDS,
            )
            if interests:
                user_keywords[user_id] = [
                    (i.keyword, i.effective_weight) for i in interests
                ]

        if not user_keywords:
            logger.info("no_user_interests_found")
            return {}

        # Step 2: Deduplicate against common pool
        common_suggestions = await self._repo.get_common_suggestions(today)
        common_keywords = {s.source_keyword.lower() for s in common_suggestions}

        # Step 3: Pool unique keywords across users
        keyword_to_users: dict[str, list[tuple[uuid.UUID, float]]] = {}
        for user_id, kw_list in user_keywords.items():
            for keyword, weight in kw_list:
                if keyword.lower() not in common_keywords:
                    keyword_to_users.setdefault(keyword, []).append(
                        (user_id, weight)
                    )

        if not keyword_to_users:
            logger.info("all_personal_keywords_overlap_common")

        return keyword_to_users

    async def _store_and_assign_personal_topic(
        self,
        keyword: str,
        user_list: list[tuple[uuid.UUID, float]],
        today: date,
    ) -> bool:
        """Fetch, store, and assign a personal topic for a keyword.

        Returns True if the topic was successfully created.
        """
        topic = await self._fetch_personal_topic(keyword, today)
        if topic is None:
            return False

        try:
            async with self._session.begin_nested():
                suggestion = await self._repo.create_suggestion(
                    title=topic.title,
                    summary=topic.summary,
                    source_keyword=keyword,
                    article_content=topic.article_content,
                    article_url=None,
                    pool_type="personal",
                    generated_date=today,
                )
        except IntegrityError:
            logger.exception(
                "personal_topic_save_error", keyword=keyword[:50]
            )
            return False

        for user_id, weight in user_list:
            try:
                async with self._session.begin_nested():
                    await self._repo.create_user_suggestion(
                        user_id=user_id,
                        topic_suggestion_id=suggestion.id,
                        relevance_score=weight,
                    )
            except IntegrityError:
                logger.debug(
                    "personal_user_suggestion_duplicate",
                    user_id=str(user_id),
                    suggestion_id=str(suggestion.id),
                )

        return True

    async def _fetch_personal_topic(
        self, keyword: str, today: date
    ) -> PersonalTopicItem | None:
        """Fetch a single personal topic via LLM + web search."""
        sanitized = _sanitize_keyword(keyword)
        if sanitized is None:
            logger.warning(
                "keyword_sanitization_rejected", keyword=keyword[:50]
            )
            return None

        prompt = _PERSONAL_SEARCH_PROMPT_TEMPLATE.format(
            today=today.isoformat(),
            keyword=sanitized,
        )
        messages = [ChatMessage(role="user", content=prompt)]
        options = ChatOptions(temperature=0.7, max_tokens=1500)

        chunks: list[str] = []
        async for event in self._llm.chat_with_tools(messages, options=options):
            if isinstance(event, TextChunk):
                chunks.append(event.text)
        full_text = "".join(chunks)

        try:
            cleaned = _extract_json(full_text)
            return PersonalTopicItem.model_validate_json(cleaned)
        except (PydanticValidationError, ValueError):
            logger.warning(
                "personal_topic_parse_error",
                keyword=keyword[:50],
                raw_text_length=len(full_text),
            )
            try:
                return await self._llm.structured(
                    messages, PersonalTopicItem, options=options
                )
            except Exception:
                logger.exception(
                    "personal_topic_structured_fallback_failed",
                    keyword=keyword[:50],
                )
                return None
