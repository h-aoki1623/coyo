"""Orchestrates the SSE turn pipeline: STT -> LLM -> Correction -> TTS.

The turn orchestrator is the core of the real-time conversation flow.
When the user submits audio, this service coordinates the following steps
as a streaming SSE response:

1. **STT** - Transcribe user audio via OpenAI transcription API
   -> SSE event: stt_result

2. **LLM Reply (streaming)** - Generate AI conversational reply
   -> SSE events: ai_response_chunk (streamed tokens), ai_response_done

3. **Correction (async)** - Analyze user text for grammar/expression errors
   -> SSE event: correction_result

4. **TTS** - Generate speech for the AI reply
   -> SSE event: tts_audio_url

5. **Done**
   -> SSE event: turn_complete

Each step emits SSE events so the mobile client can update the UI
progressively without waiting for the entire pipeline to finish.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.config import get_settings
from coyo.repositories.conversation import ConversationRepository
from coyo.repositories.turn import TurnRepository
from coyo.services.correction import CorrectionService
from coyo.services.llm.base import ChatMessage, ChatOptions, TextChunk, WebSearchStarted
from coyo.services.llm.openai_client import OpenAIClient
from coyo.services.memory_context import MemoryContextService
from coyo.services.stt import STTService
from coyo.services.theme_context import build_theme_context
from coyo.services.tts import TTSService
from coyo.services.web_search_filter import is_filler_turn, strip_citations

logger = structlog.get_logger()

_STT_CONTEXT_TURN_COUNT = 4
_STT_MAX_PROMPT_CHARS = 800

# System prompts below are structured as [static prefix] + [dynamic suffix]
# so OpenAI's prompt-prefix cache can reuse the static portion across calls.
# Never interpolate a dynamic value into the prefix block — it defeats caching.

_CONVERSATION_SYSTEM_PROMPT_PREFIX = """\
You are a friendly English conversation partner.
Keep your responses natural, concise (2-3 sentences), and at an intermediate \
English level.
If the user makes a grammar mistake, don't correct them in the conversation — \
just respond naturally. Corrections are handled separately.
When you look up information, weave the facts into a natural conversational \
response — react with your own opinion or a follow-up question, don't just \
list facts. NEVER include URLs, links, citations, or source references.\
"""


_GREETING_SYSTEM_PROMPT_PREFIX = """\
You are a friendly English conversation partner named Coyo.
Generate a natural opening greeting to start the conversation. Keep it warm and inviting \
(2-3 sentences). Include exactly one open-ended question about the topic to encourage the \
user to respond. Speak at an intermediate English level.\
"""

_SUGGESTED_GREETING_SYSTEM_PROMPT_PREFIX = """\
You are a friendly English conversation partner named Coyo.
The user wants to discuss a trending topic they selected.
Since the user selected this topic, YOU start the conversation.
Open with a natural, engaging question or comment about this topic.
Keep it warm and inviting (2-3 sentences). Speak at an intermediate English level.\
"""


def _build_conversation_system_prompt(topic: str) -> str:
    """Compose the turn system prompt: static prefix + dynamic topic suffix."""
    return f"{_CONVERSATION_SYSTEM_PROMPT_PREFIX}\n\nCurrent topic: {topic}"


def _build_greeting_system_prompt(topic: str) -> str:
    """Compose the greeting system prompt: static prefix + dynamic topic suffix."""
    return f"{_GREETING_SYSTEM_PROMPT_PREFIX}\n\nCurrent topic: {topic}"


def _build_suggested_greeting_system_prompt(article_context: str) -> str:
    """Compose the suggested-greeting prompt with article context as suffix."""
    return (
        f"{_SUGGESTED_GREETING_SYSTEM_PROMPT_PREFIX}\n\n"
        "Background information (use naturally in conversation, don't quote directly):\n"
        f"{article_context}"
    )


def _make_event(event: str, data: dict[str, Any]) -> dict[str, Any]:
    """Build an SSE event dict with the given event name and data payload."""
    return {"event": event, "data": data}


class TurnOrchestrator:
    """Coordinates the multi-step turn processing pipeline.

    Constructed with a database session; all sub-services are built
    internally following the existing service-layer pattern.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._turn_repo = TurnRepository(session)
        self._conversation_repo = ConversationRepository(session)
        self._stt = STTService()
        self._tts = TTSService()
        self._correction = CorrectionService(session)

        settings = get_settings()
        self._llm = OpenAIClient(model=settings.llm_conversation_model)

    async def process_turn(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        audio_data: bytes,
        audio_filename: str = "audio.m4a",
        topic: str = "general",
    ) -> AsyncIterator[dict[str, Any]]:
        """Process a user turn and yield SSE event dicts.

        Args:
            conversation_id: The conversation this turn belongs to.
            user_id: The user who submitted the turn.
            audio_data: Raw audio bytes from the client.
            audio_filename: Original filename of the uploaded audio.
            topic: Conversation topic for the LLM system prompt.

        Yields:
            Dicts with "event" and "data" keys for SSE formatting.
        """
        log = logger.bind(
            conversation_id=str(conversation_id),
            user_id=str(user_id),
        )
        log.info("turn_pipeline_start")

        # -- Step 1: STT transcription ------------------------------------
        previous_turns = await self._turn_repo.get_by_conversation_id(
            conversation_id,
        )
        stt_prompt = self._format_stt_prompt(previous_turns, topic)
        user_text = await self._stt.transcribe(
            audio_data,
            filename=audio_filename,
            prompt=stt_prompt,
        )
        yield _make_event("stt_result", {"text": user_text})

        # -- Step 2: Save user turn to DB ---------------------------------
        next_sequence = (previous_turns[-1].sequence + 1) if previous_turns else 1
        user_turn = await self._turn_repo.create(
            conversation_id=conversation_id,
            role="user",
            text=user_text,
            sequence=next_sequence,
            correction_status="pending",
        )
        log.info("turn_user_saved", turn_id=str(user_turn.id), sequence=next_sequence)

        # -- Step 3: Build conversation history and stream LLM reply ------
        messages = await self._build_messages(
            conversation_id,
            user_text,
            user_id=user_id,
            topic=topic,
        )
        full_ai_text = ""

        if is_filler_turn(user_text):
            async for chunk in self._llm.chat(
                messages,
                options=ChatOptions(temperature=0.8, max_tokens=256),
            ):
                full_ai_text += chunk
                yield _make_event("ai_response_chunk", {"text": chunk})
        else:
            async for event in self._llm.chat_with_tools(
                messages,
                options=ChatOptions(temperature=0.8, max_tokens=256),
            ):
                if isinstance(event, WebSearchStarted):
                    yield _make_event("web_search_started", {})
                elif isinstance(event, TextChunk):
                    full_ai_text += event.text
                    yield _make_event("ai_response_chunk", {"text": event.text})

        # Always strip markdown citations/URLs — the Responses API may include
        # them even without an explicit web_search_call event being detected.
        full_ai_text = strip_citations(full_ai_text)

        yield _make_event("ai_response_done", {"text": full_ai_text})

        # -- Step 4: Save AI turn to DB -----------------------------------
        ai_sequence = next_sequence + 1
        ai_turn = await self._turn_repo.create(
            conversation_id=conversation_id,
            role="ai",
            text=full_ai_text,
            sequence=ai_sequence,
        )
        log.info("turn_ai_saved", turn_id=str(ai_turn.id), sequence=ai_sequence)

        # -- Step 5: Correction + TTS in parallel -------------------------
        correction_result: dict[str, Any] | None = None
        tts_url: str | None = None

        async with asyncio.TaskGroup() as tg:
            correction_task = tg.create_task(
                self._correction.analyze_turn(
                    turn_id=user_turn.id,
                    user_id=user_id,
                    user_text=user_text,
                )
            )
            tts_task = tg.create_task(self._tts.synthesize(full_ai_text))

        # TaskGroup ensures both tasks are done here
        turn_correction = correction_task.result()
        tts_url = tts_task.result()

        # Yield correction result
        if turn_correction is not None:
            correction_result = {
                "turnId": str(user_turn.id),
                "correctedText": turn_correction.corrected_text,
                "explanation": turn_correction.explanation,
                "items": [
                    {
                        "original": item.original,
                        "corrected": item.corrected,
                        "originalSentence": item.original_sentence,
                        "correctedSentence": item.corrected_sentence,
                        "type": item.type,
                        "explanation": item.explanation,
                    }
                    for item in await self._load_correction_items(turn_correction.id)
                ],
            }
            yield _make_event("correction_result", correction_result)

        # Yield TTS audio URL
        yield _make_event("tts_audio_url", {"url": tts_url})

        # -- Step 6: Commit all DB changes --------------------------------
        await self._session.commit()

        # -- Step 7: Done -------------------------------------------------
        yield _make_event("turn_complete", {})
        log.info("turn_pipeline_done")

    async def process_greeting(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        topic: str,
        article_context: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Generate an AI greeting and yield SSE event dicts.

        A simplified pipeline with no STT or correction — just LLM + TTS.
        When article_context is provided (suggested topics), uses a specialised
        system prompt that incorporates the article background.
        """
        log = logger.bind(conversation_id=str(conversation_id))
        log.info("greeting_pipeline_start")

        # Build messages: system prompt only (no user message)
        if article_context:
            system_prompt = _build_suggested_greeting_system_prompt(article_context)
        else:
            system_prompt = _build_greeting_system_prompt(topic)

        # Build the theme-aware memory snapshot once per conversation and
        # persist it on the Conversation row. The turn path will read it
        # back as-is so the system prompt is byte-stable across turns
        # (crucial for OpenAI/Anthropic prompt-cache hits).
        conversation = await self._conversation_repo.get_by_id(conversation_id)
        memory_context: str | None = None
        if conversation is not None:
            theme = await build_theme_context(conversation, self._session)
            memory_context = await MemoryContextService.build_context(
                self._session,
                user_id,
                theme=theme,
            )
            # Empty string sentinel: snapshot computed but no memory.
            text_to_store = memory_context if memory_context is not None else ""
            await self._conversation_repo.set_memory_context_text(
                conversation.id,
                text_to_store,
            )

        if memory_context:
            system_prompt = system_prompt + "\n\n" + memory_context

        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=system_prompt),
        ]

        # Stream LLM response
        full_ai_text = ""
        async for chunk in self._llm.chat(
            messages,
            options=ChatOptions(temperature=0.8, max_tokens=256),
        ):
            full_ai_text += chunk
            yield _make_event("ai_response_chunk", {"text": chunk})

        yield _make_event("ai_response_done", {"text": full_ai_text})

        # Save AI turn (sequence=1, role="ai")
        ai_turn = await self._turn_repo.create(
            conversation_id=conversation_id,
            role="ai",
            text=full_ai_text,
            sequence=1,
        )
        log.info("greeting_ai_saved", turn_id=str(ai_turn.id))

        # TTS
        tts_url = await self._tts.synthesize(full_ai_text)
        yield _make_event("tts_audio_url", {"url": tts_url})

        # Commit
        await self._session.commit()

        # Done
        yield _make_event("turn_complete", {})
        log.info("greeting_pipeline_done")

    @staticmethod
    def _format_stt_prompt(turns: list[Any], topic: str) -> str:
        """Format a prompt hint for the STT model.

        Combines the conversation topic with recent turn texts so the
        transcription model can leverage context for better accuracy,
        especially for proper nouns and domain-specific terms.
        """
        parts: list[str] = []

        topic_label = topic if topic != "suggested" else "a trending news topic"
        parts.append(f"Topic: {topic_label}.")

        # Use the last few turns as context (token limit is 244 for Whisper,
        # but gpt-4o-transcribe is more generous; keep it concise regardless)
        recent_turns = turns[-_STT_CONTEXT_TURN_COUNT:]
        for turn in recent_turns:
            parts.append(turn.text)

        prompt = " ".join(parts)
        # Truncate to stay within model prompt token limits
        return prompt[:_STT_MAX_PROMPT_CHARS]

    async def _build_messages(
        self,
        conversation_id: uuid.UUID,
        current_user_text: str,
        *,
        user_id: uuid.UUID,
        topic: str = "general",
    ) -> list[ChatMessage]:
        """Build the LLM message list from conversation history.

        Includes the system prompt, previous turns, and the current
        user message.
        """
        topic_label = topic if topic != "suggested" else "a trending news topic"
        system_prompt = _build_conversation_system_prompt(topic_label)

        memory_context = await self._read_or_compute_memory_snapshot(
            conversation_id=conversation_id,
            user_id=user_id,
        )
        if memory_context:
            system_prompt = system_prompt + "\n\n" + memory_context

        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=system_prompt),
        ]

        # Add previous turns as conversation history
        previous_turns = await self._turn_repo.get_by_conversation_id(
            conversation_id,
        )
        for turn in previous_turns:
            role = "user" if turn.role == "user" else "assistant"
            messages.append(ChatMessage(role=role, content=turn.text))

        # Add current user message
        messages.append(ChatMessage(role="user", content=current_user_text))
        return messages

    async def _read_or_compute_memory_snapshot(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> str | None:
        """Return the memory context snapshot for the given conversation.

        Reads ``Conversation.memory_context_text`` (set by the greeting
        path). When the snapshot is missing — only happens in eval/dev
        flows that bypass the greeting — computes a fresh snapshot and
        writes it via the race-safe conditional UPDATE so concurrent
        turns end up with byte-identical prompts.

        Returns ``None`` when the snapshot is the empty-string sentinel
        (computed but no memory available).
        """
        conversation = await self._conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            return None

        # Targeted refresh — never call session.refresh(conversation)
        # without column list, which would clobber unsaved attributes.
        self._session.expire(
            conversation,
            ["memory_context_text", "memory_context_built_at"],
        )
        await self._session.refresh(
            conversation,
            ["memory_context_text", "memory_context_built_at"],
        )

        snapshot = conversation.memory_context_text
        if snapshot is not None:
            return snapshot or None  # "" sentinel → no injection

        # Lazy compute path. The greeting path normally pre-fills this,
        # so we only get here in eval/dev or unusual flows.
        theme = await build_theme_context(conversation, self._session)
        memory_context = await MemoryContextService.build_context(
            self._session,
            user_id,
            theme=theme,
        )
        text = memory_context if memory_context is not None else ""
        winner = await self._conversation_repo.try_set_memory_context_text_if_null(
            conversation.id,
            text,
        )
        return winner or None

    async def _load_correction_items(
        self,
        turn_correction_id: uuid.UUID,
    ) -> list[Any]:
        """Load correction items for a TurnCorrection.

        Uses a fresh query to ensure items flushed in the same
        session are visible.
        """
        from sqlalchemy import select

        from coyo.models.correction import CorrectionItem

        stmt = select(CorrectionItem).where(
            CorrectionItem.turn_correction_id == turn_correction_id,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
