"""Service for extracting user memories, interests, and summaries from conversations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import structlog
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select, update

from coyo.config import get_settings
from coyo.db import get_session_factory
from coyo.exceptions import ExternalServiceError
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
MAX_ENTITIES = 3
_MAX_KEYWORD_LENGTH = 100
_MAX_SUMMARY_LENGTH = 200
_CONFIDENCE_THRESHOLD = 0.5
_BATCH_INTERVAL = 5


# ---------------------------------------------------------------------------
# Pydantic models for LLM structured output
# ---------------------------------------------------------------------------


class MemoryItem(BaseModel):
    """A single extracted user profile attribute."""

    key: Literal["english_goal", "job_industry", "hometown_or_location", "family_status"]
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
    def normalize_raw_categories_and_entities(cls, data: dict[str, object]) -> dict[str, object]:
        """Normalize plain strings in categories/entities to dicts before validation.

        LLMs sometimes return plain keyword strings instead of full objects.
        This converts them to the expected dict format before Pydantic validates.
        """
        if isinstance(data, dict):
            for field in ("categories", "entities"):
                items = data.get(field, [])
                if isinstance(items, list):
                    data[field] = [
                        {"keyword": item} if isinstance(item, str) else item for item in items
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

=== INTERESTS (CATEGORIES & ENTITIES) ===

--- STEP 1: SIGNAL DETECTION ---
Extract a category or entity ONLY when at least one signal is present.
Merely MENTIONING a topic is NOT a signal — the user must show engagement,
enthusiasm, or ongoing involvement.

[Explicit Signals — high confidence]
- User directly states interest: "I love X", "I'm really into X", "I'm a fan of X"
- User describes ongoing engagement: "I've been following X", "I practice X every day"
- User shows sustained enthusiasm across multiple turns about the same topic
- User asks curiosity-driven follow-up questions about a topic

[Implicit Signals — medium confidence]
- User demonstrates specialized knowledge that indicates deep familiarity
  (e.g., discusses specific political details → politics)
- Interest in a specific entity implies the parent category
  (e.g., fan of Max Verstappen → F1)
- Multiple casual references to sub-categories of the same parent → extract parent
  (e.g., mentions watching tennis, soccer, and baseball occasionally → "sports")
- User describes habitual behavior tied to a topic
  (e.g., "I check my portfolio every morning" → personal investing)
- User shows repeated engagement with or positive sentiment toward
  a specific category or entity across the conversation

[No Signal = No Extraction]
If no explicit or implicit signal is present, return empty lists.

--- STEP 2: EXCLUSION FILTER ---
Even if a signal seems present, DO NOT extract if ANY of these apply:

1. TRANSACTIONAL CONTEXT: Topic appears only because the user is conducting business
   (hotel check-in ≠ travel; bank visit ≠ finance; doctor visit ≠ health)
2. NON-CELEBRITY NAMES: Personal names from dialogue that are not public figures
   (Dick, Leo, Bob, Kate, Olga → skip. Elon Musk, Carlos Alcaraz → extract)
3. AI-SIDE INTEREST: Topic is introduced/discussed primarily by the AI, not the user
4. DAILY ROUTINE: Eating, drinking coffee, smoking, commuting — unless user shows genuine
   passion beyond routine (e.g., "I love trying different coffee beans from around the world"
   = interest; "let's get coffee" = routine)
5. CONVERSATION-SCOPED: User's interest is limited to this conversation's context only
   ("I'm curious about that" in response to AI introducing a topic → skip)
6. AMBIGUOUS CONTEXT: Multiple plausible explanations exist and none clearly indicates interest
   (being in a hotel lobby could be work travel, tourism, or just a meeting location)
7. CASUAL MENTION: Topic touched on in passing without follow-up, enthusiasm, or depth
   (user mentions "America" once in passing ≠ interest in America)
8. GENERIC LOCATIONS: Countries/cities mentioned as contextual background, not as places the
   user is genuinely interested in (e.g., "I work in London" ≠ interest in London)
9. LANGUAGE LEARNING ACTIVITY: This app is for English conversation practice, so
   language learning topics (grammar, pronunciation, vocabulary, language learning itself)
   are the app's purpose, not user interests. Do NOT extract them.

--- STEP 3: FORMATTING RULES ---

[For categories]
- categories: broad interest subjects (max 3, English, lowercase)
- Must correspond to an IAB Content Taxonomy category (Tier 1 through Tier 4)
  e.g., "sports", "technology & computing"                ← Tier 1
        "tennis", "artificial intelligence"               ← Tier 2
        "running and jogging"                             ← Tier 3
        "herbs and supplements"                           ← Tier 4
- Common IAB label hints (use the exact IAB label):
  → saving/budgeting/investing talk → "personal finance" (NOT "financial services", "economics")
  → wars/military conflicts → "war and conflicts" (NOT "war")

[For entities]
- entities: specific proper nouns (max 3, English, lowercase)
- Must be a NOTABLE proper noun — a person, organization, product, or event that has
  a Wikipedia article or equivalent public presence
- DO NOT extract:
  → Personal names from conversation (Dick, Bob, Kate, Leo, Dr. Mustn)
  → Generic institutions without specific identity ("a bank", "the hospital")
  → Common nouns disguised as entities ("doctor", "player", "team")
  → Sub-components when the parent entity captures the interest
    (M2 chip → Apple is the interest; Focus mode → Apple; Flask → skip)
  → Entities mentioned only once with no positive reaction from the user
    (opponent teams, comparison targets, passing references)

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
- If two keywords refer to the same concept, keep only one.
  e.g., "grand slam" + "grand slam tournaments" → keep "grand slam" only
        "EV" + "electric vehicles" → keep "electric vehicles" (IAB term)

[is_news_relevant]
- true:  keyword generates regular news (sports, politics, economy, tech, etc.)
         Ask: does "{keyword} news" return fresh articles regularly?
- false: evergreen categories (food, daily life, grammar, hobbies)

--- EXAMPLES ---

Example 1 (transactional → extract nothing):
User: "I have a reservation for a double."
AI: "What's your last name?"
User: "It's Smith. Here is my driver's license."
→ categories: [], entities: []
Reason: Hotel check-in is transactional, not an expression of interest.

Example 2 (casual daily routine → extract nothing):
User: "So Dick, how about getting some coffee for tonight?"
AI: "I don't honestly like that kind of stuff."
User: "Come on, you can at least try."
→ categories: [], entities: []
Reason: Coffee is daily routine; Dick is a personal name, not a notable entity.

Example 3 (genuine interest — explicit + implicit signals):
User: "I went to the baseball game last weekend. It was amazing — a walk-off homer!"
User: "My tech stocks are up 15%. I check my portfolio almost every morning!"
→ categories: ["baseball", "personal investing"], entities: []
Reason: Baseball = explicit enthusiasm. Personal investing = habitual behavior (implicit signal).

Example 4 (entity interest implies parent category):
User: "I watched Carlos Alcaraz play last night!"
User: "I've been following him since his first grand slam."
→ categories: ["tennis"], entities: ["carlos alcaraz"]
Reason: Ongoing engagement with a specific athlete. Tennis implied by entity.

--- INTEREST SUMMARIES ---
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
{user_attributes}

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


def compose_summary_text(
    source_keyword: str | None,
    topic_title: str,
    summary: str,
) -> str:
    """Build the text used to embed a ConversationSummary.

    Mirrors the structure of theme text built by ``build_theme_context``
    so cosine similarity captures topical alignment, not stylistic noise.
    """
    head = source_keyword or topic_title
    return f"{head}\n{summary}"


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
                await MemoryExtractionService._extract(session, conversation_id, user_id)
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
            await MemoryExtractionService._extract(session, conversation_id, user_id)
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
        transcript = await MemoryExtractionService._build_transcript(session, conversation_id)
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
        await MemoryExtractionService._process_memories(session, user_id, extraction.memories)

        # 7. Upsert interests (categories + entities) via post-processing pipeline
        seen_keywords = await MemoryExtractionService._upsert_interests(
            session, user_id, extraction, current_conv_idx
        )

        # 8. Batch regeneration every N conversations
        if current_conv_idx % _BATCH_INTERVAL == 0:
            await MemoryExtractionService._regenerate_interest_summaries(session, user_id)
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
    async def extract_from_transcript(transcript: str) -> MemoryExtractionResult:
        """Extract memories, categories, and entities from a transcript.

        Public API for evaluation and testing. Uses the production prompt and
        model configuration to call the LLM.
        """
        return await MemoryExtractionService._call_llm(transcript)

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
        """Save the conversation summary with topic title and embedding.

        The embedding is computed from a composed string that mirrors what
        will be matched against the conversation theme later (theme + body).
        Embedding failures bubble up via ExternalServiceError so the broader
        memory extraction pipeline retries (Cloud Tasks at-least-once).
        """
        from coyo.services.embedding import get_embedding_service

        topic_title = "Free conversation"
        source_keyword: str | None = None

        if conversation.topic_suggestion_id is not None:
            suggestion = await session.get(TopicSuggestion, conversation.topic_suggestion_id)
            if suggestion is not None:
                topic_title = suggestion.title
                source_keyword = suggestion.source_keyword

        compose_text = compose_summary_text(source_keyword, topic_title, summary_text)
        embedding_service = get_embedding_service()
        embeddings = await embedding_service.embed([compose_text])
        embedding = embeddings[0] if embeddings else None

        repo = ConversationSummaryRepository(session)
        await repo.create(
            conversation_id=conversation.id,
            user_id=user_id,
            topic_title=topic_title,
            source_keyword=source_keyword,
            summary=summary_text,
            embedding=embedding,
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
                if mem.value is not None and mem.confidence >= _CONFIDENCE_THRESHOLD:
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

        # Upsert processed keywords. The embedding is reused from the
        # KeywordPostprocessor batch (already paid for during dedup) and
        # is persisted on the INSERT path only — see InterestRepository.
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
                    embedding=kw.embedding if kw.merge_target is None else None,
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

        recent_summaries = await conv_summary_repo.get_latest_for_user(user_id, limit=10)

        llm = OpenAIClient(model=settings.llm_interest_model)

        for interest in interests:
            related = [
                s
                for s in recent_summaries
                if _keyword_matches(interest.keyword, s.summary)
                or (s.source_keyword and _keyword_matches(interest.keyword, s.source_keyword))
            ]
            related_text = "\n".join(f"- {s.topic_title}: {s.summary}" for s in related)
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
                    # Re-embed only when the summary text actually changes,
                    # so we never recompute embeddings for total_mentions
                    # bumps. Same flush as the summary update.
                    new_embedding: list[float] | None = None
                    if not is_semantically_same(interest.summary or "", trimmed):
                        from coyo.services.embedding import get_embedding_service

                        embedding_service = get_embedding_service()
                        try:
                            vectors = await embedding_service.embed(
                                [f"{interest.keyword}: {trimmed}"]
                            )
                            new_embedding = vectors[0] if vectors else None
                        except ExternalServiceError:
                            logger.warning(
                                "interest_summary_embed_failed",
                                keyword=interest.keyword,
                                user_id=str(user_id),
                            )
                            new_embedding = None
                    await interest_repo.update_summary(
                        user_id,
                        interest.keyword,
                        trimmed,
                        embedding=new_embedding,
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
        top_interests = await interest_repo.get_top_interests(user_id, current_conv_idx, limit=10)
        recent_convs = await conv_summary_repo.get_latest_for_user(user_id, limit=5)

        attrs_text = "\n".join(f"- {a.key}: {a.value}" for a in attributes)
        if not attrs_text:
            attrs_text = "(no attributes yet)"

        interests_text = "\n".join(
            f"- {i.keyword}: {i.summary or '(no summary)'}" for i in top_interests
        )
        if not interests_text:
            interests_text = "(no interests yet)"

        convs_text = "\n".join(f"- {c.topic_title}: {c.summary}" for c in recent_convs)
        if not convs_text:
            convs_text = "(no recent conversations)"

        prompt = _PROFILE_SUMMARY_PROMPT.format(
            user_attributes=attrs_text,
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
