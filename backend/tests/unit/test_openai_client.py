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
