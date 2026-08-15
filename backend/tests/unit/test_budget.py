from decimal import Decimal

from app.agent.budget import calcular_orcamento


def test_contingencia_minima_10_por_cento():
    orc = calcular_orcamento(
        voos=Decimal("1000"),
        hospedagem=Decimal("1000"),
        alimentacao=Decimal("500"),
        passeios=Decimal("300"),
        transporte_local=Decimal("200"),
        teto_informado=None,
    )
    subtotal = Decimal("3000")
    assert orc.contingencia == (subtotal * Decimal("0.10"))
    assert orc.total == subtotal + orc.contingencia


def test_dentro_do_teto_sem_alertas():
    orc = calcular_orcamento(
        voos=Decimal("1000"),
        hospedagem=Decimal("1000"),
        alimentacao=Decimal("500"),
        passeios=Decimal("300"),
        transporte_local=Decimal("200"),
        teto_informado=Decimal("5000"),
    )
    assert orc.dentro_do_teto is True
    assert orc.alertas == []


def test_estouro_dentro_da_tolerancia_sinaliza_sem_alerta_forte():
    # total = 3000 + 10% contingencia = 3300; teto = 3200 -> estouro de 100 (3.1%), dentro de 10%
    orc = calcular_orcamento(
        voos=Decimal("1000"),
        hospedagem=Decimal("1000"),
        alimentacao=Decimal("500"),
        passeios=Decimal("300"),
        transporte_local=Decimal("200"),
        teto_informado=Decimal("3200"),
        tolerancia=0.10,
    )
    assert orc.dentro_do_teto is False
    assert len(orc.alertas) == 1
    assert "dentro da tolerância" in orc.alertas[0]


def test_estouro_acima_da_tolerancia_gera_alerta_explicito_com_top3():
    # total = 3300; teto = 2000 -> estouro de 1300 (65%), muito acima de 10%
    orc = calcular_orcamento(
        voos=Decimal("1000"),
        hospedagem=Decimal("1000"),
        alimentacao=Decimal("500"),
        passeios=Decimal("300"),
        transporte_local=Decimal("200"),
        teto_informado=Decimal("2000"),
        tolerancia=0.10,
    )
    assert orc.dentro_do_teto is False
    assert len(orc.alertas) == 1
    alerta = orc.alertas[0]
    assert "Orçamento estourado" in alerta
    assert "voos" in alerta and "hospedagem" in alerta
    assert "Sugestão" in alerta
