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


class OpenAIClient(LLMClient):
    """LLM client backed by the OpenAI API.

    Supports streaming chat completions and structured JSON output.
    """

    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = model or settings.llm_conversation_model

    async def chat(
        self,
        messages: list[ChatMessage],
        options: ChatOptions | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat completion tokens from OpenAI.

        Yields individual text tokens as they are generated.
        """
        opts = options or ChatOptions()
        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=opts.temperature,
                max_tokens=opts.max_tokens,
                stream=True,
            )
            async for chunk in stream:
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
            stream = self._client.responses.stream(
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
        except Exception as exc:
            logger.error("openai_responses_api_error", error=str(exc))
            raise ExternalServiceError(
                "OpenAI", "Responses API stream failed"
            ) from exc

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
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=opts.temperature,
                max_tokens=opts.max_tokens,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if content is None:
                raise ExternalServiceError("OpenAI", "Empty response content")
            return response_model.model_validate_json(content)
        except ExternalServiceError:
            raise
        except Exception as exc:
            raise ExternalServiceError("OpenAI", str(exc)) from exc

    def get_model(self) -> ModelInfo:
        """Return metadata about the active OpenAI model."""
        return ModelInfo(provider="openai", model=self._model)
