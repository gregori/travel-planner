from datetime import date
from decimal import Decimal

import pytest

from app.agent.planner import generate_plan
from app.agent.tools import AgentContext
from app.export.markdown import build_source_rows, generate_markdown
from app.export.pdf import generate_pdf_bytes
from app.models.brief import TripBrief
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore


@pytest.fixture
async def sample_plan(settings, registry: ProviderRegistry):
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
        dietary_restrictions=["sem glúten"],
        nationality="brasileira",
    )
    ctx = AgentContext(session=state, registry=registry, settings=settings)
    return await generate_plan(ctx)


@pytest.mark.asyncio
async def test_markdown_contem_secoes_obrigatorias(sample_plan):
    content = sample_plan
    md = generate_markdown(content)
    assert "# Roteiro de viagem" in md
    assert "## Fontes e confiabilidade" in md
    assert "## Orçamento detalhado" in md
    assert "## Itinerário dia a dia" in md
    assert "não realiza reservas" in md
    assert "estimativas sujeitas a variação" in md


@pytest.mark.asyncio
async def test_pdf_gerado_com_cabecalho_valido(sample_plan):
    content = sample_plan
    pdf_bytes = generate_pdf_bytes(content)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 1000


@pytest.mark.asyncio
async def test_fontes_e_confiabilidade_liga_item_a_preco(sample_plan):
    """RF-32: cada linha da tabela de fontes deve dizer a que item/preço se
    refere — não pode haver duas linhas genéricas indistinguíveis para
    categorias diferentes (regressão: rótulo de alimentação/transporte)."""
    rows = build_source_rows(sample_plan)
    items = [item for item, _value, _source in rows]

    assert any("Alimentação" in item for item in items)
    assert any("Transporte local" in item for item in items)
    assert not any(item == "Estimativa heurística de orçamento" for item in items)
    assert any(item.startswith("Voo ") for item in items)
    assert any(item.startswith("Hospedagem:") for item in items)
    # cada linha deve ser identificável — nenhum item duplicado no rótulo
    assert len(items) == len(set(items))
