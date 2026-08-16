from datetime import date
from decimal import Decimal

import pytest

from app.agent.planner import generate_plan
from app.agent.tools import AgentContext
from app.models.brief import TripBrief
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore


@pytest.mark.asyncio
async def test_gerar_plano_cenario_familia_lisboa(settings, registry: ProviderRegistry):
    store = SessionStore(ttl_minutes=60)
    state = store.create()
    state.brief = TripBrief(
        origin="São Paulo",
        destination="Lisboa",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 7),
        adults=2,
        children_ages=[6],
        total_budget=Decimal("25000"),
        display_currency="BRL",
        trip_type="family",
        dietary_restrictions=["sem glúten"],
        nationality="brasileira",
    )
    ctx = AgentContext(session=state, registry=registry, settings=settings)

    plan = await generate_plan(ctx)

    assert len(plan.itinerary) == 7
    for day in plan.itinerary:
        total_main = sum(
            1
            for block in (day.morning, day.afternoon, day.evening)
            for a in block
            if a.title not in ("Chegada e check-in", "Checkout e deslocamento ao aeroporto")
            and not a.title.startswith("Jantar")
            and a.title != "Tempo livre / descanso"
        )
        assert total_main <= 2

    assert len(plan.accommodation_options) >= 3
    assert len(plan.flight_options) >= 2
    assert plan.exchange_rate is not None
    assert plan.exchange_rate.source_currency == "EUR"
    subtotal_without_contingency = plan.budget.total - plan.budget.contingency
    assert plan.budget.contingency >= subtotal_without_contingency * Decimal("0.10") - Decimal("0.01")
    assert plan.checklist.entry_requirements  # RF-28
    for meal in plan.meals:
        assert "glúten" in meal.compatibility.lower() or "Atende" in meal.compatibility

    # RF-13: passeios em Lisboa são cotados em EUR nas fixtures; o custo
    # exibido no itinerário e no orçamento deve estar convertido para BRL,
    # não ser o valor cru em euros.
    priced_activities = [
        a for day in plan.itinerary for a in day.morning + day.afternoon + day.evening if a.estimated_cost > 0
    ]
    assert priced_activities, "cenário deveria ter ao menos uma atividade paga"
    for a in priced_activities:
        assert a.currency == "BRL"
    # Torre de Belém custa 6 EUR na fixture; convertido (taxa mock 6.10)
    # deveria estar na casa de dezenas de reais, não continuar "6".
    torre_belem = next((a for a in priced_activities if "Torre de Belém" in a.title), None)
    if torre_belem is not None:
        assert torre_belem.estimated_cost > Decimal("6")

    # RF-15/§7.3: toda atividade com custo tem Source (validado no próprio
    # modelo — aqui confirmamos que o plano realmente carrega Source nas
    # categorias heurísticas do orçamento).
    assert plan.budget.sources
    for a in priced_activities:
        assert a.source is not None


@pytest.mark.asyncio
async def test_gerar_plano_domestico_sem_cambio(settings, registry: ProviderRegistry):
    store = SessionStore(ttl_minutes=60)
    state = store.create()
    state.brief = TripBrief(
        origin="São Paulo",
        destination="Florianópolis",
        reference_month="janeiro",
        duration_days=5,
        adults=1,
        total_budget=Decimal("2000"),
        trip_type="relaxation",
    )
    ctx = AgentContext(session=state, registry=registry, settings=settings)

    plan = await generate_plan(ctx)

    assert plan.exchange_rate is None
    assert not plan.checklist.entry_requirements
    assert plan.budget.alerts  # orçamento apertado deve estourar e gerar alerta (RF-26)


@pytest.mark.asyncio
async def test_gerar_plano_com_mes_de_referencia_busca_hospedagem_real_com_datas_derivadas(
    settings, registry: ProviderRegistry
):
    """Quando só há mês + duração (sem data exata), o provedor real ainda
    deve ser chamado — com um intervalo de datas derivado do mês — em vez de
    cair direto no mock só porque check_in/check_out exatos não existem."""
    from datetime import UTC, datetime

    from app.models.common import Source
    from app.providers.base import AccommodationOption, SearchResult

    received_criteria = {}

    class FakeRealAccommodationProvider:
        async def search(self, criteria):
            received_criteria["check_in"] = criteria.check_in
            received_criteria["check_out"] = criteria.check_out
            return SearchResult(
                items=[
                    AccommodationOption(
                        name="Hotel Real",
                        type="hotel",
                        price_per_night=500,
                        currency="MXN",
                        location="Centro",
                        rating=4.5,
                        link=None,
                        source=Source(
                            type="real",
                            provider="liteapi",
                            url=None,
                            retrieved_at=datetime.now(UTC),
                            confidence="high",
                            note=None,
                        ),
                    )
                ]
            )

    registry._liteapi_real = FakeRealAccommodationProvider()

    store = SessionStore(ttl_minutes=60)
    state = store.create()
    state.brief = TripBrief(
        origin="São Paulo",
        destination="Cidade do México",
        reference_month="janeiro de 2027",
        duration_days=10,
        adults=3,
        children_ages=[15],
        total_budget=Decimal("30000"),
        trip_type="family",
    )
    ctx = AgentContext(session=state, registry=registry, settings=settings)

    plan = await generate_plan(ctx)

    assert received_criteria["check_in"] == date(2027, 1, 1)
    assert received_criteria["check_out"] == date(2027, 1, 11)
    assert any(o.name == "Hotel Real" for o in plan.accommodation_options)
    assert any("datas exatas" in w.lower() for w in plan.warnings)


@pytest.mark.asyncio
async def test_provedor_vazio_sem_motivo_ainda_declara_lacuna(settings, registry: ProviderRegistry):
    """RNF-02: mesmo se um provedor devolver lista vazia sem `empty_reason`
    preenchido, o plano precisa declarar a lacuna — nunca ficar em silêncio
    com custo zero como se não houvesse nada para contar."""
    from app.providers.base import SearchResult

    class EmptyAccommodationProvider:
        async def search(self, criteria):
            return SearchResult(items=[], empty_reason=None)

    registry._accommodation_mock = EmptyAccommodationProvider()

    store = SessionStore(ttl_minutes=60)
    state = store.create()
    state.brief = TripBrief(
        origin="São Paulo",
        destination="Lisboa",
        reference_month="outubro",
        duration_days=3,
        adults=1,
        total_budget=Decimal("5000"),
    )
    ctx = AgentContext(session=state, registry=registry, settings=settings)

    plan = await generate_plan(ctx)

    assert plan.accommodation_options == []
    assert plan.budget.accommodation == Decimal("0")
    assert any("hospedagem" in w.lower() or "Lisboa" in w for w in plan.warnings)
