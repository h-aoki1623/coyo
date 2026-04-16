"""OpenAI implementation of the LLM client interface."""

from collections.abc import AsyncIterator

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel

from coyo.config import get_settings
from coyo.exceptions import ExternalServiceError
from coyo.services.llm.base import (
    ChatMessage,
    ChatOptions,
    ChatStreamEvent,
    LLMClient,
    ModelInfo,
    TextChunk,
    WebSearchStarted,
)

logger = structlog.get_logger()


def _log_usage(model: str, method: str, usage: object) -> None:
    """Emit a structured log of OpenAI token usage for cache observability.

    Captures ``prompt_tokens_details.cached_tokens`` so cache-hit rate is
    visible to downstream log pipelines. Best-effort — never raises.
    """
    try:
        prompt_tokens = getattr(usage, "prompt_tokens", None) or getattr(
            usage, "input_tokens", None
        )
        completion_tokens = getattr(usage, "completion_tokens", None) or getattr(
            usage, "output_tokens", None
        )
        details = getattr(usage, "prompt_tokens_details", None) or getattr(
            usage, "input_tokens_details", None
        )
        cached_tokens = getattr(details, "cached_tokens", None) if details is not None else None
        cache_hit_ratio: float | None = None
        if prompt_tokens and cached_tokens is not None:
            cache_hit_ratio = round(cached_tokens / prompt_tokens, 4)
        logger.info(
            "openai_usage",
            model=model,
            method=method,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
            cache_hit_ratio=cache_hit_ratio,
        )
    except Exception as exc:  # pragma: no cover — observability must not break calls
        logger.warning("openai_usage_log_failed", error=str(exc))


class OpenAIClient(LLMClient):
    """LLM client backed by the OpenAI API.

    Supports streaming chat completions and structured JSON output.
    """

    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = model or settings.llm_conversation_model

    async def chat(  # type: ignore[override]
        self,
        messages: list[ChatMessage],
        options: ChatOptions | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat completion tokens from OpenAI.

        Yields individual text tokens as they are generated. Final chunk
        carries a ``usage`` field (via ``stream_options``) which we log
        for prompt-cache visibility.
        """
        opts = options or ChatOptions()
        try:
            stream = await self._client.chat.completions.create(  # type: ignore[call-overload]
                model=self._model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=opts.temperature,
                max_completion_tokens=opts.max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in stream:
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    _log_usage(self._model, "chat", usage)
                # Usage-only trailing chunk has no choices — skip safely.
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content is not None:
                    yield delta.content
        except Exception as exc:
            raise ExternalServiceError("OpenAI", str(exc)) from exc

    async def chat_with_tools(
        self,
        messages: list[ChatMessage],
        options: ChatOptions | None = None,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Stream chat events using the OpenAI Responses API with web search.

        Uses tool_choice="auto" so the model decides whether to search.
        Yields WebSearchStarted (at most once) and TextChunk events.
        """
        opts = options or ChatOptions()

        # Separate system message into `instructions` (Responses API convention)
        instructions: str | None = None
        input_messages: list[dict[str, str]] = []
        for m in messages:
            if m.role == "system":
                instructions = m.content
            else:
                input_messages.append({"role": m.role, "content": m.content})

        try:
            search_signalled = False
            stream = self._client.responses.stream(  # type: ignore[call-overload]
                model=self._model,
                instructions=instructions or "",
                input=input_messages,
                tools=[{"type": "web_search_preview"}],
                # "auto" lets the model decide whether a web search is needed
                tool_choice="auto",
                temperature=opts.temperature,
                max_output_tokens=opts.max_tokens,
            )
            async with stream as response:
                async for event in response:
                    event_type = getattr(event, "type", None)
                    if (
                        not search_signalled
                        and event_type == "response.web_search_call.in_progress"
                    ):
                        search_signalled = True
                        yield WebSearchStarted()
                    elif event_type == "response.output_text.delta":
                        delta = getattr(event, "delta", "")
                        if delta:
                            yield TextChunk(text=delta)
                    elif event_type == "response.completed":
                        final = getattr(event, "response", None)
                        usage = getattr(final, "usage", None)
                        if usage is not None:
                            _log_usage(self._model, "chat_with_tools", usage)
        except Exception as exc:
            logger.error("openai_responses_api_error", error=str(exc))
            raise ExternalServiceError("OpenAI", "Responses API stream failed") from exc

    async def structured[T: BaseModel](
        self,
        messages: list[ChatMessage],
        response_model: type[T],
        options: ChatOptions | None = None,
    ) -> T:
        """Generate a structured response using OpenAI JSON mode.

        Parses the raw JSON output into the given Pydantic model.
        """
        opts = options or ChatOptions()
        try:
            # TODO: Use response_format={"type": "json_object"} or
            #       the OpenAI structured outputs API once stable.
            #       For now, instruct the model to return JSON matching
            #       the schema and parse manually.
            response = await self._client.chat.completions.create(  # type: ignore[call-overload]
                model=self._model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=opts.temperature,
                max_completion_tokens=opts.max_tokens,
                response_format={"type": "json_object"},
            )
            usage = getattr(response, "usage", None)
            if usage is not None:
                _log_usage(self._model, "structured", usage)
            content = response.choices[0].message.content
            if content is None:
                raise ExternalServiceError("OpenAI", "Empty response content")
            import json as _json

            return response_model.model_validate(_json.loads(content))
        except ExternalServiceError:
            raise
        except Exception as exc:
            raise ExternalServiceError("OpenAI", str(exc)) from exc

    def get_model(self) -> ModelInfo:
        """Return metadata about the active OpenAI model."""
        return ModelInfo(provider="openai", model=self._model)
