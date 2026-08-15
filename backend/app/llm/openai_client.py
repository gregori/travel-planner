import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.llm.base import (
    AllModelsFailedError,
    LLMMessage,
    LLMResponse,
    LLMStreamChunk,
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
        errors: list[str] = []
        for model in self._model_chain:
            try:
                return await self._try_model(model, messages, tools)
            except Exception as exc:  # noqa: BLE001 - fallback intencional
                logger.warning("modelo %s falhou: %s", model, exc)
                errors.append(f"{model}: {exc}")
                continue
        raise AllModelsFailedError(f"Todos os modelos da cadeia falharam: {'; '.join(errors)}")

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
        errors: list[str] = []
        for model in self._model_chain:
            try:
                emitted_something = False
                async for chunk in self._stream_model(model, messages, tools):
                    emitted_something = True
                    yield chunk
                return
            except Exception as exc:  # noqa: BLE001 - fallback intencional
                logger.warning("modelo %s falhou no streaming: %s", model, exc)
                errors.append(f"{model}: {exc}")
                if emitted_something:
                    raise
                continue
        raise AllModelsFailedError(f"Todos os modelos da cadeia falharam: {'; '.join(errors)}")

    async def _stream_model(
        self,
        model: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None,
    ) -> AsyncIterator[LLMStreamChunk]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [_message_to_dict(m) for m in messages],
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        total_content = ""
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
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload_line = line[len("data:") :].strip()
                if payload_line == "[DONE]":
                    break
                try:
                    event = json.loads(payload_line)
                except json.JSONDecodeError:
                    continue
                choice = (event.get("choices") or [{}])[0]
                delta = choice.get("delta", {})
                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]

                text = delta.get("content")
                if text:
                    total_content += text
                    yield LLMStreamChunk(delta=text)

                for tc_delta in delta.get("tool_calls") or []:
                    index = tc_delta.get("index", 0)
                    accumulated = tool_calls_acc.setdefault(index, {"id": "", "name": "", "arguments": ""})
                    if tc_delta.get("id"):
                        accumulated["id"] = tc_delta["id"]
                    function = tc_delta.get("function") or {}
                    if function.get("name"):
                        accumulated["name"] = function["name"]
                    if function.get("arguments"):
                        accumulated["arguments"] += function["arguments"]

        tool_calls = []
        for index in sorted(tool_calls_acc):
            accumulated = tool_calls_acc[index]
            try:
                args = json.loads(accumulated["arguments"]) if accumulated["arguments"] else {}
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(id=accumulated["id"] or f"call_{index}", name=accumulated["name"], arguments=args)
            )

        final_response = LLMResponse(
            content=total_content or None,
            tool_calls=tool_calls,
            model_used=model,
            finish_reason=finish_reason,
        )
        yield LLMStreamChunk(final_response=final_response)

    async def _try_model(
        self,
        model: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": model,
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

        choice = data["choices"][0]
        msg = choice["message"]
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
            model_used=data.get("model", model),
            finish_reason=choice.get("finish_reason", "stop"),
        )
