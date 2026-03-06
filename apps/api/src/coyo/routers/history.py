"""Conversation history endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.dependencies import get_current_user, get_db
from coyo.exceptions import NotFoundError
from coyo.models.user import User
from coyo.repositories.history import HistoryRepository
from coyo.schemas.correction import TurnCorrectionResponse
from coyo.schemas.history import (
    BatchDeleteRequest,
    HistoryDetailResponse,
    HistoryListItem,
    HistoryListResponse,
)
from coyo.schemas.turn import TurnResponse

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=HistoryListResponse)
async def list_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
) -> HistoryListResponse:
    """List conversation history for the current user.

    Supports pagination via page and per_page query parameters.
    """
    offset = (page - 1) * per_page
    repo = HistoryRepository(db)
    items, total = await repo.get_list_by_device_id(user.id, offset=offset, limit=per_page)
    return HistoryListResponse(
        items=[HistoryListItem.model_validate(c) for c in items],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{conversation_id}", response_model=HistoryDetailResponse)
async def get_history_detail(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HistoryDetailResponse:
    """Get detailed conversation history with turns and corrections."""
    repo = HistoryRepository(db)
    conversation = await repo.get_detail(conversation_id, user.id)
    if conversation is None:
        raise NotFoundError("Conversation", str(conversation_id))

    # Build turns and corrections as separate lists
    turns: list[TurnResponse] = []
    corrections: list[TurnCorrectionResponse] = []
    for turn in conversation.turns:
        turns.append(TurnResponse.model_validate(turn))
        if turn.correction is not None:
            corrections.append(TurnCorrectionResponse.model_validate(turn.correction))

    return HistoryDetailResponse(
        id=conversation.id,
        topic=conversation.topic,
        status=conversation.status,
        duration_seconds=conversation.duration_seconds,
        time_limit_seconds=conversation.time_limit_seconds,
        started_at=conversation.started_at,
        ended_at=conversation.ended_at,
        total_corrections=conversation.total_corrections,
        turns=turns,
        corrections=corrections,
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_history(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a single conversation from history."""
    repo = HistoryRepository(db)
    deleted = await repo.delete(conversation_id, user.id)
    if not deleted:
        raise NotFoundError("Conversation", str(conversation_id))
    await db.commit()


@router.post("/batch-delete", status_code=204)
async def batch_delete_history(
    body: BatchDeleteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete multiple conversations from history in a single request."""
    repo = HistoryRepository(db)
    await repo.batch_delete(body.ids, user.id)
    await db.commit()
