"""Abstract interface for LLM providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """A single message in a chat conversation."""

    role: str  # "system" | "user" | "assistant"
    content: str


class ChatOptions(BaseModel):
    """Configuration options for LLM inference."""

    temperature: float = 0.8
    max_tokens: int = 256


class ModelInfo(BaseModel):
    """Metadata about the active LLM model."""

    provider: str
    model: str


@dataclass(frozen=True)
class TextChunk:
    """A streamed text token from the LLM."""

    text: str


@dataclass(frozen=True)
class WebSearchStarted:
    """Signals that the LLM has initiated a web search."""


ChatStreamEvent = TextChunk | WebSearchStarted


class LLMClient(ABC):
    """Abstract interface for LLM providers.

    Implementations must support both streaming chat and
    structured (JSON-mode) output.
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        options: ChatOptions | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat completion tokens.

        Args:
            messages: The conversation history.
            options: Inference parameters.

        Yields:
            Individual text tokens as they are generated.
        """
        ...

    async def chat_with_tools(
        self,
        messages: list[ChatMessage],
        options: ChatOptions | None = None,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Stream chat events with tool support (e.g. web search).

        Default implementation delegates to chat() yielding TextChunk only.
        """
        async for chunk in self.chat(messages, options):
            yield TextChunk(text=chunk)

    @abstractmethod
    async def structured[T: BaseModel](
        self,
        messages: list[ChatMessage],
        response_model: type[T],
        options: ChatOptions | None = None,
    ) -> T:
        """Generate a structured response parsed into a Pydantic model.

        Args:
            messages: The conversation history.
            response_model: The Pydantic model class to parse the response into.
            options: Inference parameters.

        Returns:
            An instance of response_model populated from the LLM output.
        """
        ...

    @abstractmethod
    def get_model(self) -> ModelInfo:
        """Return metadata about the current model configuration."""
        ...
