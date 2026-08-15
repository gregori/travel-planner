from datetime import UTC, datetime
from decimal import Decimal

from app.agent.budget import calculate_budget
from app.models.common import Source

HEURISTIC_SOURCE = [
    Source(
        type="estimate",
        provider="heuristica",
        url=None,
        retrieved_at=datetime.now(UTC),
        confidence="low",
        note="Estimativa heurística de alimentação/transporte local.",
    )
]


def test_contingencia_minima_10_por_cento():
    budget = calculate_budget(
        flights=Decimal("1000"),
        accommodation=Decimal("1000"),
        food=Decimal("500"),
        activities=Decimal("300"),
        local_transport=Decimal("200"),
        stated_cap=None,
        sources=HEURISTIC_SOURCE,
    )
    subtotal = Decimal("3000")
    assert budget.contingency == (subtotal * Decimal("0.10"))
    assert budget.total == subtotal + budget.contingency


def test_alimentacao_ou_transporte_sem_fonte_falha_validacao():
    import pytest

    with pytest.raises(Exception, match="Source"):
        calculate_budget(
            flights=Decimal("1000"),
            accommodation=Decimal("1000"),
            food=Decimal("500"),
            activities=Decimal("300"),
            local_transport=Decimal("200"),
            stated_cap=None,
            sources=[],
        )


def test_dentro_do_teto_sem_alertas():
    budget = calculate_budget(
        flights=Decimal("1000"),
        accommodation=Decimal("1000"),
        food=Decimal("500"),
        activities=Decimal("300"),
        local_transport=Decimal("200"),
        stated_cap=Decimal("5000"),
        sources=HEURISTIC_SOURCE,
    )
    assert budget.within_cap is True
    assert budget.alerts == []


def test_estouro_dentro_da_tolerancia_sinaliza_sem_alerta_forte():
    # total = 3000 + 10% contingencia = 3300; teto = 3200 -> estouro de 100 (3.1%), dentro de 10%
    budget = calculate_budget(
        flights=Decimal("1000"),
        accommodation=Decimal("1000"),
        food=Decimal("500"),
        activities=Decimal("300"),
        local_transport=Decimal("200"),
        stated_cap=Decimal("3200"),
        tolerance=0.10,
        sources=HEURISTIC_SOURCE,
    )
    assert budget.within_cap is False
    assert len(budget.alerts) == 1
    assert "dentro da tolerância" in budget.alerts[0]


def test_estouro_acima_da_tolerancia_gera_alerta_explicito_com_top3():
    # total = 3300; teto = 2000 -> estouro de 1300 (65%), muito acima de 10%
    budget = calculate_budget(
        flights=Decimal("1000"),
        accommodation=Decimal("1000"),
        food=Decimal("500"),
        activities=Decimal("300"),
        local_transport=Decimal("200"),
        stated_cap=Decimal("2000"),
        tolerance=0.10,
        sources=HEURISTIC_SOURCE,
    )
    assert budget.within_cap is False
    assert len(budget.alerts) == 1
    alert = budget.alerts[0]
    assert "Orçamento estourado" in alert
    assert "voos" in alert and "hospedagem" in alert
    assert "Sugest" in alert


def test_top3_ignora_categorias_zeradas():
    # apenas voos e hospedagem têm custo; passeios/transporte ficam de fora do top3
    budget = calculate_budget(
        flights=Decimal("1000"),
        accommodation=Decimal("1000"),
        food=Decimal("0"),
        activities=Decimal("0"),
        local_transport=Decimal("0"),
        stated_cap=Decimal("500"),
        tolerance=0.10,
        sources=[],
    )
    alert = budget.alerts[0]
    assert "passeios" not in alert
    assert "transporte local" not in alert
