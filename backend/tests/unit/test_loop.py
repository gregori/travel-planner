import pytest

from app.agent.loop import conta_perguntas, estimar_tokens, processar_mensagem
from app.agent.tools import AgentContext
from app.config import Settings
from app.llm.fake import FakeLLM, resposta_texto
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore


def test_conta_perguntas():
    assert conta_perguntas("Para onde? Quantas pessoas?") == 2
    assert conta_perguntas("Não há perguntas aqui.") == 0
    assert conta_perguntas("Uma? Duas? Três?") == 3


def test_estimar_tokens_nunca_zero():
    assert estimar_tokens("") == 1
    assert estimar_tokens("a" * 40) == 10


@pytest.mark.asyncio
async def test_resposta_de_texto_chega_em_multiplos_eventos_token(
    settings: Settings, registry: ProviderRegistry
):
    """RF-06: a resposta deve ser emitida em pedaços conforme chega, não
    como um único evento com o texto inteiro."""
    store = SessionStore(ttl_minutos=60)
    estado = store.criar()
    ctx = AgentContext(sessao=estado, registry=registry, settings=settings)
    llm = FakeLLM(script=[resposta_texto("Olá! Para onde você quer viajar?")])

    eventos = [e async for e in processar_mensagem(ctx, llm, "oi")]
    eventos_token = [e for e in eventos if e["evento"] == "token"]

    assert len(eventos_token) > 1  # várias palavras, não um único bloco
    assert "".join(e["dados"] for e in eventos_token) == "Olá! Para onde você quer viajar?"


@pytest.mark.asyncio
async def test_teto_de_tokens_encerra_graciosamente(settings: Settings, registry: ProviderRegistry):
    settings_teto_baixo = settings.model_copy(update={"max_tokens_per_session": 1})
    store = SessionStore(ttl_minutos=60)
    estado = store.criar()
    ctx = AgentContext(sessao=estado, registry=registry, settings=settings_teto_baixo)
    llm = FakeLLM(script=[resposta_texto("não deveria ser usada")])

    eventos = [
        e async for e in processar_mensagem(ctx, llm, "mensagem razoavelmente longa para estourar o teto")
    ]

    tipos = [e["evento"] for e in eventos]
    assert "error" not in tipos
    assert "done" in tipos
    textos = [e["dados"] for e in eventos if e["evento"] == "token"]
    assert any("limite" in t.lower() for t in textos)
