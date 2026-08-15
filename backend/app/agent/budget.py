from decimal import ROUND_HALF_UP, Decimal

from app.models.common import Source
from app.models.plan import Budget

MINIMUM_CONTINGENCY = Decimal("0.10")

_SUGGESTION_BY_CATEGORY = {
    "voos": "revisar a categoria/companhia do voo ou datas com tarifa menor",
    "hospedagem": "trocar a hospedagem por uma opção mais econômica",
    "alimentação": "reduzir refeições em restaurantes e priorizar opções mais simples",
    "passeios": "diminuir o número de passeios pagos",
    "transporte local": "priorizar transporte público em vez de particular",
}


def calculate_budget(
    *,
    flights: Decimal,
    accommodation: Decimal,
    food: Decimal,
    activities: Decimal,
    local_transport: Decimal,
    stated_cap: Decimal | None,
    tolerance: float = 0.10,
    currency: str = "BRL",
    sources: list[Source] | None = None,
) -> Budget:
    """Monta o Budget detalhado com contingência mínima de 10% (RF-25) e
    alertas de estouro de teto (RF-26)."""

    subtotal = flights + accommodation + food + activities + local_transport
    contingency = (subtotal * MINIMUM_CONTINGENCY).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    budget = Budget(
        flights=flights,
        accommodation=accommodation,
        food=food,
        activities=activities,
        local_transport=local_transport,
        contingency=contingency,
        stated_cap=stated_cap,
        sources=sources or [],
    )

    if stated_cap is not None and stated_cap > 0:
        difference = budget.total - stated_cap
        if difference > 0:
            tolerance_limit = stated_cap * Decimal(str(tolerance))
            if difference <= tolerance_limit:
                budget.alerts.append(
                    f"Orçamento {budget.total:.2f} está {difference:.2f} {currency} acima do teto "
                    f"informado ({stated_cap:.2f}), dentro da tolerância de "
                    f"{tolerance:.0%}."
                )
            else:
                categories = {
                    "voos": flights,
                    "hospedagem": accommodation,
                    "alimentação": food,
                    "passeios": activities,
                    "transporte local": local_transport,
                }
                priced_categories = {k: v for k, v in categories.items() if v > 0}
                top3 = sorted(priced_categories.items(), key=lambda kv: kv[1], reverse=True)[:3]
                top3_text = ", ".join(f"{name} ({currency} {value:.2f})" for name, value in top3)
                suggestions = "; ".join(_SUGGESTION_BY_CATEGORY[name] for name, _ in top3)
                budget.alerts.append(
                    f"Orçamento estourado: total de {budget.total:.2f} excede o teto de "
                    f"{stated_cap:.2f} em {difference:.2f} "
                    f"({(difference / stated_cap):.0%}), acima da tolerância de "
                    f"{tolerance:.0%}. Categorias mais caras: {top3_text}. "
                    f"Sugestões: {suggestions}."
                )

    return budget
