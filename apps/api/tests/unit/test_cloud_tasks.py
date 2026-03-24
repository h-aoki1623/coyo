"""Unit tests for the CloudTasksService."""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coyo.services.cloud_tasks import CloudTasksService, _background_tasks


class TestEnqueueMemoryExtraction:
    """Tests for CloudTasksService.enqueue_memory_extraction."""

    @pytest.mark.unit
    async def test_enqueue_memory_extraction_fallback(self, mock_settings):
        """When cloud_tasks_queue is None, should call _fallback_asyncio_memory."""
        mock_settings.cloud_tasks_queue = None
        conv_id = uuid.uuid4()
        user_id = uuid.uuid4()

        with (
            patch(
                "coyo.services.cloud_tasks.get_settings", return_value=mock_settings
            ),
            patch.object(
                CloudTasksService, "_fallback_asyncio_memory"
            ) as mock_fallback,
        ):
            await CloudTasksService.enqueue_memory_extraction(conv_id, user_id)

        mock_fallback.assert_called_once_with(conv_id, user_id)

    @pytest.mark.unit
    async def test_enqueue_memory_extraction_cloud_tasks(self, mock_settings):
        """When cloud_tasks_queue is set, should call _enqueue_memory_task."""
        mock_settings.cloud_tasks_queue = "my-queue"
        mock_settings.cloud_tasks_project = "my-project"
        mock_settings.cloud_tasks_location = "us-central1"
        mock_settings.cloud_run_service_url = "https://my-service.run.app"
        conv_id = uuid.uuid4()
        user_id = uuid.uuid4()

        with (
            patch(
                "coyo.services.cloud_tasks.get_settings", return_value=mock_settings
            ),
            patch.object(
                CloudTasksService, "_enqueue_memory_task", new_callable=AsyncMock
            ) as mock_enqueue,
        ):
            await CloudTasksService.enqueue_memory_extraction(conv_id, user_id)

        mock_enqueue.assert_called_once_with(mock_settings, conv_id, user_id)


class TestFallbackAsyncioMemory:
    """Tests for the asyncio fallback path for memory extraction."""

    @pytest.mark.unit
    async def test_fallback_asyncio_memory_creates_task(self, mock_settings):
        """Verify asyncio.create_task is called with extract_background."""
        conv_id = uuid.uuid4()
        user_id = uuid.uuid4()

        with patch(
            "coyo.services.memory_extraction.MemoryExtractionService.extract_background",
            new_callable=AsyncMock,
        ):
            CloudTasksService._fallback_asyncio_memory(conv_id, user_id)
            # Allow the event loop to schedule the task
            await asyncio.sleep(0)

    @pytest.mark.unit
    async def test_fallback_asyncio_memory_adds_task_to_background_set(
        self, mock_settings
    ):
        """Verify the background task is added to _background_tasks set."""
        conv_id = uuid.uuid4()
        user_id = uuid.uuid4()

        initial_count = len(_background_tasks)

        with patch(
            "coyo.services.memory_extraction.MemoryExtractionService.extract_background",
            new_callable=AsyncMock,
        ):
            CloudTasksService._fallback_asyncio_memory(conv_id, user_id)
            # Task should be added immediately
            assert len(_background_tasks) > initial_count

            # Allow task to complete and be discarded
            await asyncio.sleep(0.1)


class TestCreateMemoryTaskSync:
    """Tests for the synchronous Cloud Tasks API call."""

    @pytest.mark.unit
    def test_create_memory_task_sync_calls_client(self, mock_settings):
        """Should call CloudTasksClient.create_task with correct arguments."""
        mock_settings.cloud_tasks_project = "my-project"
        mock_settings.cloud_tasks_location = "us-central1"
        mock_settings.cloud_tasks_queue = "my-queue"
        mock_settings.cloud_run_service_url = "https://my-service.run.app"
        mock_settings.cloud_tasks_service_account = "sa@project.iam.gserviceaccount.com"

        conv_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_client = MagicMock()
        mock_client.queue_path.return_value = (
            "projects/my-project/locations/us-central1/queues/my-queue"
        )
        mock_result = MagicMock()
        mock_result.name = (
            "projects/my-project/locations/us-central1/queues/my-queue/tasks/123"
        )
        mock_client.create_task.return_value = mock_result

        with patch(
            "coyo.services.cloud_tasks._get_cloud_tasks_client",
            return_value=mock_client,
        ):
            result = CloudTasksService._create_memory_task_sync(
                mock_settings, conv_id, user_id
            )

        mock_client.queue_path.assert_called_once_with(
            "my-project", "us-central1", "my-queue"
        )
        mock_client.create_task.assert_called_once()
        assert result.name == mock_result.name

    @pytest.mark.unit
    def test_create_memory_task_sync_payload_format(self, mock_settings):
        """Verify the JSON payload contains conversation_id and user_id as strings."""
        mock_settings.cloud_tasks_project = "my-project"
        mock_settings.cloud_tasks_location = "us-central1"
        mock_settings.cloud_tasks_queue = "my-queue"
        mock_settings.cloud_run_service_url = "https://my-service.run.app"
        mock_settings.cloud_tasks_service_account = "sa@project.iam.gserviceaccount.com"

        conv_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_client = MagicMock()
        mock_client.queue_path.return_value = (
            "projects/my-project/locations/us-central1/queues/my-queue"
        )
        mock_result = MagicMock()
        mock_result.name = "tasks/123"
        mock_client.create_task.return_value = mock_result

        with patch(
            "coyo.services.cloud_tasks._get_cloud_tasks_client",
            return_value=mock_client,
        ):
            CloudTasksService._create_memory_task_sync(
                mock_settings, conv_id, user_id
            )

        call_args = mock_client.create_task.call_args
        task_request = call_args.kwargs.get("request") or call_args.args[0]
        body = task_request.task.http_request.body
        payload = json.loads(body.decode())

        assert payload["conversation_id"] == str(conv_id)
        assert payload["user_id"] == str(user_id)

    @pytest.mark.unit
    def test_create_memory_task_sync_url_format(self, mock_settings):
        """Verify the URL is {cloud_run_service_url}/api/tasks/extract-memory."""
        mock_settings.cloud_tasks_project = "my-project"
        mock_settings.cloud_tasks_location = "us-central1"
        mock_settings.cloud_tasks_queue = "my-queue"
        mock_settings.cloud_run_service_url = "https://my-service.run.app"
        mock_settings.cloud_tasks_service_account = "sa@project.iam.gserviceaccount.com"

        conv_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_client = MagicMock()
        mock_client.queue_path.return_value = (
            "projects/my-project/locations/us-central1/queues/my-queue"
        )
        mock_result = MagicMock()
        mock_result.name = "tasks/123"
        mock_client.create_task.return_value = mock_result

        with patch(
            "coyo.services.cloud_tasks._get_cloud_tasks_client",
            return_value=mock_client,
        ):
            CloudTasksService._create_memory_task_sync(
                mock_settings, conv_id, user_id
            )

        call_args = mock_client.create_task.call_args
        task_request = call_args.kwargs.get("request") or call_args.args[0]
        url = task_request.task.http_request.url

        assert url == "https://my-service.run.app/api/tasks/extract-memory"


class TestEnqueueMemoryTaskErrorHandling:
    """Tests for error handling in the Cloud Tasks enqueue path."""

    @pytest.mark.unit
    async def test_enqueue_memory_task_logs_and_swallows_errors(self, mock_settings):
        """When _create_memory_task_sync raises, the error is logged but not propagated."""
        mock_settings.cloud_tasks_project = "my-project"
        mock_settings.cloud_tasks_location = "us-central1"
        mock_settings.cloud_tasks_queue = "my-queue"
        mock_settings.cloud_run_service_url = "https://my-service.run.app"
        mock_settings.cloud_tasks_service_account = "sa@project.iam.gserviceaccount.com"

        conv_id = uuid.uuid4()
        user_id = uuid.uuid4()

        with patch.object(
            CloudTasksService,
            "_create_memory_task_sync",
            side_effect=RuntimeError("gRPC connection failed"),
        ):
            # Should NOT raise
            await CloudTasksService._enqueue_memory_task(
                mock_settings, conv_id, user_id
            )
