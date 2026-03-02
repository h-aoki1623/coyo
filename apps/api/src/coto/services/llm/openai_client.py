"""OpenAI implementation of the LLM client interface."""

from collections.abc import AsyncIterator

from openai import AsyncOpenAI
from pydantic import BaseModel

from coto.config import get_settings
from coto.exceptions import ExternalServiceError
from coto.services.llm.base import ChatMessage, ChatOptions, LLMClient, ModelInfo


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
