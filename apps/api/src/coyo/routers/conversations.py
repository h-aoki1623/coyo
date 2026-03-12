"""Conversation and turn endpoints."""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from coyo.config import get_settings
from coyo.dependencies import get_current_user, get_db
from coyo.exceptions import ConversationStateError, ValidationError
from coyo.models.user import User
from coyo.rate_limit import DEFAULT_RATE_LIMIT, EXPENSIVE_RATE_LIMIT, limiter
from coyo.schemas.conversation import (
    ConversationResponse,
    CreateConversationRequest,
)
from coyo.schemas.correction import FeedbackResponse, TurnCorrectionResponse
from coyo.services.conversation import ConversationService
from coyo.services.turn_orchestrator import TurnOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=ConversationResponse, status_code=201)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def create_conversation(
    request: Request,
    body: CreateConversationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Start a new conversation session.

    Requires Firebase authentication.
    """
    service = ConversationService(db)
    conversation = await service.start_conversation(
        user_id=user.id,
        topic=body.topic,
    )
    return ConversationResponse.model_validate(conversation)


@router.post("/{conversation_id}/turns")
@limiter.limit(EXPENSIVE_RATE_LIMIT)
async def submit_turn(
    request: Request,
    conversation_id: uuid.UUID,
    audio: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """Submit a user audio turn and receive SSE events.

    Accepts multipart audio file upload. Returns a streaming SSE response
    with events for: stt_result, ai_response_chunk, ai_response_done,
    correction_result, tts_audio_url, turn_complete.
    """
    # Verify conversation exists, belongs to user, and is active
    service = ConversationService(db)
    conversation = await service.get_conversation(conversation_id, user.id)
    if conversation.status != "active":
        raise ConversationStateError(
            f"Cannot submit turn to conversation in '{conversation.status}' status. "
            "Only 'active' conversations accept new turns."
        )

    audio_data = await audio.read()

    # Validate file size to prevent abuse
    settings = get_settings()
    if len(audio_data) > settings.max_audio_size_bytes:
        raise ValidationError(
            f"Audio file exceeds maximum size of "
            f"{settings.max_audio_size_bytes // (1024 * 1024)} MB"
        )

    audio_filename = audio.filename or "audio.m4a"
    orchestrator = TurnOrchestrator(db)

    async def event_generator():
        try:
            async for event in orchestrator.process_turn(
                conversation_id=conversation_id,
                user_id=user.id,
                audio_data=audio_data,
                audio_filename=audio_filename,
            ):
                yield {"event": event["event"], "data": json.dumps(event["data"])}
        except Exception as exc:
            logger.error("Turn pipeline error: %s", exc, exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({
                    "code": "TURN_PROCESSING_FAILED",
                    "message": "An error occurred while processing your turn.",
                }),
            }

    return EventSourceResponse(event_generator())


@router.get("/{conversation_id}", response_model=ConversationResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def get_conversation(
    request: Request,
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Retrieve a conversation by ID."""
    service = ConversationService(db)
    conversation = await service.get_conversation(conversation_id, user.id)
    return ConversationResponse.model_validate(conversation)


@router.get(
    "/{conversation_id}/feedback",
    response_model=FeedbackResponse,
)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def get_feedback(
    request: Request,
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """Get feedback summary with corrections for a completed conversation.

    Returns total turn counts and a list of turn-level corrections.
    """
    service = ConversationService(db)
    stats = await service.get_feedback_with_stats(conversation_id, user.id)
    return FeedbackResponse(
        total_turns=stats.total_turns,
        total_corrections=stats.total_corrections,
        total_clean=stats.total_clean,
        corrections=[
            TurnCorrectionResponse.model_validate(c) for c in stats.corrections
        ],
    )


@router.post("/{conversation_id}/end", response_model=ConversationResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def end_conversation(
    request: Request,
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """End an active conversation and compute final metrics."""
    service = ConversationService(db)
    conversation = await service.end_conversation(conversation_id, user.id)
    return ConversationResponse.model_validate(conversation)


@router.post("/{conversation_id}/resume", response_model=ConversationResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def resume_conversation(
    request: Request,
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Resume a paused conversation."""
    service = ConversationService(db)
    conversation = await service.resume_conversation(conversation_id, user.id)
    return ConversationResponse.model_validate(conversation)
