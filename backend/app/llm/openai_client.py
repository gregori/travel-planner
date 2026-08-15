import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.llm.base import (
    LLMMessage,
    LLMResponse,
    LLMStreamChunk,
    LLMTodosModelosFalharamError,
    ToolCall,
)

logger = logging.getLogger("travel_planner.llm")


def _message_to_dict(msg: LLMMessage) -> dict[str, Any]:
    d: dict[str, Any] = {"role": msg.role}
    if msg.content is not None:
        d["content"] = msg.content
    if msg.tool_call_id:
        d["tool_call_id"] = msg.tool_call_id
    if msg.name:
        d["name"] = msg.name
    if msg.tool_calls:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": _dumps(tc.arguments)},
            }
            for tc in msg.tool_calls
        ]
    return d


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


class OpenAICompatibleLLM:
    """Cliente OpenAI-compatible com cadeia de fallback de modelos (RNF-07).

    Aponta para um `base_url` configurável (gateway tipo opencode/OpenRouter).
    Tenta cada modelo da cadeia em ordem até um responder com sucesso.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_chain: list[str],
        timeout_seconds: float = 30.0,
    ) -> None:
        if not model_chain:
            raise ValueError("model_chain não pode ser vazio")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model_chain = model_chain
        self._timeout = timeout_seconds

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        erros: list[str] = []
        for modelo in self._model_chain:
            try:
                return await self._tenta_modelo(modelo, messages, tools)
            except Exception as exc:  # noqa: BLE001 - fallback intencional
                logger.warning("modelo %s falhou: %s", modelo, exc)
                erros.append(f"{modelo}: {exc}")
                continue
        raise LLMTodosModelosFalharamError(f"Todos os modelos da cadeia falharam: {'; '.join(erros)}")

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Streaming real via SSE do endpoint `/chat/completions` (RF-06).

        Tenta cada modelo da cadeia (RNF-07); o fallback só se aplica antes
        do primeiro pedaço de conteúdo chegar — depois disso, uma falha no
        meio do stream é propagada (evita duplicar texto já exibido).
        """
        erros: list[str] = []
        for modelo in self._model_chain:
            try:
                algo_emitido = False
                async for chunk in self._stream_modelo(modelo, messages, tools):
                    algo_emitido = True
                    yield chunk
                return
            except Exception as exc:  # noqa: BLE001 - fallback intencional
                logger.warning("modelo %s falhou no streaming: %s", modelo, exc)
                erros.append(f"{modelo}: {exc}")
                if algo_emitido:
                    raise
                continue
        raise LLMTodosModelosFalharamError(f"Todos os modelos da cadeia falharam: {'; '.join(erros)}")

    async def _stream_modelo(
        self,
        modelo: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None,
    ) -> AsyncIterator[LLMStreamChunk]:
        payload: dict[str, Any] = {
            "model": modelo,
            "messages": [_message_to_dict(m) for m in messages],
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        conteudo_total = ""
        tool_calls_acc: dict[int, dict[str, Any]] = {}
        finish_reason = "stop"

        async with (
            httpx.AsyncClient(timeout=self._timeout) as client,
            client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            ) as resp,
        ):
            resp.raise_for_status()
            async for linha in resp.aiter_lines():
                if not linha.startswith("data:"):
                    continue
                dado = linha[len("data:") :].strip()
                if dado == "[DONE]":
                    break
                try:
                    evento = json.loads(dado)
                except json.JSONDecodeError:
                    continue
                escolha = (evento.get("choices") or [{}])[0]
                delta = escolha.get("delta", {})
                if escolha.get("finish_reason"):
                    finish_reason = escolha["finish_reason"]

                texto = delta.get("content")
                if texto:
                    conteudo_total += texto
                    yield LLMStreamChunk(delta=texto)

                for tc_delta in delta.get("tool_calls") or []:
                    indice = tc_delta.get("index", 0)
                    acumulado = tool_calls_acc.setdefault(indice, {"id": "", "name": "", "arguments": ""})
                    if tc_delta.get("id"):
                        acumulado["id"] = tc_delta["id"]
                    funcao = tc_delta.get("function") or {}
                    if funcao.get("name"):
                        acumulado["name"] = funcao["name"]
                    if funcao.get("arguments"):
                        acumulado["arguments"] += funcao["arguments"]

        tool_calls = []
        for indice in sorted(tool_calls_acc):
            acumulado = tool_calls_acc[indice]
            try:
                args = json.loads(acumulado["arguments"]) if acumulado["arguments"] else {}
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(id=acumulado["id"] or f"call_{indice}", name=acumulado["name"], arguments=args)
            )

        resposta_final = LLMResponse(
            content=conteudo_total or None,
            tool_calls=tool_calls,
            modelo_usado=modelo,
            finish_reason=finish_reason,
        )
        yield LLMStreamChunk(resposta_final=resposta_final)

    async def _tenta_modelo(
        self,
        modelo: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": modelo,
            "messages": [_message_to_dict(m) for m in messages],
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        escolha = data["choices"][0]
        msg = escolha["message"]
        tool_calls = []
        for tc in msg.get("tool_calls") or []:
            try:
                args = json.loads(tc["function"]["arguments"])
            except (json.JSONDecodeError, KeyError):
                args = {}
            tool_calls.append(ToolCall(id=tc["id"], name=tc["function"]["name"], arguments=args))

        return LLMResponse(
            content=msg.get("content"),
            tool_calls=tool_calls,
            modelo_usado=data.get("model", modelo),
            finish_reason=escolha.get("finish_reason", "stop"),
        )
