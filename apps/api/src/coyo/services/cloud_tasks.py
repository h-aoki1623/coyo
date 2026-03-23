"""Cloud Tasks client for enqueuing background work.

Falls back to asyncio.create_task() when Cloud Tasks is not configured
(local development).
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import structlog

from coyo.config import get_settings

if TYPE_CHECKING:
    import uuid

    from google.cloud import tasks_v2

    from coyo.config import Settings

logger = structlog.get_logger()

# Strong references to background tasks to prevent GC during execution.
# Used only in local fallback mode (asyncio.create_task).
_background_tasks: set[asyncio.Task[None]] = set()

# Cached Cloud Tasks client (lazy init, reuses gRPC channel).
_cloud_tasks_client: tasks_v2.CloudTasksClient | None = None


def _get_cloud_tasks_client() -> tasks_v2.CloudTasksClient:
    """Return a cached CloudTasksClient singleton."""
    global _cloud_tasks_client  # noqa: PLW0603
    if _cloud_tasks_client is None:
        from google.cloud import tasks_v2

        _cloud_tasks_client = tasks_v2.CloudTasksClient()
    return _cloud_tasks_client


class CloudTasksService:
    """Enqueue work via Cloud Tasks or fall back to asyncio."""

    @staticmethod
    async def enqueue_interest_extraction(
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Enqueue interest extraction for a completed conversation.

        When Cloud Tasks is configured, creates an HTTP task targeting
        the task handler endpoint. Otherwise, falls back to asyncio.create_task().
        """
        settings = get_settings()

        if not settings.cloud_tasks_queue:
            CloudTasksService._fallback_asyncio(conversation_id, user_id)
            return

        await CloudTasksService._enqueue_cloud_task(settings, conversation_id, user_id)

    @staticmethod
    def _fallback_asyncio(
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Local development fallback using asyncio.create_task."""
        from coyo.services.interest_extraction import InterestExtractionService

        logger.info(
            "cloud_tasks_fallback_asyncio",
            conversation_id=str(conversation_id),
            user_id=str(user_id),
        )
        task = asyncio.create_task(
            InterestExtractionService.extract_background(conversation_id, user_id)
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    @staticmethod
    async def _enqueue_cloud_task(
        settings: Settings,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Create an HTTP task in Cloud Tasks.

        Runs the blocking gRPC call in a thread to avoid blocking the event loop.
        Errors are logged but not propagated, so the caller's response is not affected.
        """
        try:
            result = await asyncio.to_thread(
                CloudTasksService._create_task_sync,
                settings,
                conversation_id,
                user_id,
            )
            logger.info(
                "cloud_task_enqueued",
                task_name=result.name,
                conversation_id=str(conversation_id),
                user_id=str(user_id),
            )
        except Exception:
            logger.exception(
                "cloud_task_enqueue_failed",
                conversation_id=str(conversation_id),
                user_id=str(user_id),
            )

    @staticmethod
    def _create_task_sync(
        settings: Settings,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tasks_v2.Task:
        """Blocking Cloud Tasks API call (run via asyncio.to_thread)."""
        from google.cloud import tasks_v2

        client = _get_cloud_tasks_client()
        parent = client.queue_path(
            settings.cloud_tasks_project,
            settings.cloud_tasks_location,
            settings.cloud_tasks_queue,
        )

        payload = json.dumps({
            "conversation_id": str(conversation_id),
            "user_id": str(user_id),
        })

        task_request = tasks_v2.CreateTaskRequest(
            parent=parent,
            task=tasks_v2.Task(
                http_request=tasks_v2.HttpRequest(
                    http_method=tasks_v2.HttpMethod.POST,
                    url=f"{settings.cloud_run_service_url}/api/tasks/extract-interests",
                    headers={"Content-Type": "application/json"},
                    body=payload.encode(),
                    oidc_token=tasks_v2.OidcToken(
                        service_account_email=settings.cloud_tasks_service_account,
                        audience=settings.cloud_run_service_url,
                    ),
                ),
            ),
        )

        return client.create_task(request=task_request)
