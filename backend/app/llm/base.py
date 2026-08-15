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
    modelo_usado: str = ""
    finish_reason: str = "stop"


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str | None = None
    tool_call_id: str | None = None
    name: str | None = None
    tool_calls: list[ToolCall] | None = None


class LLMTodosModelosFalharamError(Exception):
    """Nenhum modelo da cadeia de fallback respondeu (RNF-07)."""


class LLMClient(Protocol):
    """Interface que isola o agente do provedor de LLM (REQUIREMENTS.md §9)."""

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse: ...
