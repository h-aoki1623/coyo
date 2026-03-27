"""Service for extracting user memories, interests, and summaries from conversations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import structlog
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select, update

from coyo.config import get_settings
from coyo.db import get_session_factory
from coyo.models.conversation import Conversation
from coyo.models.topic_suggestion import TopicSuggestion
from coyo.models.turn import Turn
from coyo.models.user import User
from coyo.repositories.conversation_summary import ConversationSummaryRepository
from coyo.repositories.interest import InterestRepository
from coyo.repositories.profile_attribute import ProfileAttributeRepository
from coyo.repositories.profile_summary import ProfileSummaryRepository
from coyo.services.llm.base import ChatMessage, ChatOptions
from coyo.services.llm.openai_client import OpenAIClient

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

MAX_CATEGORIES = 3
MAX_ENTITIES = 5
_MAX_KEYWORD_LENGTH = 100
_MAX_SUMMARY_LENGTH = 200
_CONFIDENCE_THRESHOLD = 0.5
_BATCH_INTERVAL = 5


# ---------------------------------------------------------------------------
# Pydantic models for LLM structured output
# ---------------------------------------------------------------------------


class MemoryItem(BaseModel):
    """A single extracted user profile attribute."""

    key: Literal[
        "english_goal", "job_industry", "hometown_or_location", "family_status"
    ]
    value: str | None = Field(default=None, max_length=200)
    confidence: float = Field(ge=0.0, le=1.0)
    is_negation: bool = False


class KeywordItem(BaseModel):
    """A single extracted keyword with optional summary."""

    keyword: str
    is_news_relevant: bool = False
    summary: str | None = None

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, v: str) -> str:
        v = v.lower().strip()
        if len(v) > _MAX_KEYWORD_LENGTH:
            v = v[:_MAX_KEYWORD_LENGTH]
        return v


class MemoryExtractionResult(BaseModel):
    """LLM response model for unified memory extraction."""

    conversation_summary: str
    memories: list[MemoryItem] = []
    categories: list[KeywordItem] = []
    entities: list[KeywordItem] = []

    @model_validator(mode="before")
    @classmethod
    def normalize_raw_categories_and_entities(cls, data: dict) -> dict:
        """Normalize plain strings in categories/entities to dicts before validation.

        LLMs sometimes return plain keyword strings instead of full objects.
        This converts them to the expected dict format before Pydantic validates.
        """
        if isinstance(data, dict):
            for field in ("categories", "entities"):
                items = data.get(field, [])
                if isinstance(items, list):
                    data[field] = [
                        {"keyword": item} if isinstance(item, str) else item
                        for item in items
                    ]
        return data


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_EXTRACTION_SYSTEM_PROMPT = """\
You are analyzing an English conversation practice session.
Extract two types of information from the USER's turns only (never from the AI's turns).
The conversation transcript will be provided in the user message.

Return JSON only with this exact structure:
{
  "conversation_summary": "1-2 sentence summary of what was discussed (max 60 words, English)",
  "memories": [{"key": "...", "value": "...", "confidence": 0.0, "is_negation": false}],
  "categories": [{"keyword": "...", "is_news_relevant": true/false, "summary": "..." or null}],
  "entities": [{"keyword": "...", "is_news_relevant": true/false, "summary": "..." or null}]
}

=== MEMORIES ===
Valid keys (background attributes only - 4 keys total):
  english_goal        the user's English learning goal or purpose
  job_industry        the user's industry, job type, or role
  hometown_or_location the user's hometown or current city/country
  family_status       the user's family situation (married, children, etc.)

Rules:
- ONLY extract from USER's turns
- confidence: 1.0 = stated directly, 0.7 = strongly implied, 0.5 = inferred
- is_negation = true if user denies/contradicts a previous fact
- Do NOT extract passwords, financial details, health conditions
- If no relevant facts, return "memories": []

=== VALIDITY RULES FOR KEYWORDS ===

All keywords must pass this test:
  "I'm interested in ___" sounds natural in English. If not, skip it.

[For categories]
- categories: broad interest subjects (max 3, English, lowercase)
- Must correspond to an IAB Content Taxonomy category (Tier 1 through Tier 4)
  e.g., "sports", "technology"                            ← Tier 1
        "tennis", "cooking", "generative AI"              ← Tier 2
        "running and jogging", "barbecues and grilling"   ← Tier 3
        "herbs and supplements"                           ← Tier 4

[For entities]
- entities: specific proper nouns (max 5, English, lowercase)
- Must be a proper noun with a unique real-world identity
  (person, event, organization, product — Knowledge Graph level)

[Granularity — applies to both categories and entities]
- Choose the tier that best reflects the SCOPE OF INTEREST the user expressed,
  not simply the most specific term mentioned in the conversation.
  → If the user expresses a broad interest that happens to include a specific activity,
    use the broader tier to avoid narrowing the interest unnecessarily.
  → Only use a more specific tier when the user explicitly focuses on that subcategory.

  e.g., BAD: User says "I enjoy working out. I did some yoga this morning."
        → Do NOT extract "Yoga" (Tier 3); the user's interest is "Fitness and Exercise" (Tier 2)
  e.g., GOOD: User says "I'm really into yoga. I practice it every day."
        → Extract "Yoga" (Tier 3); the user explicitly focuses on yoga itself

- Use a broader tier when the conversation is too vague to identify a specific one.
  e.g., user says "I like watching sports in general" → "Sports" (Tier 1) is acceptable
- Must NOT be a rule, mechanic, system, or sub-element of a category.
  e.g., "challenge system" → extract "tennis" instead
        "pick and roll"    → extract "basketball" instead
        "video review"     → extract "tennis" instead
- Must NOT be a common noun used generically without a specific referent.
  e.g., "the player", "a famous chef", "my favorite team" → skip

[Deduplication — semantic, not exact match]
- If two keywords refer to the same concept, keep only the shorter/broader one.
  e.g., "grand slam" + "grand slam tournaments" → keep "grand slam" only

[is_news_relevant]
- true:  keyword generates regular news (sports, politics, economy, tech, etc.)
         Ask: does "{keyword} news" return fresh articles regularly?
- false: evergreen categories (food, daily life, grammar, hobbies)

=== INTEREST SUMMARIES ===
For each category/entity, generate summary if conversation has specific info about it.
- Third person ("User is...", "User started...")
- Hard limit: 200 characters
- Return null if no specific info beyond keyword itself
- Priority: HIGH=permanent facts, MEDIUM=ongoing preferences, LOW=one-time events"""

_INTEREST_SUMMARY_PROMPT = """\
You are updating a user interest summary for a personalized English conversation app.

Keyword: "{keyword}"

[Existing summary (for reference only - do not copy or extend)]
{existing_summary}

[Recent conversations where this keyword appeared]
{related_conversations}

Write a fresh 1-2 sentence summary in English describing what this user has \
shared about "{keyword}".
Guidelines:
- Third person ("User is...")
- Write fresh - do NOT copy existing summary
- Priority: HIGH=permanent facts, MEDIUM=ongoing preferences, LOW=one-time events
- Remove contradicted info
- Hard limit: 200 characters
- If no useful info, return null for the summary

Return JSON: {{"summary": "..."}}  (or {{"summary": null}} if no useful info)"""

_PROFILE_SUMMARY_PROMPT = """\
You are synthesizing a user profile for a personalized English conversation app.

[User's background attributes]
{user_profile_attributes}

[User's top interests with summaries]
{interests_with_summaries}

[Recent conversation topics]
{recent_conversations}

Write a 2-3 paragraph narrative summary of this user in English (150-250 words).
Focus on: professional background, interests and hobbies, learning goals, \
notable experiences.
Guidelines:
- Third person ("This user...", "They...")
- Be specific where data supports it
- Do not fabricate
- Do not mention confidence scores
- Keep it warm and human

Return JSON: {{"summary": "..."}}"""


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def is_semantically_same(old: str, new: str) -> bool:
    """Case-insensitive, whitespace-normalized comparison."""
    return old.strip().lower() == new.strip().lower()


def _keyword_matches(keyword: str, text: str) -> bool:
    """Check if keyword appears in text with word boundary awareness."""
    import re

    pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
    return bool(re.search(pattern, text.lower()))



def trim_to_word_boundary(text: str, *, max_chars: int = _MAX_SUMMARY_LENGTH) -> str:
    """Trim text to max_chars at a word boundary."""
    if len(text) <= max_chars:
        return text
    trimmed = text[:max_chars]
    last_space = trimmed.rfind(" ")
    if last_space > 0:
        return trimmed[:last_space]
    return trimmed


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class MemoryExtractionService:
    """Extracts memories, interests, and summaries from conversations."""

    @staticmethod
    async def extract_background(
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Run memory extraction in an independent session.

        Designed to be called via asyncio.create_task after conversation ends.
        Errors are logged but never propagated.
        """
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                await MemoryExtractionService._extract(
                    session, conversation_id, user_id
                )
                await session.commit()
        except Exception:
            logger.exception(
                "memory_extraction_failed",
                conversation_id=str(conversation_id),
                user_id=str(user_id),
            )

    @staticmethod
    async def extract(
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Run memory extraction. Raises on failure for Cloud Tasks retry."""
        session_factory = get_session_factory()
        async with session_factory() as session:
            await MemoryExtractionService._extract(
                session, conversation_id, user_id
            )
            await session.commit()

    @staticmethod
    async def _extract(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Core extraction logic within a given session."""
        # 1. Idempotency check
        conversation = await session.get(Conversation, conversation_id)
        if conversation is None:
            logger.warning(
                "memory_extraction_conversation_not_found",
                conversation_id=str(conversation_id),
            )
            return
        if conversation.user_id != user_id:
            logger.error(
                "memory_extraction_user_mismatch",
                conversation_id=str(conversation_id),
                user_id=str(user_id),
                actual_user_id=str(conversation.user_id),
            )
            return
        if conversation.memory_extracted:
            logger.info(
                "memory_extraction_already_done",
                conversation_id=str(conversation_id),
            )
            return

        # 2. Atomically increment conversation_count (prevents race condition)
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(conversation_count=User.conversation_count + 1)
            .returning(User.conversation_count)
        )
        result = await session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            logger.warning(
                "memory_extraction_user_not_found",
                user_id=str(user_id),
            )
            return
        current_conv_idx = row[0]

        # 3. Build transcript (all turns for full context)
        transcript = await MemoryExtractionService._build_transcript(
            session, conversation_id
        )
        if not transcript.strip():
            logger.info(
                "memory_extraction_empty_transcript",
                conversation_id=str(conversation_id),
            )
            conversation.memory_extracted = True
            conversation.interests_extracted = True
            await session.flush()
            return

        # 4. Single LLM call with unified prompt
        extraction = await MemoryExtractionService._call_llm(transcript)

        # 5. Save conversation summary
        await MemoryExtractionService._save_conversation_summary(
            session, conversation, extraction.conversation_summary, user_id
        )

        # 6. Process memories (profile attributes)
        await MemoryExtractionService._process_memories(
            session, user_id, extraction.memories
        )

        # 7. Upsert interests (categories + entities) via post-processing pipeline
        seen_keywords = await MemoryExtractionService._upsert_interests(
            session, user_id, extraction, current_conv_idx
        )

        # 8. Batch regeneration every N conversations
        if current_conv_idx % _BATCH_INTERVAL == 0:
            await MemoryExtractionService._regenerate_interest_summaries(
                session, user_id
            )
            await MemoryExtractionService._regenerate_profile_summary(
                session, user_id, current_conv_idx
            )

        # 9. Mark as extracted
        conversation.memory_extracted = True
        conversation.interests_extracted = True
        await session.flush()
        logger.info(
            "memory_extraction_complete",
            conversation_id=str(conversation_id),
            keywords_count=len(seen_keywords),
            memories_count=len(extraction.memories),
        )

    @staticmethod
    async def _build_transcript(
        session: AsyncSession,
        conversation_id: uuid.UUID,
    ) -> str:
        """Build a transcript of all turns for the conversation."""
        stmt = (
            select(Turn.role, Turn.text)
            .where(Turn.conversation_id == conversation_id)
            .order_by(Turn.sequence)
        )
        result = await session.execute(stmt)
        rows = result.all()
        lines: list[str] = []
        for role, text in rows:
            label = "User" if role == "user" else "AI"
            lines.append(f"{label}: {text}")
        return "\n".join(lines)

    @staticmethod
    async def _call_llm(transcript: str) -> MemoryExtractionResult:
        """Call LLM to extract memories, categories, and entities from transcript."""
        settings = get_settings()
        llm = OpenAIClient(model=settings.llm_interest_model)

        prompt = _EXTRACTION_SYSTEM_PROMPT
        messages = [
            ChatMessage(role="system", content=prompt),
            ChatMessage(role="user", content=transcript),
        ]

        return await llm.structured(
            messages,
            response_model=MemoryExtractionResult,
            options=ChatOptions(temperature=0.3, max_tokens=1024),
        )

    @staticmethod
    async def _save_conversation_summary(
        session: AsyncSession,
        conversation: Conversation,
        summary_text: str,
        user_id: uuid.UUID,
    ) -> None:
        """Save the conversation summary with topic title."""
        topic_title = "Free conversation"
        source_keyword: str | None = None

        if conversation.topic_suggestion_id is not None:
            suggestion = await session.get(
                TopicSuggestion, conversation.topic_suggestion_id
            )
            if suggestion is not None:
                topic_title = suggestion.title
                source_keyword = suggestion.source_keyword

        repo = ConversationSummaryRepository(session)
        await repo.create(
            conversation_id=conversation.id,
            user_id=user_id,
            topic_title=topic_title,
            source_keyword=source_keyword,
            summary=summary_text,
        )

    @staticmethod
    async def _process_memories(
        session: AsyncSession,
        user_id: uuid.UUID,
        memories: list[MemoryItem],
    ) -> None:
        """Process memory items: ADD, UPDATE, DELETE, or NOOP."""
        repo = ProfileAttributeRepository(session)
        for mem in memories:
            # Skip items with no value (LLM returns null when key was not mentioned)
            if mem.value is None and not mem.is_negation:
                continue
            existing = await repo.get_by_key(user_id, mem.key)
            if mem.is_negation and existing:
                await repo.delete(user_id, mem.key)
            elif not existing:
                if mem.confidence >= _CONFIDENCE_THRESHOLD:
                    await repo.upsert(
                        user_id=user_id,
                        key=mem.key,
                        value=mem.value,
                        confidence=mem.confidence,
                    )
            elif mem.value is not None and is_semantically_same(existing.value, mem.value):
                pass  # NOOP
            elif mem.value is not None and mem.confidence >= existing.confidence:
                await repo.upsert(
                    user_id=user_id,
                    key=mem.key,
                    value=mem.value,
                    confidence=mem.confidence,
                )
            # else: NOOP (lower confidence)

    @staticmethod
    async def _upsert_interests(
        session: AsyncSession,
        user_id: uuid.UUID,
        extraction: MemoryExtractionResult,
        current_conv_idx: int,
    ) -> set[str]:
        """Upsert interest keywords via the post-processing pipeline."""
        from coyo.services.embedding import get_embedding_service
        from coyo.services.iab_taxonomy import get_iab_taxonomy_service
        from coyo.services.keyword_postprocessor import (
            KeywordPostprocessor,
            RawKeyword,
        )

        repo = InterestRepository(session)

        # Build raw keywords from LLM extraction
        raw_keywords = [
            RawKeyword(
                keyword=item.keyword,
                keyword_type="category",
                is_news_relevant=item.is_news_relevant,
                summary=item.summary,
            )
            for item in extraction.categories[:MAX_CATEGORIES]
            if item.keyword
        ] + [
            RawKeyword(
                keyword=item.keyword,
                keyword_type="entity",
                is_news_relevant=item.is_news_relevant,
                summary=item.summary,
            )
            for item in extraction.entities[:MAX_ENTITIES]
            if item.keyword
        ]

        # Fetch existing keywords for deduplication
        existing_keyword_texts = await repo.get_existing_keywords(user_id)

        # Run post-processing pipeline (Process A/B/C)
        postprocessor = KeywordPostprocessor(
            embedding_service=get_embedding_service(),
            iab_taxonomy_service=get_iab_taxonomy_service(),
        )
        processed = await postprocessor.process(raw_keywords, existing_keyword_texts)

        # Upsert processed keywords
        seen_keywords: set[str] = set()
        for kw in processed:
            target = kw.merge_target or kw.keyword
            if target not in seen_keywords:
                seen_keywords.add(target)
                await repo.upsert_interest(
                    user_id=user_id,
                    keyword=target,
                    keyword_type=kw.keyword_type,
                    is_news_relevant=kw.is_news_relevant,
                    current_conv_idx=current_conv_idx,
                    summary=kw.summary if kw.merge_target is None else None,
                    iab_category_id=kw.iab_category_id,
                )

        return seen_keywords

    @staticmethod
    async def _regenerate_interest_summaries(
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> None:
        """Regenerate summaries for interests with needs_summary_update=True."""
        interest_repo = InterestRepository(session)
        conv_summary_repo = ConversationSummaryRepository(session)
        settings = get_settings()

        interests = await interest_repo.get_interests_needing_summary_update(user_id)
        if not interests:
            return

        recent_summaries = await conv_summary_repo.get_latest_for_user(
            user_id, limit=10
        )

        llm = OpenAIClient(model=settings.llm_interest_model)

        for interest in interests:
            related = [
                s
                for s in recent_summaries
                if _keyword_matches(interest.keyword, s.summary)
                or (s.source_keyword and _keyword_matches(interest.keyword, s.source_keyword))
            ]
            related_text = "\n".join(
                f"- {s.topic_title}: {s.summary}" for s in related
            )
            if not related_text:
                related_text = "(no related conversations found)"

            existing_summary = interest.summary or "(none)"

            prompt = _INTEREST_SUMMARY_PROMPT.format(
                keyword=interest.keyword,
                existing_summary=existing_summary,
                related_conversations=related_text,
            )

            try:
                messages = [
                    ChatMessage(role="system", content=prompt),
                    ChatMessage(
                        role="user",
                        content=f"Generate summary for: {interest.keyword}",
                    ),
                ]
                response = await llm.structured(
                    messages,
                    response_model=_SummaryResponse,
                    options=ChatOptions(temperature=0.3, max_tokens=256),
                )
                if response.summary:
                    trimmed = trim_to_word_boundary(response.summary)
                    await interest_repo.update_summary(
                        user_id, interest.keyword, trimmed
                    )
            except Exception:
                logger.exception(
                    "interest_summary_regeneration_failed",
                    keyword=interest.keyword,
                    user_id=str(user_id),
                )

    @staticmethod
    async def _regenerate_profile_summary(
        session: AsyncSession,
        user_id: uuid.UUID,
        current_conv_idx: int,
    ) -> None:
        """Regenerate the user's profile summary narrative."""
        attr_repo = ProfileAttributeRepository(session)
        interest_repo = InterestRepository(session)
        conv_summary_repo = ConversationSummaryRepository(session)
        profile_repo = ProfileSummaryRepository(session)
        settings = get_settings()

        # Gather data
        attributes = await attr_repo.get_all_for_user(user_id)
        top_interests = await interest_repo.get_top_interests(
            user_id, current_conv_idx, limit=10
        )
        recent_convs = await conv_summary_repo.get_latest_for_user(user_id, limit=5)

        attrs_text = "\n".join(
            f"- {a.key}: {a.value}" for a in attributes
        )
        if not attrs_text:
            attrs_text = "(no attributes yet)"

        interests_text = "\n".join(
            f"- {i.keyword}: {i.summary or '(no summary)'}" for i in top_interests
        )
        if not interests_text:
            interests_text = "(no interests yet)"

        convs_text = "\n".join(
            f"- {c.topic_title}: {c.summary}" for c in recent_convs
        )
        if not convs_text:
            convs_text = "(no recent conversations)"

        prompt = _PROFILE_SUMMARY_PROMPT.format(
            user_profile_attributes=attrs_text,
            interests_with_summaries=interests_text,
            recent_conversations=convs_text,
        )

        try:
            llm = OpenAIClient(model=settings.llm_interest_model)
            messages = [
                ChatMessage(role="system", content=prompt),
                ChatMessage(role="user", content="Generate user profile summary."),
            ]
            response = await llm.structured(
                messages,
                response_model=_ProfileSummaryResponse,
                options=ChatOptions(temperature=0.5, max_tokens=1024),
            )
            if response.summary:
                await profile_repo.upsert(
                    user_id=user_id,
                    summary=response.summary,
                    conversation_count_at_update=current_conv_idx,
                )
        except Exception:
            logger.exception(
                "profile_summary_regeneration_failed",
                user_id=str(user_id),
            )


# ---------------------------------------------------------------------------
# Response models for sub-LLM calls
# ---------------------------------------------------------------------------


class _SummaryResponse(BaseModel):
    """LLM response for interest summary regeneration."""

    summary: str | None = None


class _ProfileSummaryResponse(BaseModel):
    """LLM response for profile summary regeneration."""

    summary: str | None = None
