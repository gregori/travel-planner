import pytest

from app.agent.tools import (
    tool_calculate_budget,
    tool_estimate_flights,
    tool_get_exchange_rate,
    tool_practical_info,
    tool_search_accommodation,
    tool_search_attractions,
    tool_search_restaurants,
    tool_update_brief,
)


@pytest.mark.asyncio
async def test_tool_update_brief_atualiza_e_reporta_faltantes(agent_ctx):
    result = await tool_update_brief(agent_ctx, destination="Lisboa", adults=2)
    assert result["brief"]["destination"] == "Lisboa"
    assert any("orçamento" in field for field in result["missing_fields"])
    assert result["ready_to_plan"] is False


@pytest.mark.asyncio
async def test_tool_search_accommodation_retorna_opcoes(agent_ctx):
    result = await tool_search_accommodation(agent_ctx, city="Lisboa", guests=2)
    assert len(result["options"]) >= 3
    assert result["empty_reason"] is None


@pytest.mark.asyncio
async def test_tool_search_attractions_retorna_lista(agent_ctx):
    result = await tool_search_attractions(agent_ctx, city="Lisboa", interests=["cultural"])
    assert len(result["attractions"]) > 0


@pytest.mark.asyncio
async def test_tool_search_restaurants_com_restricao(agent_ctx):
    result = await tool_search_restaurants(agent_ctx, city="Lisboa", restrictions=["sem glúten"])
    assert len(result["restaurants"]) > 0


@pytest.mark.asyncio
async def test_tool_estimate_flights_retorna_faixa(agent_ctx):
    result = await tool_estimate_flights(agent_ctx, origin="São Paulo", destination="Lisboa", passengers=2)
    assert len(result["options"]) >= 2


@pytest.mark.asyncio
async def test_tool_get_exchange_rate_par_conhecido(agent_ctx):
    result = await tool_get_exchange_rate(agent_ctx, source_currency="EUR", target_currency="BRL")
    assert result["rate"] is not None
    assert result["rate"]["rate"]


@pytest.mark.asyncio
async def test_tool_get_exchange_rate_par_desconhecido(agent_ctx):
    result = await tool_get_exchange_rate(agent_ctx, source_currency="XXX", target_currency="YYY")
    assert result["rate"] is None
    assert result["empty_reason"] is not None


@pytest.mark.asyncio
async def test_tool_practical_info_internacional_inclui_requisitos(agent_ctx):
    result = await tool_practical_info(agent_ctx, destination="Lisboa", nationality="brasileira")
    assert result["checklist"]["entry_requirements"]
    assert "Passaporte válido" in result["checklist"]["documents"]


@pytest.mark.asyncio
async def test_tool_practical_info_domestico_sem_requisitos(agent_ctx):
    result = await tool_practical_info(agent_ctx, destination="Florianópolis")
    assert result["checklist"]["entry_requirements"] == []
    assert "Passaporte válido" not in result["checklist"]["documents"]


@pytest.mark.asyncio
async def test_tool_calculate_budget_usa_teto_do_briefing(agent_ctx):
    from decimal import Decimal

    agent_ctx.session.brief = agent_ctx.session.brief.merge(total_budget=Decimal("1000"))
    result = await tool_calculate_budget(agent_ctx, flights=500, accommodation=500)
    assert result["budget"]["stated_cap"] == "1000"


@pytest.mark.asyncio
async def test_cache_evita_segunda_chamada_externa(agent_ctx, monkeypatch):
    calls = {"n": 0}
    original = agent_ctx.registry.search_accommodation

    async def counting(criteria, warnings):
        calls["n"] += 1
        return await original(criteria, warnings)

    monkeypatch.setattr(agent_ctx.registry, "search_accommodation", counting)

    await tool_search_accommodation(agent_ctx, city="Lisboa", guests=2)
    await tool_search_accommodation(agent_ctx, city="Lisboa", guests=2)

    assert calls["n"] == 1  # RF-17: buscas idênticas no mesmo turno reaproveitam o cache
