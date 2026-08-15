import pytest

from app.llm.base import LLMTodosModelosFalharamError
from app.llm.fake import FakeLLM, resposta_texto


@pytest.mark.asyncio
async def test_fake_llm_retorna_roteiro_em_sequencia():
    llm = FakeLLM(script=[resposta_texto("primeira"), resposta_texto("segunda")])
    r1 = await llm.complete(messages=[])
    r2 = await llm.complete(messages=[])
    assert r1.content == "primeira"
    assert r2.content == "segunda"


@pytest.mark.asyncio
async def test_fallback_de_modelos_registra_qual_respondeu():
    llm = FakeLLM(
        script=[resposta_texto("ok")],
        model_chain=["primario", "secundario"],
        falha_modelos={"primario"},
    )
    resposta = await llm.complete(messages=[])
    assert resposta.modelo_usado == "secundario"
    assert llm.modelos_tentados == ["primario", "secundario"]


@pytest.mark.asyncio
async def test_todos_os_modelos_falhando_levanta_erro():
    llm = FakeLLM(
        script=[resposta_texto("nunca chega")],
        model_chain=["primario", "secundario"],
        falha_modelos={"primario", "secundario"},
    )
    with pytest.raises(LLMTodosModelosFalharamError):
        await llm.complete(messages=[])
