from datetime import date
from decimal import Decimal

from app.models.brief import TripBrief


def test_brief_vazio_lista_todos_campos_faltantes():
    brief = TripBrief()
    missing = brief.missing_fields()
    assert "destino" in missing
    assert "datas (ou mês + duração)" in missing
    assert "orçamento" in missing
    assert not brief.ready_to_plan()


def test_brief_completo_com_datas_exatas():
    brief = TripBrief(
        destination="Lisboa",
        origin="São Paulo",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 8),
        adults=2,
        total_budget=Decimal("25000"),
    )
    assert brief.ready_to_plan()
    assert brief.estimated_duration() == 8


def test_brief_completo_com_mes_e_duracao():
    brief = TripBrief(
        destination="Florianópolis",
        reference_month="dezembro",
        duration_days=5,
        adults=2,
        total_budget=Decimal("4000"),
    )
    assert brief.ready_to_plan()
    assert brief.estimated_duration() == 5


def test_merge_preserva_campos_ja_definidos():
    brief = TripBrief(destination="Paris", adults=2)
    updated = brief.merge(total_budget=Decimal("8000"))
    assert updated.destination == "Paris"
    assert updated.adults == 2
    assert updated.total_budget == Decimal("8000")


def test_total_viajantes_soma_adultos_e_criancas():
    brief = TripBrief(adults=2, children_ages=[6])
    assert brief.total_travelers == 3
    assert brief.has_children is True


def test_numero_de_viajantes_falta_quando_adultos_nao_informado():
    """RF-02: sem adultos explícito, o agente deve perguntar — não assumir 1."""
    brief = TripBrief(
        destination="Lisboa",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 8),
        total_budget=Decimal("25000"),
    )
    assert "número de viajantes" in brief.missing_fields()
    assert not brief.ready_to_plan()
    assert brief.total_travelers == 0


def test_rf04_alterar_duracao_recalcula_apos_datas_exatas():
    """RF-04: 'na verdade são 5 dias' deve substituir a duração antiga
    calculada a partir de datas exatas, não ser ignorado."""
    brief = TripBrief(
        destination="Lisboa",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 8),
        adults=2,
        total_budget=Decimal("25000"),
    )
    assert brief.estimated_duration() == 8

    updated = brief.merge(duration_days=5)
    assert updated.estimated_duration() == 5
    assert updated.end_date == date(2026, 10, 5)


def test_rf04_datas_novas_no_mesmo_turno_tem_prioridade():
    brief = TripBrief(destination="Lisboa", start_date=date(2026, 10, 1), end_date=date(2026, 10, 8))
    updated = brief.merge(start_date=date(2026, 11, 1), end_date=date(2026, 11, 10))
    assert updated.estimated_duration() == 10


def test_inferencia_de_ritmo_leve_com_criancas():
    """RF-05: ritmo leve é inferido (e declarado) quando há crianças e o
    usuário não escolheu um ritmo explicitamente."""
    brief = TripBrief(destination="Lisboa", children_ages=[6])
    inferred = brief.with_default_inferences()
    assert inferred.pace == "light"
    assert "pace" in inferred.inferred_fields


def test_inferencia_de_ritmo_nao_sobrescreve_escolha_explicita():
    brief = TripBrief(destination="Lisboa", children_ages=[6], pace="intense")
    inferred = brief.with_default_inferences()
    assert inferred.pace == "intense"
    assert "pace" not in inferred.inferred_fields
