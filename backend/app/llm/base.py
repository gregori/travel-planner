from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    model_used: str = ""
    finish_reason: str = "stop"


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str | None = None
    tool_call_id: str | None = None
    name: str | None = None
    tool_calls: list[ToolCall] | None = None


@dataclass
class LLMStreamChunk:
    """Um pedaço do streaming (RF-06). `delta` é um fragmento de texto que já
    pode ser exibido ao usuário assim que chega; `final_response` só vem
    preenchido no último chunk, com o texto completo e eventuais tool_calls."""

    delta: str | None = None
    final_response: LLMResponse | None = None


class AllModelsFailedError(Exception):
    """Nenhum modelo da cadeia de fallback respondeu (RNF-07)."""


class LLMClient(Protocol):
    """Interface que isola o agente do provedor de LLM (REQUIREMENTS.md §9)."""

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse: ...

    def stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Streaming de texto (RF-06): emite pedaços de conteúdo assim que
        ficam disponíveis, terminando com um chunk contendo `final_response`
        (mesmo formato de `complete`, incluindo tool_calls se houver)."""
        ...
