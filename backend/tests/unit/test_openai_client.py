import httpx
import pytest
import respx

from app.llm.base import AllModelsFailedError, LLMMessage
from app.llm.openai_client import OpenAICompatibleLLM


@pytest.mark.asyncio
@respx.mock
async def test_completa_com_sucesso_no_modelo_primario():
    respx.post("http://llm.invalid/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "primary-model",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "olá"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )
    )
    client = OpenAICompatibleLLM(base_url="http://llm.invalid", api_key="x", model_chain=["primary-model"])
    response = await client.complete([LLMMessage(role="user", content="oi")])
    assert response.content == "olá"
    assert response.model_used == "primary-model"


@pytest.mark.asyncio
@respx.mock
async def test_faz_fallback_para_modelo_secundario_quando_primario_falha():
    route = respx.post("http://llm.invalid/chat/completions")
    route.side_effect = [
        httpx.Response(500, json={"error": "unavailable"}),
        httpx.Response(
            200,
            json={
                "model": "secondary-model",
                "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
            },
        ),
    ]
    client = OpenAICompatibleLLM(
        base_url="http://llm.invalid",
        api_key="x",
        model_chain=["primary-model", "secondary-model"],
    )
    response = await client.complete([LLMMessage(role="user", content="oi")])
    assert response.model_used == "secondary-model"


@pytest.mark.asyncio
@respx.mock
async def test_levanta_erro_quando_todos_os_modelos_falham():
    respx.post("http://llm.invalid/chat/completions").mock(
        return_value=httpx.Response(500, json={"error": "unavailable"})
    )
    client = OpenAICompatibleLLM(base_url="http://llm.invalid", api_key="x", model_chain=["m1", "m2"])
    with pytest.raises(AllModelsFailedError):
        await client.complete([LLMMessage(role="user", content="oi")])


@pytest.mark.asyncio
@respx.mock
async def test_interpreta_tool_calls_da_resposta():
    respx.post("http://llm.invalid/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "m1",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "update_brief",
                                        "arguments": '{"destination": "Lisboa"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
            },
        )
    )
    client = OpenAICompatibleLLM(base_url="http://llm.invalid", api_key="x", model_chain=["m1"])
    response = await client.complete([LLMMessage(role="user", content="oi")], tools=[{"type": "function"}])
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "update_brief"
    assert response.tool_calls[0].arguments == {"destination": "Lisboa"}


def _sse(*events: str) -> bytes:
    body = "".join(f"data: {e}\n\n" for e in events)
    return (body + "data: [DONE]\n\n").encode()


@pytest.mark.asyncio
@respx.mock
async def test_stream_emite_deltas_de_texto_incrementais():
    body = _sse(
        '{"choices":[{"delta":{"content":"Ol"},"finish_reason":null}]}',
        '{"choices":[{"delta":{"content":"á!"},"finish_reason":null}]}',
        '{"choices":[{"delta":{},"finish_reason":"stop"}]}',
    )
    respx.post("http://llm.invalid/chat/completions").mock(
        return_value=httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})
    )
    client = OpenAICompatibleLLM(base_url="http://llm.invalid", api_key="x", model_chain=["m1"])

    chunks = [c async for c in client.stream([LLMMessage(role="user", content="oi")])]

    deltas = [c.delta for c in chunks if c.delta]
    assert deltas == ["Ol", "á!"]
    finals = [c.final_response for c in chunks if c.final_response]
    assert len(finals) == 1
    assert finals[0].content == "Olá!"
    assert finals[0].model_used == "m1"


@pytest.mark.asyncio
@respx.mock
async def test_stream_acumula_tool_calls_fragmentadas():
    body = _sse(
        '{"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function",'
        '"function":{"name":"update_brief","arguments":""}}]},"finish_reason":null}]}',
        '{"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"destination\\":"}}]},'
        '"finish_reason":null}]}',
        '{"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":" \\"Lisboa\\"}"}}]},'
        '"finish_reason":null}]}',
        '{"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
    )
    respx.post("http://llm.invalid/chat/completions").mock(
        return_value=httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})
    )
    client = OpenAICompatibleLLM(base_url="http://llm.invalid", api_key="x", model_chain=["m1"])

    chunks = [
        c async for c in client.stream([LLMMessage(role="user", content="oi")], tools=[{"type": "function"}])
    ]

    final_response = next(c.final_response for c in chunks if c.final_response)
    assert final_response.tool_calls[0].name == "update_brief"
    assert final_response.tool_calls[0].arguments == {"destination": "Lisboa"}
    assert final_response.finish_reason == "tool_calls"


@pytest.mark.asyncio
@respx.mock
async def test_stream_faz_fallback_quando_primario_falha_antes_de_emitir():
    route = respx.post("http://llm.invalid/chat/completions")
    route.side_effect = [
        httpx.Response(500, json={"error": "unavailable"}),
        httpx.Response(
            200,
            content=_sse('{"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}'),
            headers={"content-type": "text/event-stream"},
        ),
    ]
    client = OpenAICompatibleLLM(
        base_url="http://llm.invalid", api_key="x", model_chain=["primary-model", "secondary-model"]
    )

    chunks = [c async for c in client.stream([LLMMessage(role="user", content="oi")])]

    finals = [c.final_response for c in chunks if c.final_response]
    assert finals[0].model_used == "secondary-model"
