import pytest

from app.agent.loop import count_questions, estimate_tokens, process_message
from app.agent.tools import AgentContext
from app.config import Settings
from app.llm.fake import FakeLLM, text_response
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore


def test_conta_perguntas():
    assert count_questions("Para onde? Quantas pessoas?") == 2
    assert count_questions("Não há perguntas aqui.") == 0
    assert count_questions("Uma? Duas? Três?") == 3


def test_estimar_tokens_nunca_zero():
    assert estimate_tokens("") == 1
    assert estimate_tokens("a" * 40) == 10


@pytest.mark.asyncio
async def test_resposta_de_texto_chega_em_multiplos_eventos_token(
    settings: Settings, registry: ProviderRegistry
):
    """RF-06: a resposta deve ser emitida em pedaços conforme chega, não
    como um único evento com o texto inteiro."""
    store = SessionStore(ttl_minutes=60)
    state = store.create()
    ctx = AgentContext(session=state, registry=registry, settings=settings)
    llm = FakeLLM(script=[text_response("Olá! Para onde você quer viajar?")])

    events = [e async for e in process_message(ctx, llm, "oi")]
    token_events = [e for e in events if e["event"] == "token"]

    assert len(token_events) > 1  # várias palavras, não um único bloco
    assert "".join(e["data"] for e in token_events) == "Olá! Para onde você quer viajar?"


@pytest.mark.asyncio
async def test_teto_de_tokens_encerra_graciosamente(settings: Settings, registry: ProviderRegistry):
    low_token_limit_settings = settings.model_copy(update={"max_tokens_per_session": 1})
    store = SessionStore(ttl_minutes=60)
    state = store.create()
    ctx = AgentContext(session=state, registry=registry, settings=low_token_limit_settings)
    llm = FakeLLM(script=[text_response("não deveria ser usada")])

    events = [e async for e in process_message(ctx, llm, "mensagem razoavelmente longa para estourar o teto")]

    types = [e["event"] for e in events]
    assert "error" not in types
    assert "done" in types
    texts = [e["data"] for e in events if e["event"] == "token"]
    assert any("limite" in t.lower() for t in texts)
