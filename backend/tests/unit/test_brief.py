from datetime import date
from decimal import Decimal

from app.models.brief import TripBrief


def test_brief_vazio_lista_todos_campos_faltantes():
    brief = TripBrief()
    faltantes = brief.campos_faltantes()
    assert "destino" in faltantes
    assert "datas (ou mês + duração)" in faltantes
    assert "orçamento" in faltantes
    assert not brief.pronto_para_planejar()


def test_brief_completo_com_datas_exatas():
    brief = TripBrief(
        destino="Lisboa",
        origem="São Paulo",
        data_ida=date(2026, 10, 1),
        data_volta=date(2026, 10, 8),
        adultos=2,
        orcamento_total=Decimal("25000"),
    )
    assert brief.pronto_para_planejar()
    assert brief.duracao_estimada() == 8


def test_brief_completo_com_mes_e_duracao():
    brief = TripBrief(
        destino="Florianópolis",
        mes_referencia="dezembro",
        duracao_dias=5,
        adultos=2,
        orcamento_total=Decimal("4000"),
    )
    assert brief.pronto_para_planejar()
    assert brief.duracao_estimada() == 5


def test_merge_preserva_campos_ja_definidos():
    brief = TripBrief(destino="Paris", adultos=2)
    atualizado = brief.merge(orcamento_total=Decimal("8000"))
    assert atualizado.destino == "Paris"
    assert atualizado.adultos == 2
    assert atualizado.orcamento_total == Decimal("8000")


def test_total_viajantes_soma_adultos_e_criancas():
    brief = TripBrief(adultos=2, criancas_idades=[6])
    assert brief.total_viajantes == 3
    assert brief.tem_criancas is True
