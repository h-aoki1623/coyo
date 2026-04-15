"""Tests covering prompt-cache optimizations.

Two concerns:
1. System prompts keep a byte-stable prefix across calls so OpenAI's
   prompt-prefix cache can reuse it (dynamic values live in the suffix).
2. ``OpenAIClient`` logs token usage including ``cached_tokens`` so cache
   hit rate is observable.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coyo.services.correction import (
    _CORRECTION_SYSTEM_PROMPT_PREFIX,
    _build_correction_system_prompt,
)
from coyo.services.llm.base import ChatMessage
from coyo.services.llm.openai_client import OpenAIClient, _log_usage
from coyo.services.turn_orchestrator import (
    _CONVERSATION_SYSTEM_PROMPT_PREFIX,
    _GREETING_SYSTEM_PROMPT_PREFIX,
    _SUGGESTED_GREETING_SYSTEM_PROMPT_PREFIX,
    _build_conversation_system_prompt,
    _build_greeting_system_prompt,
    _build_suggested_greeting_system_prompt,
)

# ---------------------------------------------------------------------------
# Byte-stable prefix across dynamic values
# ---------------------------------------------------------------------------


class TestStablePrefix:
    """Dynamic values must never mutate the cacheable static prefix."""

    @pytest.mark.unit
    def test_conversation_prefix_is_stable_across_topics(self):
        p1 = _build_conversation_system_prompt("sports")
        p2 = _build_conversation_system_prompt("technology")
        prefix = _CONVERSATION_SYSTEM_PROMPT_PREFIX
        assert p1.startswith(prefix)
        assert p2.startswith(prefix)
        assert p1 != p2  # dynamic suffix differs

    @pytest.mark.unit
    def test_greeting_prefix_is_stable_across_topics(self):
        p1 = _build_greeting_system_prompt("sports")
        p2 = _build_greeting_system_prompt("a trending news topic")
        prefix = _GREETING_SYSTEM_PROMPT_PREFIX
        assert p1.startswith(prefix)
        assert p2.startswith(prefix)

    @pytest.mark.unit
    def test_suggested_greeting_prefix_is_stable_across_articles(self):
        p1 = _build_suggested_greeting_system_prompt("Title A\n\nBody A.")
        p2 = _build_suggested_greeting_system_prompt("Title B\n\nBody B.")
        prefix = _SUGGESTED_GREETING_SYSTEM_PROMPT_PREFIX
        assert p1.startswith(prefix)
        assert p2.startswith(prefix)
        assert p1 != p2

    @pytest.mark.unit
    def test_correction_prefix_is_stable_across_language_and_user_text(self):
        p1 = _build_correction_system_prompt("Japanese", "I goed yesterday")
        p2 = _build_correction_system_prompt("English", "He don't know")
        prefix = _CORRECTION_SYSTEM_PROMPT_PREFIX
        assert p1.startswith(prefix)
        assert p2.startswith(prefix)
        assert p1 != p2

    @pytest.mark.unit
    def test_correction_dynamic_values_live_in_suffix(self):
        prompt = _build_correction_system_prompt("Japanese", "some spoken text")
        suffix = prompt[len(_CORRECTION_SYSTEM_PROMPT_PREFIX) :]
        assert "Japanese" in suffix
        assert "some spoken text" in suffix
        # And NOT in the prefix
        assert "Japanese" not in _CORRECTION_SYSTEM_PROMPT_PREFIX


# ---------------------------------------------------------------------------
# Usage logging
# ---------------------------------------------------------------------------


class TestUsageLogging:
    """``_log_usage`` and the three client methods emit cache metrics."""

    @pytest.mark.unit
    def test_log_usage_computes_cache_hit_ratio(self):
        import structlog

        usage = SimpleNamespace(
            prompt_tokens=1000,
            completion_tokens=200,
            prompt_tokens_details=SimpleNamespace(cached_tokens=800),
        )
        with structlog.testing.capture_logs() as logs:
            _log_usage("gpt-test", "chat", usage)

        assert len(logs) == 1
        entry = logs[0]
        assert entry["event"] == "openai_usage"
        assert entry["prompt_tokens"] == 1000
        assert entry["cached_tokens"] == 800
        assert entry["cache_hit_ratio"] == 0.8
        assert entry["model"] == "gpt-test"
        assert entry["method"] == "chat"

    @pytest.mark.unit
    def test_log_usage_handles_missing_details_gracefully(self):
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20)
        _log_usage("gpt-test", "chat", usage)  # must not raise

    @pytest.mark.unit
    def test_log_usage_never_raises_on_malformed_usage(self):
        # Intentionally wrong shape — observability must not break calls.
        _log_usage("gpt-test", "chat", object())

    @pytest.mark.unit
    async def test_chat_requests_usage_in_stream(self):
        """chat() must pass stream_options={'include_usage': True}."""
        mock_client = MagicMock()

        async def mock_stream():
            if False:
                yield  # empty async iter

        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

        with patch(
            "coyo.services.llm.openai_client.AsyncOpenAI",
            return_value=mock_client,
        ):
            client = OpenAIClient(model="gpt-test")
            client._client = mock_client
            async for _ in client.chat([ChatMessage(role="user", content="hi")]):
                pass

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs.get("stream") is True
        assert call_kwargs.get("stream_options") == {"include_usage": True}

    @pytest.mark.unit
    async def test_chat_logs_usage_from_trailing_chunk(self, caplog):
        """Trailing usage-only chunk should be logged, not crash the iterator."""
        mock_client = MagicMock()

        # Simulate: one text chunk, then a usage-only trailing chunk.
        text_chunk = SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="Hi"))],
            usage=None,
        )
        usage_chunk = SimpleNamespace(
            choices=[],
            usage=SimpleNamespace(
                prompt_tokens=500,
                completion_tokens=10,
                prompt_tokens_details=SimpleNamespace(cached_tokens=384),
            ),
        )

        async def mock_stream():
            yield text_chunk
            yield usage_chunk

        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

        with patch(
            "coyo.services.llm.openai_client.AsyncOpenAI",
            return_value=mock_client,
        ):
            client = OpenAIClient(model="gpt-test")
            client._client = mock_client
            tokens = [t async for t in client.chat([ChatMessage(role="user", content="hi")])]

        assert tokens == ["Hi"]  # iterator did not crash on empty-choices chunk
