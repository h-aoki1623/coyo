"""Task handler endpoints for Cloud Tasks callbacks."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from coyo.dependencies import verify_cloud_task_token
from coyo.services.memory_extraction import MemoryExtractionService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class ExtractMemoryRequest(BaseModel):
    """Request body for memory extraction task."""

    conversation_id: uuid.UUID
    user_id: uuid.UUID


@router.post("/extract-memory", dependencies=[Depends(verify_cloud_task_token)])
async def extract_memory(body: ExtractMemoryRequest) -> dict[str, str]:
    """Handle memory extraction task from Cloud Tasks.

    Cloud Tasks retries on 5xx responses, so errors are propagated.
    """
    await MemoryExtractionService.extract(body.conversation_id, body.user_id)
    return {"status": "ok"}
