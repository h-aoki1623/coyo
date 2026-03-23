"""Task handler endpoints for Cloud Tasks callbacks."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from coyo.dependencies import verify_cloud_task_token
from coyo.services.interest_extraction import InterestExtractionService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class ExtractInterestsRequest(BaseModel):
    """Request body for interest extraction task."""

    conversation_id: uuid.UUID
    user_id: uuid.UUID


@router.post("/extract-interests", dependencies=[Depends(verify_cloud_task_token)])
async def extract_interests(body: ExtractInterestsRequest) -> dict[str, str]:
    """Handle interest extraction task from Cloud Tasks.

    Cloud Tasks retries on 5xx responses, so errors are propagated.
    """
    await InterestExtractionService.extract(body.conversation_id, body.user_id)
    return {"status": "ok"}
