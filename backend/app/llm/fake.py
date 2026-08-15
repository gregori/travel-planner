from collections.abc import AsyncIterator
from typing import Any

from app.llm.base import LLMMessage, LLMResponse, LLMStreamChunk, LLMTodosModelosFalharamError, ToolCall


class FakeLLM:
    """Cliente LLM determinístico para testes (RNF-03).

    Recebe um roteiro (`script`) de respostas pré-definidas e as retorna em
    sequência a cada chamada de `complete`, sem nenhuma rede envolvida.

    `falha_modelos` permite simular modelos indisponíveis na cadeia de
    fallback (RNF-07): a primeira chamada tentará esses modelos e falhará
    antes de responder com o próximo modelo saudável da cadeia.
    """

    def __init__(
        self,
        script: list[LLMResponse],
        model_chain: list[str] | None = None,
        falha_modelos: set[str] | None = None,
    ) -> None:
        self._script = list(script)
        self._idx = 0
        self._model_chain = model_chain or ["fake-model-primario"]
        self._falha_modelos = falha_modelos or set()
        self.modelos_tentados: list[str] = []

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        if self._idx >= len(self._script):
            raise LLMTodosModelosFalharamError("FakeLLM: roteiro esgotado")
        resposta = self._script[self._idx]
        self._idx += 1

        for modelo in self._model_chain:
            self.modelos_tentados.append(modelo)
            if modelo in self._falha_modelos:
                continue
            resposta.modelo_usado = modelo
            return resposta

        raise LLMTodosModelosFalharamError(f"Todos os modelos falharam (simulado): {self._model_chain}")

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Simula streaming dividindo o conteúdo do roteiro em palavras —
        determinístico, sem rede (RNF-03), mas exercita o mesmo caminho de
        emissão incremental usado pelo cliente real (RF-06)."""
        resposta = await self.complete(messages, tools)
        if resposta.content:
            palavras = resposta.content.split(" ")
            for i, palavra in enumerate(palavras):
                pedaco = palavra if i == len(palavras) - 1 else palavra + " "
                yield LLMStreamChunk(delta=pedaco)
        yield LLMStreamChunk(resposta_final=resposta)


def resposta_texto(texto: str, modelo: str = "fake-model") -> LLMResponse:
    return LLMResponse(content=texto, tool_calls=[], modelo_usado=modelo)


def resposta_tool_call(nome: str, argumentos: dict[str, Any], call_id: str = "call_1") -> LLMResponse:
    return LLMResponse(
        content=None,
        tool_calls=[ToolCall(id=call_id, name=nome, arguments=argumentos)],
        modelo_usado="fake-model",
        finish_reason="tool_calls",
    )
