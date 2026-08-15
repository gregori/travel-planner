from datetime import date
from decimal import Decimal

import pytest

from app.agent.planner import gerar_plano
from app.agent.tools import AgentContext
from app.export.markdown import gerar_markdown, montar_linhas_fontes
from app.export.pdf import gerar_pdf_bytes
from app.models.brief import TripBrief
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore


@pytest.fixture
async def plano_exemplo(settings, registry: ProviderRegistry):
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
        restricoes_alimentares=["sem glúten"],
        nacionalidade="brasileira",
    )
    ctx = AgentContext(sessao=estado, registry=registry, settings=settings)
    return await gerar_plano(ctx)


@pytest.mark.asyncio
async def test_markdown_contem_secoes_obrigatorias(plano_exemplo):
    conteudo = plano_exemplo
    md = gerar_markdown(conteudo)
    assert "# Roteiro de viagem" in md
    assert "## Fontes e confiabilidade" in md
    assert "## Orçamento detalhado" in md
    assert "## Itinerário dia a dia" in md
    assert "não realiza reservas" in md
    assert "estimativas sujeitas a variação" in md


@pytest.mark.asyncio
async def test_pdf_gerado_com_cabecalho_valido(plano_exemplo):
    conteudo = plano_exemplo
    pdf_bytes = gerar_pdf_bytes(conteudo)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 1000


@pytest.mark.asyncio
async def test_fontes_e_confiabilidade_liga_item_a_preco(plano_exemplo):
    """RF-32: cada linha da tabela de fontes deve dizer a que item/preço se
    refere — não pode haver duas linhas genéricas indistinguíveis para
    categorias diferentes (regressão: rótulo de alimentação/transporte)."""
    linhas = montar_linhas_fontes(plano_exemplo)
    itens = [item for item, _valor, _fonte in linhas]

    assert any("Alimentação" in item for item in itens)
    assert any("Transporte local" in item for item in itens)
    assert not any(item == "Estimativa heurística de orçamento" for item in itens)
    assert any(item.startswith("Voo ") for item in itens)
    assert any(item.startswith("Hospedagem:") for item in itens)
    # cada linha deve ser identificável — nenhum item duplicado no rótulo
    assert len(itens) == len(set(itens))
