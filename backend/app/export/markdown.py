from app.models.common import Source
from app.models.plan import TripPlan

FOOTER_NOTICE = (
    "> **Aviso:** os preços apresentados são estimativas sujeitas a variação. "
    "Este sistema **não realiza reservas nem processa pagamentos** — use os "
    "links fornecidos para contratar diretamente com os provedores."
)


def _fmt_currency(value, currency: str) -> str:
    return f"{value:.2f} {currency}"


def build_source_rows(plan: TripPlan) -> list[tuple[str, str, Source]]:
    """Constrói a lista (item, valor, Source) para a seção "Fontes e
    confiabilidade" (RF-32), ligando cada preço à sua origem — em vez de
    depender só de `plan.sources` "achatada", que não diz a que preço cada
    fonte se refere."""
    rows: list[tuple[str, str, Source]] = []
    for f in plan.flight_options:
        value = f"{_fmt_currency(f.min_price, f.currency)} a {_fmt_currency(f.max_price, f.currency)}"
        rows.append((f"Voo {f.airline} ({f.origin} → {f.destination})", value, f.source))
    for h in plan.accommodation_options:
        rows.append(
            (f"Hospedagem: {h.name}", f"{_fmt_currency(h.price_per_night, h.currency)}/noite", h.source)
        )
    for m in plan.meals:
        rows.append((f"Restaurante: {m.name}", m.price_range or "—", m.source))
    for day in plan.itinerary:
        for a in day.morning + day.afternoon + day.evening:
            if a.estimated_cost > 0 and a.source:
                rows.append(
                    (
                        f"Atividade: {a.title} (dia {day.day})",
                        _fmt_currency(a.estimated_cost, a.currency),
                        a.source,
                    )
                )
    display_currency = plan.brief.display_currency
    for source in plan.budget.sources:
        text = (source.note or "").lower()
        if "aliment" in text:
            label = f"Alimentação (estimativa): {_fmt_currency(plan.budget.food, display_currency)}"
        elif "transporte" in text:
            value = _fmt_currency(plan.budget.local_transport, display_currency)
            label = f"Transporte local (estimativa): {value}"
        else:
            label = "Estimativa heurística de orçamento"
        rows.append((label, "—", source))
    if plan.exchange_rate:
        rows.append(
            (
                f"Câmbio {plan.exchange_rate.source_currency} → {plan.exchange_rate.target_currency}",
                f"{plan.exchange_rate.rate:.4f}",
                plan.exchange_rate.source,
            )
        )
    return rows


def generate_markdown(plan: TripPlan) -> str:
    """Gera o plano completo em Markdown autocontido (RF-30, RF-32, RF-33)."""
    brief = plan.brief
    currency = brief.display_currency
    lines: list[str] = []

    lines.append(f"# Roteiro de viagem — {brief.destination}")
    lines.append("")
    lines.append(f"_Gerado em {plan.generated_at.strftime('%d/%m/%Y %H:%M UTC')}_")
    lines.append("")
    lines.append(plan.summary)
    lines.append("")

    if plan.warnings:
        lines.append("## Avisos")
        for w in plan.warnings:
            lines.append(f"- ⚠️ {w}")
        lines.append("")

    lines.append("## Opções de voo")
    if plan.flight_options:
        for f in plan.flight_options:
            badge = " ⭐ recomendada" if f.recommended else ""
            link = f" — [comparar preços]({f.link})" if f.link else ""
            lines.append(
                f"- **{f.airline}**{badge} — {f.origin} → {f.destination}: "
                f"{_fmt_currency(f.min_price, f.currency)} a {_fmt_currency(f.max_price, f.currency)} "
                f"({f.stops} escala(s)){link} — *{f.source.type}*"
            )
            if f.rationale:
                lines.append(f"  - {f.rationale}")
    else:
        lines.append("_Nenhuma opção de voo encontrada — informe a origem para estimar preços._")
    lines.append("")

    lines.append("## Opções de hospedagem")
    if plan.accommodation_options:
        for h in plan.accommodation_options:
            badge = " ⭐ recomendada" if h.recommended else ""
            link = f" — [link]({h.link})" if h.link else ""
            lines.append(
                f"- **{h.name}**{badge} ({h.type}) — {_fmt_currency(h.price_per_night, h.currency)}/noite "
                f"— {h.location}{link} — *{h.source.type}*"
            )
            if h.rationale:
                lines.append(f"  - {h.rationale}")
    else:
        lines.append("_Nenhuma opção de hospedagem encontrada._")
    lines.append("")

    lines.append("## Itinerário dia a dia")
    for day in plan.itinerary:
        date_text = f" — {day.date.strftime('%d/%m/%Y')}" if day.date else ""
        lines.append(f"### Dia {day.day}{date_text} — {day.region}")
        if day.note:
            lines.append(f"_{day.note}_")
        for block_name, block in (("Manhã", day.morning), ("Tarde", day.afternoon), ("Noite", day.evening)):
            lines.append(f"**{block_name}:**")
            if block:
                for a in block:
                    cost = f" ({_fmt_currency(a.estimated_cost, a.currency)})" if a.estimated_cost else ""
                    lines.append(f"- {a.title}{cost}")
                    if a.description:
                        lines.append(f"  - {a.description}")
            else:
                lines.append("- _Bloco livre_")
        lines.append(f"_Custo estimado do dia: {_fmt_currency(day.estimated_day_cost, currency)}_")
        lines.append("")

    lines.append("## Restaurantes sugeridos")
    if plan.meals:
        for m in plan.meals:
            lines.append(
                f"- **{m.name}** ({m.meal_type}, {m.cuisine or 'culinária variada'}) — "
                f"{m.compatibility} — *{m.source.type}*"
            )
    else:
        lines.append("_Nenhuma sugestão de restaurante encontrada para os critérios informados._")
    lines.append("")

    b = plan.budget
    lines.append("## Orçamento detalhado")
    lines.append(f"| Categoria | Valor ({currency}) |")
    lines.append("|---|---|")
    lines.append(f"| Voos | {b.flights:.2f} |")
    lines.append(f"| Hospedagem | {b.accommodation:.2f} |")
    lines.append(f"| Alimentação (estimativa) | {b.food:.2f} |")
    lines.append(f"| Passeios | {b.activities:.2f} |")
    lines.append(f"| Transporte local (estimativa) | {b.local_transport:.2f} |")
    lines.append(f"| Contingência | {b.contingency:.2f} |")
    lines.append(f"| **Total** | **{b.total:.2f}** |")
    if b.stated_cap is not None:
        status = "dentro do teto" if b.within_cap else "acima do teto"
        lines.append(f"\nTeto informado: {b.stated_cap:.2f} — **{status}**.")
    for alert in b.alerts:
        lines.append(f"\n⚠️ {alert}")
    lines.append("")

    if plan.exchange_rate:
        e = plan.exchange_rate
        lines.append("## Câmbio")
        lines.append(
            f"1 {e.source_currency} = {e.rate:.4f} {e.target_currency} "
            f"(consultado em {e.source.retrieved_at.strftime('%d/%m/%Y %H:%M UTC')})"
        )
        lines.append("")

    ck = plan.checklist
    lines.append("## Checklist prático")
    if ck.documents:
        lines.append("**Documentos:** " + ", ".join(ck.documents))
    if ck.entry_requirements:
        lines.append("\n**Requisitos de entrada:**")
        for req in ck.entry_requirements:
            lines.append(f"- {req}")
    if ck.weather:
        lines.append(f"\n**Clima:** {ck.weather}")
    if ck.currency_and_exchange:
        lines.append(f"\n**Moeda:** {ck.currency_and_exchange}")
    if ck.power_outlet:
        lines.append(f"\n**Tomada/adaptador:** {ck.power_outlet}")
    if ck.what_to_pack:
        lines.append("\n**O que levar:** " + ", ".join(ck.what_to_pack))
    lines.append("")

    lines.append("## Fontes e confiabilidade")
    lines.append("| Item | Valor | Tipo | Confiança | Consultado em |")
    lines.append("|---|---|---|---|---|")
    for item, value, s in build_source_rows(plan):
        lines.append(
            f"| {item} | {value} | {s.type} | {s.confidence} | "
            f"{s.retrieved_at.strftime('%d/%m/%Y %H:%M UTC')} |"
        )
    lines.append("")

    lines.append("---")
    lines.append(FOOTER_NOTICE)

    return "\n".join(lines)
