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

    # RF-13: passeios em Lisboa são cotados em EUR nas fixtures; o custo
    # exibido no itinerário e no orçamento deve estar convertido para BRL,
    # não ser o valor cru em euros.
    atividades_com_custo = [
        a for dia in plano.itinerario for a in dia.manha + dia.tarde + dia.noite if a.custo_estimado > 0
    ]
    assert atividades_com_custo, "cenário deveria ter ao menos uma atividade paga"
    for a in atividades_com_custo:
        assert a.moeda == "BRL"
    # Torre de Belém custa 6 EUR na fixture; convertido (taxa mock 6.10)
    # deveria estar na casa de dezenas de reais, não continuar "6".
    torre_belem = next((a for a in atividades_com_custo if "Torre de Belém" in a.titulo), None)
    if torre_belem is not None:
        assert torre_belem.custo_estimado > Decimal("6")

    # RF-15/§7.3: toda atividade com custo tem Fonte (validado no próprio
    # modelo — aqui confirmamos que o plano realmente carrega Fonte nas
    # categorias heurísticas do orçamento).
    assert plano.orcamento.fontes
    for a in atividades_com_custo:
        assert a.fonte is not None


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


@pytest.mark.asyncio
async def test_provedor_vazio_sem_motivo_ainda_declara_lacuna(settings, registry: ProviderRegistry):
    """RNF-02: mesmo se um provedor devolver lista vazia sem `motivo_vazio`
    preenchido, o plano precisa declarar a lacuna — nunca ficar em silêncio
    com custo zero como se não houvesse nada para contar."""
    from app.providers.base import ResultadoBusca

    class HospedagemVazia:
        async def buscar(self, criterios):
            return ResultadoBusca(itens=[], motivo_vazio=None)

    registry._hospedagem_mock = HospedagemVazia()

    store = SessionStore(ttl_minutos=60)
    estado = store.criar()
    estado.brief = TripBrief(
        origem="São Paulo",
        destino="Lisboa",
        mes_referencia="outubro",
        duracao_dias=3,
        adultos=1,
        orcamento_total=Decimal("5000"),
    )
    ctx = AgentContext(sessao=estado, registry=registry, settings=settings)

    plano = await gerar_plano(ctx)

    assert plano.opcoes_hospedagem == []
    assert plano.orcamento.hospedagem == Decimal("0")
    assert any("hospedagem" in a.lower() or "Lisboa" in a for a in plano.avisos)
