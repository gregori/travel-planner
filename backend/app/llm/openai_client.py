import logging
from typing import Any

import httpx

from app.llm.base import LLMMessage, LLMResponse, LLMTodosModelosFalharamError, ToolCall

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
    import json

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
            import json

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
