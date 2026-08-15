from decimal import Decimal

import pytest

from app.agent.loop import processar_mensagem
from app.agent.tools import AgentContext
from app.config import Settings
from app.llm.base import LLMResponse, ToolCall
from app.llm.fake import FakeLLM
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore

BRIEF_CEN3 = {
    "origem": "São Paulo",
    "destino": "Florianópolis",
    "mes_referencia": "janeiro",
    "duracao_dias": 5,
    "adultos": 1,
    "orcamento_total": 1800,
    "moeda_exibicao": "BRL",
    "tipo_viagem": "descanso",
}


@pytest.mark.asyncio
async def test_cen3_nacional_economico(settings: Settings, registry: ProviderRegistry):
    store = SessionStore(ttl_minutos=60)
    estado = store.criar()
    ctx = AgentContext(sessao=estado, registry=registry, settings=settings)

    llm = FakeLLM(
        script=[
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="c1", name="atualizar_briefing", arguments=BRIEF_CEN3)],
                finish_reason="tool_calls",
            ),
            LLMResponse(content="Vou montar uma viagem econômica de 5 dias para Florianópolis."),
        ]
    )

    eventos = [e async for e in processar_mensagem(ctx, llm, "Quero uma viagem barata para Floripa")]
    assert "plan_ready" in [e["evento"] for e in eventos]

    plano = estado.plan
    assert plano is not None

    # CEN-3 — critérios de aceite
    assert plano.cambio is None  # viagem doméstica: câmbio ausente/não aplicável

    assert plano.orcamento.dentro_do_teto is False
    assert plano.orcamento.alertas, "Orçamento apertado deve gerar alerta explícito (RF-26)"
    alerta = plano.orcamento.alertas[0]
    assert "estourado" in alerta or "tolerância" in alerta

    subtotal_sem_contingencia = plano.orcamento.total - plano.orcamento.contingencia
    assert plano.orcamento.contingencia >= subtotal_sem_contingencia * Decimal("0.0999")
