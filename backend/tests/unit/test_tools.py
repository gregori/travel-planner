import pytest

from app.agent.tools import (
    tool_atualizar_briefing,
    tool_buscar_atracoes,
    tool_buscar_hospedagem,
    tool_buscar_restaurantes,
    tool_calcular_orcamento,
    tool_cotar_cambio,
    tool_estimar_voos,
    tool_info_pratica,
)


@pytest.mark.asyncio
async def test_tool_atualizar_briefing_atualiza_e_reporta_faltantes(agent_ctx):
    resultado = await tool_atualizar_briefing(agent_ctx, destino="Lisboa", adultos=2)
    assert resultado["briefing"]["destino"] == "Lisboa"
    assert "orçamento" in resultado["campos_faltantes"]
    assert resultado["pronto_para_planejar"] is False


@pytest.mark.asyncio
async def test_tool_buscar_hospedagem_retorna_opcoes(agent_ctx):
    resultado = await tool_buscar_hospedagem(agent_ctx, cidade="Lisboa", hospedes=2)
    assert len(resultado["opcoes"]) >= 3
    assert resultado["motivo_vazio"] is None


@pytest.mark.asyncio
async def test_tool_buscar_atracoes_retorna_lista(agent_ctx):
    resultado = await tool_buscar_atracoes(agent_ctx, cidade="Lisboa", interesses=["cultural"])
    assert len(resultado["atracoes"]) > 0


@pytest.mark.asyncio
async def test_tool_buscar_restaurantes_com_restricao(agent_ctx):
    resultado = await tool_buscar_restaurantes(agent_ctx, cidade="Lisboa", restricoes=["sem glúten"])
    assert len(resultado["restaurantes"]) > 0


@pytest.mark.asyncio
async def test_tool_estimar_voos_retorna_faixa(agent_ctx):
    resultado = await tool_estimar_voos(agent_ctx, origem="São Paulo", destino="Lisboa", passageiros=2)
    assert len(resultado["opcoes"]) >= 2


@pytest.mark.asyncio
async def test_tool_cotar_cambio_par_conhecido(agent_ctx):
    resultado = await tool_cotar_cambio(agent_ctx, moeda_origem="EUR", moeda_destino="BRL")
    assert resultado["cotacao"] is not None
    assert resultado["cotacao"]["taxa"]


@pytest.mark.asyncio
async def test_tool_cotar_cambio_par_desconhecido(agent_ctx):
    resultado = await tool_cotar_cambio(agent_ctx, moeda_origem="XXX", moeda_destino="YYY")
    assert resultado["cotacao"] is None
    assert resultado["motivo_vazio"] is not None


@pytest.mark.asyncio
async def test_tool_info_pratica_internacional_inclui_requisitos(agent_ctx):
    resultado = await tool_info_pratica(agent_ctx, destino="Lisboa", nacionalidade="brasileira")
    assert resultado["checklist"]["requisitos_entrada"]
    assert "Passaporte válido" in resultado["checklist"]["documentos"]


@pytest.mark.asyncio
async def test_tool_info_pratica_domestico_sem_requisitos(agent_ctx):
    resultado = await tool_info_pratica(agent_ctx, destino="Florianópolis")
    assert resultado["checklist"]["requisitos_entrada"] == []
    assert "Passaporte válido" not in resultado["checklist"]["documentos"]


@pytest.mark.asyncio
async def test_tool_calcular_orcamento_usa_teto_do_briefing(agent_ctx):
    from decimal import Decimal

    agent_ctx.sessao.brief = agent_ctx.sessao.brief.merge(orcamento_total=Decimal("1000"))
    resultado = await tool_calcular_orcamento(agent_ctx, voos=500, hospedagem=500)
    assert resultado["orcamento"]["teto_informado"] == "1000"


@pytest.mark.asyncio
async def test_cache_evita_segunda_chamada_externa(agent_ctx, monkeypatch):
    chamadas = {"n": 0}
    original = agent_ctx.registry.buscar_hospedagem

    async def contando(criterios, avisos):
        chamadas["n"] += 1
        return await original(criterios, avisos)

    monkeypatch.setattr(agent_ctx.registry, "buscar_hospedagem", contando)

    await tool_buscar_hospedagem(agent_ctx, cidade="Lisboa", hospedes=2)
    await tool_buscar_hospedagem(agent_ctx, cidade="Lisboa", hospedes=2)

    assert chamadas["n"] == 1  # RF-17: buscas idênticas no mesmo turno reaproveitam o cache
