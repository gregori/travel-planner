import pytest

from app.agent.loop import process_message
from app.agent.tools import AgentContext
from app.config import Settings
from app.export.markdown import generate_markdown
from app.export.pdf import generate_pdf_bytes
from app.llm.base import LLMResponse, ToolCall
from app.llm.fake import FakeLLM
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore

BRIEF_CEN1 = {
    "origin": "São Paulo",
    "destination": "Lisboa",
    "start_date": "2026-10-01",
    "end_date": "2026-10-07",
    "adults": 2,
    "children_ages": [6],
    "total_budget": 25000,
    "budget_currency": "BRL",
    "display_currency": "BRL",
    "trip_type": "family",
    "dietary_restrictions": ["sem glúten"],
    "nationality": "brasileira",
    "pace": "light",
    "inferred_fields": ["pace"],
}


@pytest.mark.asyncio
async def test_cen1_familia_internacional_ponta_a_ponta(settings: Settings, registry: ProviderRegistry):
    store = SessionStore(ttl_minutes=60)
    state = store.create()
    ctx = AgentContext(session=state, registry=registry, settings=settings)

    llm = FakeLLM(
        script=[
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="c1", name="update_brief", arguments=BRIEF_CEN1)],
                finish_reason="tool_calls",
            ),
            LLMResponse(
                content="Perfeito! Com destino, datas, viajantes e orçamento em mãos, já vou montar "
                "seu roteiro para Lisboa com restrição sem glúten.",
            ),
        ]
    )

    events = [e async for e in process_message(ctx, llm, "Quero ir para Lisboa com minha família")]

    types = [e["event"] for e in events]
    assert "brief_update" in types
    assert "plan_ready" in types
    assert "done" in types
    assert "error" not in types

    plan = state.plan
    assert plan is not None

    # CEN-1 — critérios de aceite (REQUIREMENTS.md §11)
    assert len(plan.itinerary) == 7
    for day in plan.itinerary:
        main_activities = [
            a
            for block in (day.morning, day.afternoon, day.evening)
            for a in block
            if a.title
            not in ("Chegada e check-in", "Checkout e deslocamento ao aeroporto", "Tempo livre / descanso")
            and not a.title.startswith("Jantar")
        ]
        assert len(main_activities) <= 2

    for meal in plan.meals:
        assert "gluten" in meal.compatibility.lower().replace("é", "e") or "Atende" in meal.compatibility

    assert plan.exchange_rate is not None
    assert plan.exchange_rate.source_currency == "EUR"
    assert plan.exchange_rate.target_currency == "BRL"
    assert plan.exchange_rate.source.retrieved_at is not None

    assert plan.checklist.entry_requirements, "CEN-1 deve mencionar documentação de entrada (RF-28)"

    assert len(plan.flight_options) >= 2
    assert len(plan.accommodation_options) >= 3
    assert any(v.recommended for v in plan.flight_options)
    assert any(h.recommended for h in plan.accommodation_options)

    assert plan.budget.contingency > 0

    for item in plan.flight_options + plan.accommodation_options + plan.meals:
        assert item.source is not None  # RF-15 / regra invariante §7.3

    # RF-30/31/32/33: exportação em Markdown e PDF com seção de fontes e aviso legal.
    markdown = generate_markdown(plan)
    assert "## Fontes e confiabilidade" in markdown
    assert "não realiza reservas" in markdown
    assert "Lisboa" in markdown

    pdf_bytes = generate_pdf_bytes(plan)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 1000
