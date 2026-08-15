from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.common import Source
from app.models.plan import Activity, Budget

SOURCE = Source(
    type="mock",
    provider="fixture",
    url=None,
    retrieved_at=datetime.now(UTC),
    confidence="low",
    note=None,
)


def test_atividade_com_custo_exige_fonte():
    """RF-15/§7.3: um item com preço sem Source é um plano inválido."""
    with pytest.raises(ValidationError, match="Source"):
        Activity(title="Passeio pago", estimated_cost=Decimal("50"), source=None)


def test_atividade_sem_custo_dispensa_fonte():
    activity = Activity(title="Tempo livre", estimated_cost=Decimal("0"), source=None)
    assert activity.source is None


def test_atividade_com_custo_e_fonte_valida():
    activity = Activity(title="Museu", estimated_cost=Decimal("20"), source=SOURCE)
    assert activity.source is not None


def test_orcamento_com_alimentacao_sem_fonte_falha():
    with pytest.raises(ValidationError, match="Source"):
        Budget(food=Decimal("500"), local_transport=Decimal("0"), sources=[])


def test_orcamento_com_alimentacao_e_fonte_valida():
    budget = Budget(food=Decimal("500"), local_transport=Decimal("100"), sources=[SOURCE])
    assert budget.total > 0


def test_orcamento_sem_categorias_heuristicas_dispensa_fonte():
    budget = Budget(flights=Decimal("1000"), accommodation=Decimal("500"), sources=[])
    assert budget.total == Decimal("1500")
