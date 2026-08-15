import pytest

from app.agent.loop import processar_mensagem
from app.agent.tools import AgentContext
from app.config import Settings
from app.llm.base import LLMResponse, ToolCall
from app.llm.fake import FakeLLM
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore

BRIEF_CEN2 = {
    "origem": "São Paulo",
    "destino": "Paris",
    "mes_referencia": "fevereiro",
    "duracao_dias": 3,
    "adultos": 2,
    "orcamento_total": 12000,
    "moeda_exibicao": "BRL",
    "tipo_viagem": "romantica",
    "interesses": ["gastronomia", "romantica"],
    "ritmo": "leve",
}


@pytest.mark.asyncio
async def test_cen2_casal_fim_de_semana_romantico(settings: Settings, registry: ProviderRegistry):
    store = SessionStore(ttl_minutos=60)
    estado = store.criar()
    ctx = AgentContext(sessao=estado, registry=registry, settings=settings)

    llm = FakeLLM(
        script=[
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="c1", name="atualizar_briefing", arguments=BRIEF_CEN2)],
                finish_reason="tool_calls",
            ),
            LLMResponse(
                content="Ótimo! Vou montar um fim de semana romântico em Paris com foco gastronômico."
            ),
        ]
    )

    eventos = [e async for e in processar_mensagem(ctx, llm, "Quero um fim de semana romântico em Paris")]
    assert "plan_ready" in [e["evento"] for e in eventos]

    plano = estado.plan
    assert plano is not None

    # CEN-2 — critérios de aceite
    assert len(plano.itinerario) == 3

    dia_chegada = plano.itinerario[0]
    assert dia_chegada.manha[0].titulo == "Chegada e check-in"
    dia_partida = plano.itinerario[-1]
    assert any(a.titulo == "Checkout e deslocamento ao aeroporto" for a in dia_partida.tarde)
    assert dia_partida.noite == []  # sem atividade à noite no dia de partida (RF-23)

    for dia in plano.itinerario:
        regioes_do_dia = {a.regiao for bloco in (dia.manha, dia.tarde, dia.noite) for a in bloco if a.regiao}
        assert len(regioes_do_dia) <= 1  # agrupamento geográfico (RF-21)

    for item in plano.opcoes_voo + plano.opcoes_hospedagem + plano.refeicoes:
        assert item.fonte is not None  # RNF-01
