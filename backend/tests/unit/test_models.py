from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.common import Fonte
from app.models.plan import Atividade, Orcamento

FONTE = Fonte(
    tipo="mock",
    provedor="fixture",
    url=None,
    consultado_em=datetime.now(UTC),
    confianca="baixa",
    observacao=None,
)


def test_atividade_com_custo_exige_fonte():
    """RF-15/§7.3: um item com preço sem Fonte é um plano inválido."""
    with pytest.raises(ValidationError, match="Fonte"):
        Atividade(titulo="Passeio pago", custo_estimado=Decimal("50"), fonte=None)


def test_atividade_sem_custo_dispensa_fonte():
    atividade = Atividade(titulo="Tempo livre", custo_estimado=Decimal("0"), fonte=None)
    assert atividade.fonte is None


def test_atividade_com_custo_e_fonte_valida():
    atividade = Atividade(titulo="Museu", custo_estimado=Decimal("20"), fonte=FONTE)
    assert atividade.fonte is not None


def test_orcamento_com_alimentacao_sem_fonte_falha():
    with pytest.raises(ValidationError, match="Fonte"):
        Orcamento(alimentacao=Decimal("500"), transporte_local=Decimal("0"), fontes=[])


def test_orcamento_com_alimentacao_e_fonte_valida():
    orc = Orcamento(alimentacao=Decimal("500"), transporte_local=Decimal("100"), fontes=[FONTE])
    assert orc.total > 0


def test_orcamento_sem_categorias_heuristicas_dispensa_fonte():
    orc = Orcamento(voos=Decimal("1000"), hospedagem=Decimal("500"), fontes=[])
    assert orc.total == Decimal("1500")
