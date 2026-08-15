import httpx
import pytest
import respx

from app.llm.base import LLMMessage, LLMTodosModelosFalharamError
from app.llm.openai_client import OpenAICompatibleLLM


@pytest.mark.asyncio
@respx.mock
async def test_completa_com_sucesso_no_modelo_primario():
    respx.post("http://llm.invalid/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "modelo-primario",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "olá"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )
    )
    cliente = OpenAICompatibleLLM(base_url="http://llm.invalid", api_key="x", model_chain=["modelo-primario"])
    resposta = await cliente.complete([LLMMessage(role="user", content="oi")])
    assert resposta.content == "olá"
    assert resposta.modelo_usado == "modelo-primario"


@pytest.mark.asyncio
@respx.mock
async def test_faz_fallback_para_modelo_secundario_quando_primario_falha():
    rota = respx.post("http://llm.invalid/chat/completions")
    rota.side_effect = [
        httpx.Response(500, json={"erro": "indisponivel"}),
        httpx.Response(
            200,
            json={
                "model": "modelo-secundario",
                "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
            },
        ),
    ]
    cliente = OpenAICompatibleLLM(
        base_url="http://llm.invalid",
        api_key="x",
        model_chain=["modelo-primario", "modelo-secundario"],
    )
    resposta = await cliente.complete([LLMMessage(role="user", content="oi")])
    assert resposta.modelo_usado == "modelo-secundario"


@pytest.mark.asyncio
@respx.mock
async def test_levanta_erro_quando_todos_os_modelos_falham():
    respx.post("http://llm.invalid/chat/completions").mock(
        return_value=httpx.Response(500, json={"erro": "indisponivel"})
    )
    cliente = OpenAICompatibleLLM(base_url="http://llm.invalid", api_key="x", model_chain=["m1", "m2"])
    with pytest.raises(LLMTodosModelosFalharamError):
        await cliente.complete([LLMMessage(role="user", content="oi")])


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
                                        "name": "atualizar_briefing",
                                        "arguments": '{"destino": "Lisboa"}',
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
    cliente = OpenAICompatibleLLM(base_url="http://llm.invalid", api_key="x", model_chain=["m1"])
    resposta = await cliente.complete([LLMMessage(role="user", content="oi")], tools=[{"type": "function"}])
    assert len(resposta.tool_calls) == 1
    assert resposta.tool_calls[0].name == "atualizar_briefing"
    assert resposta.tool_calls[0].arguments == {"destino": "Lisboa"}


def _sse(*eventos: str) -> bytes:
    corpo = "".join(f"data: {e}\n\n" for e in eventos)
    return (corpo + "data: [DONE]\n\n").encode()


@pytest.mark.asyncio
@respx.mock
async def test_stream_emite_deltas_de_texto_incrementais():
    corpo = _sse(
        '{"choices":[{"delta":{"content":"Ol"},"finish_reason":null}]}',
        '{"choices":[{"delta":{"content":"á!"},"finish_reason":null}]}',
        '{"choices":[{"delta":{},"finish_reason":"stop"}]}',
    )
    respx.post("http://llm.invalid/chat/completions").mock(
        return_value=httpx.Response(200, content=corpo, headers={"content-type": "text/event-stream"})
    )
    cliente = OpenAICompatibleLLM(base_url="http://llm.invalid", api_key="x", model_chain=["m1"])

    chunks = [c async for c in cliente.stream([LLMMessage(role="user", content="oi")])]

    deltas = [c.delta for c in chunks if c.delta]
    assert deltas == ["Ol", "á!"]
    finais = [c.resposta_final for c in chunks if c.resposta_final]
    assert len(finais) == 1
    assert finais[0].content == "Olá!"
    assert finais[0].modelo_usado == "m1"


@pytest.mark.asyncio
@respx.mock
async def test_stream_acumula_tool_calls_fragmentadas():
    corpo = _sse(
        '{"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function",'
        '"function":{"name":"atualizar_briefing","arguments":""}}]},"finish_reason":null}]}',
        '{"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"destino\\":"}}]},'
        '"finish_reason":null}]}',
        '{"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":" \\"Lisboa\\"}"}}]},'
        '"finish_reason":null}]}',
        '{"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
    )
    respx.post("http://llm.invalid/chat/completions").mock(
        return_value=httpx.Response(200, content=corpo, headers={"content-type": "text/event-stream"})
    )
    cliente = OpenAICompatibleLLM(base_url="http://llm.invalid", api_key="x", model_chain=["m1"])

    chunks = [
        c async for c in cliente.stream([LLMMessage(role="user", content="oi")], tools=[{"type": "function"}])
    ]

    resposta_final = next(c.resposta_final for c in chunks if c.resposta_final)
    assert resposta_final.tool_calls[0].name == "atualizar_briefing"
    assert resposta_final.tool_calls[0].arguments == {"destino": "Lisboa"}
    assert resposta_final.finish_reason == "tool_calls"


@pytest.mark.asyncio
@respx.mock
async def test_stream_faz_fallback_quando_primario_falha_antes_de_emitir():
    rota = respx.post("http://llm.invalid/chat/completions")
    rota.side_effect = [
        httpx.Response(500, json={"erro": "indisponivel"}),
        httpx.Response(
            200,
            content=_sse('{"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}'),
            headers={"content-type": "text/event-stream"},
        ),
    ]
    cliente = OpenAICompatibleLLM(
        base_url="http://llm.invalid", api_key="x", model_chain=["modelo-primario", "modelo-secundario"]
    )

    chunks = [c async for c in cliente.stream([LLMMessage(role="user", content="oi")])]

    finais = [c.resposta_final for c in chunks if c.resposta_final]
    assert finais[0].modelo_usado == "modelo-secundario"
