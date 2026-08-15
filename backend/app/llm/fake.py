from collections.abc import AsyncIterator
from typing import Any

from app.llm.base import AllModelsFailedError, LLMMessage, LLMResponse, LLMStreamChunk, ToolCall


class FakeLLM:
    """Cliente LLM determinístico para testes (RNF-03).

    Recebe um roteiro (`script`) de respostas pré-definidas e as retorna em
    sequência a cada chamada de `complete`, sem nenhuma rede envolvida.

    `failing_models` permite simular modelos indisponíveis na cadeia de
    fallback (RNF-07): a primeira chamada tentará esses modelos e falhará
    antes de responder com o próximo modelo saudável da cadeia.
    """

    def __init__(
        self,
        script: list[LLMResponse],
        model_chain: list[str] | None = None,
        failing_models: set[str] | None = None,
    ) -> None:
        self._script = list(script)
        self._idx = 0
        self._model_chain = model_chain or ["fake-model-primary"]
        self._failing_models = failing_models or set()
        self.models_tried: list[str] = []

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        if self._idx >= len(self._script):
            raise AllModelsFailedError("FakeLLM: roteiro esgotado")
        response = self._script[self._idx]
        self._idx += 1

        for model in self._model_chain:
            self.models_tried.append(model)
            if model in self._failing_models:
                continue
            response.model_used = model
            return response

        raise AllModelsFailedError(f"Todos os modelos falharam (simulado): {self._model_chain}")

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Simula streaming dividindo o conteúdo do roteiro em palavras —
        determinístico, sem rede (RNF-03), mas exercita o mesmo caminho de
        emissão incremental usado pelo cliente real (RF-06)."""
        response = await self.complete(messages, tools)
        if response.content:
            words = response.content.split(" ")
            for i, word in enumerate(words):
                chunk = word if i == len(words) - 1 else word + " "
                yield LLMStreamChunk(delta=chunk)
        yield LLMStreamChunk(final_response=response)


def text_response(text: str, model: str = "fake-model") -> LLMResponse:
    return LLMResponse(content=text, tool_calls=[], model_used=model)


def tool_call_response(name: str, arguments: dict[str, Any], call_id: str = "call_1") -> LLMResponse:
    return LLMResponse(
        content=None,
        tool_calls=[ToolCall(id=call_id, name=name, arguments=arguments)],
        model_used="fake-model",
        finish_reason="tool_calls",
    )
