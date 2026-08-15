from datetime import date
from decimal import Decimal

import pytest

from app.agent.planner import gerar_plano
from app.agent.tools import AgentContext
from app.models.brief import TripBrief
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore


@pytest.mark.asyncio
async def test_gerar_plano_cenario_familia_lisboa(settings, registry: ProviderRegistry):
    store = SessionStore(ttl_minutos=60)
    estado = store.criar()
    estado.brief = TripBrief(
        origem="São Paulo",
        destino="Lisboa",
        data_ida=date(2026, 10, 1),
        data_volta=date(2026, 10, 7),
        adultos=2,
        criancas_idades=[6],
        orcamento_total=Decimal("25000"),
        moeda_exibicao="BRL",
        tipo_viagem="familia",
        restricoes_alimentares=["sem glúten"],
        nacionalidade="brasileira",
    )
    ctx = AgentContext(sessao=estado, registry=registry, settings=settings)

    plano = await gerar_plano(ctx)

    assert len(plano.itinerario) == 7
    for dia in plano.itinerario:
        total_principais = sum(
            1
            for bloco in (dia.manha, dia.tarde, dia.noite)
            for a in bloco
            if a.titulo not in ("Chegada e check-in", "Checkout e deslocamento ao aeroporto")
            and not a.titulo.startswith("Jantar")
            and a.titulo != "Tempo livre / descanso"
        )
        assert total_principais <= 2

    assert len(plano.opcoes_hospedagem) >= 3
    assert len(plano.opcoes_voo) >= 2
    assert plano.cambio is not None
    assert plano.cambio.moeda_origem == "EUR"
    subtotal_sem_contingencia = plano.orcamento.total - plano.orcamento.contingencia
    assert plano.orcamento.contingencia >= subtotal_sem_contingencia * Decimal("0.10") - Decimal("0.01")
    assert plano.checklist.requisitos_entrada  # RF-28
    for refeicao in plano.refeicoes:
        assert "glúten" in refeicao.compatibilidade.lower() or "Atende" in refeicao.compatibilidade


@pytest.mark.asyncio
async def test_gerar_plano_domestico_sem_cambio(settings, registry: ProviderRegistry):
    store = SessionStore(ttl_minutos=60)
    estado = store.criar()
    estado.brief = TripBrief(
        origem="São Paulo",
        destino="Florianópolis",
        mes_referencia="janeiro",
        duracao_dias=5,
        adultos=1,
        orcamento_total=Decimal("2000"),
        tipo_viagem="descanso",
    )
    ctx = AgentContext(sessao=estado, registry=registry, settings=settings)

    plano = await gerar_plano(ctx)

    assert plano.cambio is None
    assert not plano.checklist.requisitos_entrada
    assert plano.orcamento.alertas  # orçamento apertado deve estourar e gerar alerta (RF-26)
