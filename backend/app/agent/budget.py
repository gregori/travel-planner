from decimal import ROUND_HALF_UP, Decimal

from app.models.plan import Orcamento

CONTINGENCIA_MINIMA = Decimal("0.10")


def calcular_orcamento(
    *,
    voos: Decimal,
    hospedagem: Decimal,
    alimentacao: Decimal,
    passeios: Decimal,
    transporte_local: Decimal,
    teto_informado: Decimal | None,
    tolerancia: float = 0.10,
) -> Orcamento:
    """Monta o Orçamento detalhado com contingência mínima de 10% (RF-25) e
    alertas de estouro de teto (RF-26)."""

    subtotal = voos + hospedagem + alimentacao + passeios + transporte_local
    contingencia = (subtotal * CONTINGENCIA_MINIMA).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    orcamento = Orcamento(
        voos=voos,
        hospedagem=hospedagem,
        alimentacao=alimentacao,
        passeios=passeios,
        transporte_local=transporte_local,
        contingencia=contingencia,
        teto_informado=teto_informado,
    )

    if teto_informado is not None and teto_informado > 0:
        diferenca = orcamento.total - teto_informado
        if diferenca > 0:
            limite_tolerancia = teto_informado * Decimal(str(tolerancia))
            if diferenca <= limite_tolerancia:
                orcamento.alertas.append(
                    f"Orçamento {orcamento.total:.2f} está {diferenca:.2f} acima do teto "
                    f"informado ({teto_informado:.2f}), dentro da tolerância de "
                    f"{tolerancia:.0%}."
                )
            else:
                categorias = {
                    "voos": voos,
                    "hospedagem": hospedagem,
                    "alimentação": alimentacao,
                    "passeios": passeios,
                    "transporte local": transporte_local,
                }
                top3 = sorted(categorias.items(), key=lambda kv: kv[1], reverse=True)[:3]
                top3_texto = ", ".join(f"{nome} (R$ {valor:.2f})" for nome, valor in top3)
                orcamento.alertas.append(
                    f"Orçamento estourado: total de {orcamento.total:.2f} excede o teto de "
                    f"{teto_informado:.2f} em {diferenca:.2f} "
                    f"({(diferenca / teto_informado):.0%}), acima da tolerância de "
                    f"{tolerancia:.0%}. Categorias mais caras: {top3_texto}. "
                    "Sugestão: reduzir hospedagem (trocar por opção mais econômica), "
                    "diminuir o número de passeios pagos ou revisar a categoria de voo."
                )

    return orcamento
