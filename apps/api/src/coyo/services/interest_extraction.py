"""Service for extracting user interests from conversation transcripts."""

import uuid

import structlog
from pydantic import BaseModel, field_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.config import get_settings
from coyo.db import get_session_factory
from coyo.models.conversation import Conversation
from coyo.models.turn import Turn
from coyo.models.user import User
from coyo.repositories.interest import InterestRepository
from coyo.services.llm.base import ChatMessage, ChatOptions
from coyo.services.llm.openai_client import OpenAIClient

logger = structlog.get_logger()

_EXTRACTION_SYSTEM_PROMPT = """\
Extract keywords from the English conversation.

Return JSON:
{
  "topics": [
    { "keyword": "tennis", "is_news_relevant": true },
    { "keyword": "dining out", "is_news_relevant": false }
  ],
  "entities": [
    { "keyword": "kei nishikori", "is_news_relevant": true },
    { "keyword": "pasta carbonara", "is_news_relevant": false }
  ]
}
Rules:
- topics: broad subjects (max 3)
- entities: specific proper nouns (max 5)
- Deduplicate within each list
- ALL keywords must be in English, lowercase
- is_news_relevant: judge by the CATEGORY of the keyword, not by how \
the user mentioned it. true for categories that regularly produce news \
(sports, politics, economy, tech, entertainment, companies, athletes, etc.) \
false for inherently evergreen categories (cooking, travel tips, daily \
routines, language learning, personal hobbies with no pro scene). \
Example: "tennis" is true (pro tournaments exist) even if the user said \
"I play tennis" rather than "I watch tennis"."""


_MAX_KEYWORD_LENGTH = 100
MAX_TOPICS = 3
MAX_ENTITIES = 5


class KeywordItem(BaseModel):
    """A single extracted keyword with news relevance flag."""

    keyword: str
    is_news_relevant: bool

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, v: str) -> str:
        v = v.lower().strip()
        if len(v) > _MAX_KEYWORD_LENGTH:
            v = v[:_MAX_KEYWORD_LENGTH]
        return v


class ExtractionResult(BaseModel):
    """LLM response model for interest extraction."""

    topics: list[KeywordItem] = []
    entities: list[KeywordItem] = []


class InterestExtractionService:
    """Extracts interest keywords from conversations and persists them."""

    @staticmethod
    async def extract_background(
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Run interest extraction in an independent session.

        Designed to be called via asyncio.create_task after conversation ends.
        Errors are logged but never propagated.
        """
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                await InterestExtractionService._extract(
                    session, conversation_id, user_id
                )
                await session.commit()
        except Exception:
            logger.exception(
                "interest_extraction_failed",
                conversation_id=str(conversation_id),
                user_id=str(user_id),
            )

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
                "interest_extraction_conversation_not_found",
                conversation_id=str(conversation_id),
            )
            return
        if conversation.interests_extracted:
            logger.info(
                "interest_extraction_already_done",
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
                "interest_extraction_user_not_found",
                user_id=str(user_id),
            )
            return
        current_conv_idx = row[0]

        # 3. Build transcript (user turns only)
        transcript = await InterestExtractionService._build_transcript(
            session, conversation_id
        )
        if not transcript.strip():
            logger.info(
                "interest_extraction_empty_transcript",
                conversation_id=str(conversation_id),
            )
            conversation.interests_extracted = True
            await session.flush()
            return

        # 4. LLM extraction
        extraction = await InterestExtractionService._call_llm(transcript)

        # 5. Upsert interests
        repo = InterestRepository(session)
        seen_keywords: set[str] = set()

        for item in extraction.topics[:MAX_TOPICS]:
            if item.keyword and item.keyword not in seen_keywords:
                seen_keywords.add(item.keyword)
                await repo.upsert_interest(
                    user_id=user_id,
                    keyword=item.keyword,
                    keyword_type="topic",
                    is_news_relevant=item.is_news_relevant,
                    current_conv_idx=current_conv_idx,
                )

        for item in extraction.entities[:MAX_ENTITIES]:
            if item.keyword and item.keyword not in seen_keywords:
                seen_keywords.add(item.keyword)
                await repo.upsert_interest(
                    user_id=user_id,
                    keyword=item.keyword,
                    keyword_type="entity",
                    is_news_relevant=item.is_news_relevant,
                    current_conv_idx=current_conv_idx,
                )

        # 6. Mark as extracted
        conversation.interests_extracted = True
        await session.flush()
        logger.info(
            "interest_extraction_complete",
            conversation_id=str(conversation_id),
            keywords_count=len(seen_keywords),
        )

    @staticmethod
    async def _build_transcript(
        session: AsyncSession,
        conversation_id: uuid.UUID,
    ) -> str:
        """Build a transcript of user-only turns for the conversation."""
        stmt = (
            select(Turn.text)
            .where(
                Turn.conversation_id == conversation_id,
                Turn.role == "user",
            )
            .order_by(Turn.sequence)
        )
        result = await session.execute(stmt)
        texts = result.scalars().all()
        return "\n".join(texts)

    @staticmethod
    async def _call_llm(transcript: str) -> ExtractionResult:
        """Call LLM to extract topics and entities from transcript."""
        settings = get_settings()
        llm = OpenAIClient(model=settings.llm_interest_model)

        messages = [
            ChatMessage(role="system", content=_EXTRACTION_SYSTEM_PROMPT),
            ChatMessage(role="user", content=transcript),
        ]

        return await llm.structured(
            messages,
            response_model=ExtractionResult,
            options=ChatOptions(temperature=0.3, max_tokens=512),
        )
