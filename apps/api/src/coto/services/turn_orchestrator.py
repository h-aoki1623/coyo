"""Orchestrates the SSE turn pipeline: STT -> LLM -> Correction -> TTS.

The turn orchestrator is the core of the real-time conversation flow.
When the user submits audio, this service coordinates the following steps
as a streaming SSE response:

1. **STT** - Transcribe user audio via OpenAI Whisper
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

from coto.config import get_settings
from coto.repositories.turn import TurnRepository
from coto.services.correction import CorrectionService
from coto.services.llm.base import ChatMessage, ChatOptions
from coto.services.llm.openai_client import OpenAIClient
from coto.services.stt import STTService
from coto.services.tts import TTSService

logger = structlog.get_logger()

_CONVERSATION_SYSTEM_PROMPT = """\
You are a friendly English conversation partner. The current topic is {topic}.
Keep your responses natural, concise (2-3 sentences), and at an intermediate \
English level.
If the user makes a grammar mistake, don't correct them in the conversation — \
just respond naturally. Corrections are handled separately.\
"""


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
    ) -> AsyncIterator[dict[str, Any]]:
        """Process a user turn and yield SSE event dicts.

        Args:
            conversation_id: The conversation this turn belongs to.
            user_id: The user who submitted the turn.
            audio_data: Raw audio bytes from the client.
            audio_filename: Original filename of the uploaded audio.

        Yields:
            Dicts with "event" and "data" keys for SSE formatting.
        """
        log = logger.bind(
            conversation_id=str(conversation_id),
            user_id=str(user_id),
        )
        log.info("turn_pipeline_start")

        # -- Step 1: STT transcription ------------------------------------
        user_text = await self._stt.transcribe(audio_data, filename=audio_filename)
        yield _make_event("stt_result", {"text": user_text})

        # -- Step 2: Save user turn to DB ---------------------------------
        next_sequence = await self._get_next_sequence(conversation_id)
        user_turn = await self._turn_repo.create(
            conversation_id=conversation_id,
            role="user",
            text=user_text,
            sequence=next_sequence,
            correction_status="pending",
        )
        log.info("turn_user_saved", turn_id=str(user_turn.id), sequence=next_sequence)

        # -- Step 3: Build conversation history and stream LLM reply ------
        messages = await self._build_messages(conversation_id, user_text)
        full_ai_text = ""

        async for chunk in self._llm.chat(
            messages,
            options=ChatOptions(temperature=0.8, max_tokens=256),
        ):
            full_ai_text += chunk
            yield _make_event("ai_response_chunk", {"text": chunk})

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

    async def _get_next_sequence(self, conversation_id: uuid.UUID) -> int:
        """Determine the next sequence number for a conversation."""
        turns = await self._turn_repo.get_by_conversation_id(conversation_id)
        if not turns:
            return 1
        return turns[-1].sequence + 1

    async def _build_messages(
        self,
        conversation_id: uuid.UUID,
        current_user_text: str,
    ) -> list[ChatMessage]:
        """Build the LLM message list from conversation history.

        Includes the system prompt, previous turns, and the current
        user message.
        """
        # Fetch the conversation to get the topic
        from coto.models.conversation import Conversation

        conversation = await self._session.get(Conversation, conversation_id)
        topic = conversation.topic if conversation else "general"

        system_prompt = _CONVERSATION_SYSTEM_PROMPT.format(topic=topic)
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

    async def _load_correction_items(
        self,
        turn_correction_id: uuid.UUID,
    ) -> list[Any]:
        """Load correction items for a TurnCorrection.

        Uses a fresh query to ensure items flushed in the same
        session are visible.
        """
        from sqlalchemy import select

        from coto.models.correction import CorrectionItem

        stmt = select(CorrectionItem).where(
            CorrectionItem.turn_correction_id == turn_correction_id,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
