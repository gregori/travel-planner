import pytest

from app.agent.loop import process_message
from app.agent.tools import AgentContext
from app.config import Settings
from app.llm.base import LLMResponse, ToolCall
from app.llm.fake import FakeLLM
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore

BRIEF_CEN2 = {
    "origin": "São Paulo",
    "destination": "Paris",
    "reference_month": "fevereiro",
    "duration_days": 3,
    "adults": 2,
    "total_budget": 12000,
    "display_currency": "BRL",
    "trip_type": "romantic",
    "interests": ["gastronomia", "romantica"],
    "pace": "light",
}


@pytest.mark.asyncio
async def test_cen2_casal_fim_de_semana_romantico(settings: Settings, registry: ProviderRegistry):
    store = SessionStore(ttl_minutes=60)
    state = store.create()
    ctx = AgentContext(session=state, registry=registry, settings=settings)

    llm = FakeLLM(
        script=[
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="c1", name="update_brief", arguments=BRIEF_CEN2)],
                finish_reason="tool_calls",
            ),
            LLMResponse(
                content="Ótimo! Vou montar um fim de semana romântico em Paris com foco gastronômico."
            ),
        ]
    )

    events = [e async for e in process_message(ctx, llm, "Quero um fim de semana romântico em Paris")]
    assert "plan_ready" in [e["event"] for e in events]

    plan = state.plan
    assert plan is not None

    # CEN-2 — critérios de aceite
    assert len(plan.itinerary) == 3

    arrival_day = plan.itinerary[0]
    assert arrival_day.morning[0].title == "Chegada e check-in"
    departure_day = plan.itinerary[-1]
    assert any(a.title == "Checkout e deslocamento ao aeroporto" for a in departure_day.afternoon)
    assert departure_day.evening == []  # sem atividade à noite no dia de partida (RF-23)

    for day in plan.itinerary:
        day_regions = {
            a.region for block in (day.morning, day.afternoon, day.evening) for a in block if a.region
        }
        assert len(day_regions) <= 1  # agrupamento geográfico (RF-21)

    for item in plan.flight_options + plan.accommodation_options + plan.meals:
        assert item.source is not None  # RNF-01
