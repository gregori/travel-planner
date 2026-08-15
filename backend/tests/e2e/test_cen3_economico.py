from decimal import Decimal

import pytest

from app.agent.loop import process_message
from app.agent.tools import AgentContext
from app.config import Settings
from app.llm.base import LLMResponse, ToolCall
from app.llm.fake import FakeLLM
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore

BRIEF_CEN3 = {
    "origin": "São Paulo",
    "destination": "Florianópolis",
    "reference_month": "janeiro",
    "duration_days": 5,
    "adults": 1,
    "total_budget": 1800,
    "display_currency": "BRL",
    "trip_type": "relaxation",
}


@pytest.mark.asyncio
async def test_cen3_nacional_economico(settings: Settings, registry: ProviderRegistry):
    store = SessionStore(ttl_minutes=60)
    state = store.create()
    ctx = AgentContext(session=state, registry=registry, settings=settings)

    llm = FakeLLM(
        script=[
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="c1", name="update_brief", arguments=BRIEF_CEN3)],
                finish_reason="tool_calls",
            ),
            LLMResponse(content="Vou montar uma viagem econômica de 5 dias para Florianópolis."),
        ]
    )

    events = [e async for e in process_message(ctx, llm, "Quero uma viagem barata para Floripa")]
    assert "plan_ready" in [e["event"] for e in events]

    plan = state.plan
    assert plan is not None

    # CEN-3 — critérios de aceite
    assert plan.exchange_rate is None  # viagem doméstica: câmbio ausente/não aplicável

    assert plan.budget.within_cap is False
    assert plan.budget.alerts, "Orçamento apertado deve gerar alerta explícito (RF-26)"
    alert = plan.budget.alerts[0]
    assert "estourado" in alert or "tolerância" in alert

    subtotal_without_contingency = plan.budget.total - plan.budget.contingency
    assert plan.budget.contingency >= subtotal_without_contingency * Decimal("0.0999")
