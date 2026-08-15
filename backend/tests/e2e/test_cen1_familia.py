import pytest

from app.agent.loop import processar_mensagem
from app.agent.tools import AgentContext
from app.config import Settings
from app.llm.base import LLMResponse, ToolCall
from app.llm.fake import FakeLLM
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore

BRIEF_CEN1 = {
    "origem": "São Paulo",
    "destino": "Lisboa",
    "data_ida": "2026-10-01",
    "data_volta": "2026-10-07",
    "adultos": 2,
    "criancas_idades": [6],
    "orcamento_total": 25000,
    "moeda_orcamento": "BRL",
    "moeda_exibicao": "BRL",
    "tipo_viagem": "familia",
    "restricoes_alimentares": ["sem glúten"],
    "nacionalidade": "brasileira",
    "ritmo": "leve",
    "campos_inferidos": ["ritmo"],
}


@pytest.mark.asyncio
async def test_cen1_familia_internacional_ponta_a_ponta(settings: Settings, registry: ProviderRegistry):
    store = SessionStore(ttl_minutos=60)
    estado = store.criar()
    ctx = AgentContext(sessao=estado, registry=registry, settings=settings)

    llm = FakeLLM(
        script=[
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="c1", name="atualizar_briefing", arguments=BRIEF_CEN1)],
                finish_reason="tool_calls",
            ),
            LLMResponse(
                content="Perfeito! Com destino, datas, viajantes e orçamento em mãos, já vou montar "
                "seu roteiro para Lisboa com restrição sem glúten.",
            ),
        ]
    )

    eventos = [e async for e in processar_mensagem(ctx, llm, "Quero ir para Lisboa com minha família")]

    tipos = [e["evento"] for e in eventos]
    assert "brief_update" in tipos
    assert "plan_ready" in tipos
    assert "done" in tipos
    assert "error" not in tipos

    plano = estado.plan
    assert plano is not None

    # CEN-1 — critérios de aceite (REQUIREMENTS.md §11)
    assert len(plano.itinerario) == 7
    for dia in plano.itinerario:
        principais = [
            a
            for bloco in (dia.manha, dia.tarde, dia.noite)
            for a in bloco
            if a.titulo
            not in ("Chegada e check-in", "Checkout e deslocamento ao aeroporto", "Tempo livre / descanso")
            and not a.titulo.startswith("Jantar")
        ]
        assert len(principais) <= 2

    for refeicao in plano.refeicoes:
        assert (
            "gluten" in refeicao.compatibilidade.lower().replace("é", "e")
            or "Atende" in refeicao.compatibilidade
        )

    assert plano.cambio is not None
    assert plano.cambio.moeda_origem == "EUR"
    assert plano.cambio.moeda_destino == "BRL"
    assert plano.cambio.fonte.consultado_em is not None

    assert plano.checklist.requisitos_entrada, "CEN-1 deve mencionar documentação de entrada (RF-28)"

    assert len(plano.opcoes_voo) >= 2
    assert len(plano.opcoes_hospedagem) >= 3
    assert any(v.recomendada for v in plano.opcoes_voo)
    assert any(h.recomendada for h in plano.opcoes_hospedagem)

    assert plano.orcamento.contingencia > 0

    for item in plano.opcoes_voo + plano.opcoes_hospedagem + plano.refeicoes:
        assert item.fonte is not None  # RF-15 / regra invariante §7.3
