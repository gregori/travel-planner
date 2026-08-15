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


def test_numero_de_viajantes_falta_quando_adultos_nao_informado():
    """RF-02: sem adultos explícito, o agente deve perguntar — não assumir 1."""
    brief = TripBrief(
        destino="Lisboa",
        data_ida=date(2026, 10, 1),
        data_volta=date(2026, 10, 8),
        orcamento_total=Decimal("25000"),
    )
    assert "número de viajantes" in brief.campos_faltantes()
    assert not brief.pronto_para_planejar()
    assert brief.total_viajantes == 0


def test_rf04_alterar_duracao_recalcula_apos_datas_exatas():
    """RF-04: 'na verdade são 5 dias' deve substituir a duração antiga
    calculada a partir de datas exatas, não ser ignorado."""
    brief = TripBrief(
        destino="Lisboa",
        data_ida=date(2026, 10, 1),
        data_volta=date(2026, 10, 8),
        adultos=2,
        orcamento_total=Decimal("25000"),
    )
    assert brief.duracao_estimada() == 8

    atualizado = brief.merge(duracao_dias=5)
    assert atualizado.duracao_estimada() == 5
    assert atualizado.data_volta == date(2026, 10, 5)


def test_rf04_datas_novas_no_mesmo_turno_tem_prioridade():
    brief = TripBrief(destino="Lisboa", data_ida=date(2026, 10, 1), data_volta=date(2026, 10, 8))
    atualizado = brief.merge(data_ida=date(2026, 11, 1), data_volta=date(2026, 11, 10))
    assert atualizado.duracao_estimada() == 10


def test_inferencia_de_ritmo_leve_com_criancas():
    """RF-05: ritmo leve é inferido (e declarado) quando há crianças e o
    usuário não escolheu um ritmo explicitamente."""
    brief = TripBrief(destino="Lisboa", criancas_idades=[6])
    inferido = brief.com_inferencias_padrao()
    assert inferido.ritmo == "leve"
    assert "ritmo" in inferido.campos_inferidos


def test_inferencia_de_ritmo_nao_sobrescreve_escolha_explicita():
    brief = TripBrief(destino="Lisboa", criancas_idades=[6], ritmo="intenso")
    inferido = brief.com_inferencias_padrao()
    assert inferido.ritmo == "intenso"
    assert "ritmo" not in inferido.campos_inferidos
