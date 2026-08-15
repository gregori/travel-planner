import pytest

from app.llm.base import AllModelsFailedError
from app.llm.fake import FakeLLM, text_response


@pytest.mark.asyncio
async def test_fake_llm_retorna_roteiro_em_sequencia():
    llm = FakeLLM(script=[text_response("primeira"), text_response("segunda")])
    r1 = await llm.complete(messages=[])
    r2 = await llm.complete(messages=[])
    assert r1.content == "primeira"
    assert r2.content == "segunda"


@pytest.mark.asyncio
async def test_fallback_de_modelos_registra_qual_respondeu():
    llm = FakeLLM(
        script=[text_response("ok")],
        model_chain=["primary", "secondary"],
        failing_models={"primary"},
    )
    response = await llm.complete(messages=[])
    assert response.model_used == "secondary"
    assert llm.models_tried == ["primary", "secondary"]


@pytest.mark.asyncio
async def test_todos_os_modelos_falhando_levanta_erro():
    llm = FakeLLM(
        script=[text_response("nunca chega")],
        model_chain=["primary", "secondary"],
        failing_models={"primary", "secondary"},
    )
    with pytest.raises(AllModelsFailedError):
        await llm.complete(messages=[])
