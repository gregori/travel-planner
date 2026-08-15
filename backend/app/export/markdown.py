from app.models.common import Fonte
from app.models.plan import TripPlan

AVISO_RODAPE = (
    "> **Aviso:** os preços apresentados são estimativas sujeitas a variação. "
    "Este sistema **não realiza reservas nem processa pagamentos** — use os "
    "links fornecidos para contratar diretamente com os provedores."
)


def _fmt_moeda(valor, moeda: str) -> str:
    return f"{valor:.2f} {moeda}"


def montar_linhas_fontes(plan: TripPlan) -> list[tuple[str, str, Fonte]]:
    """Constrói a lista (item, valor, Fonte) para a seção "Fontes e
    confiabilidade" (RF-32), ligando cada preço à sua origem — em vez de
    depender só de `plan.fontes` "achatada", que não diz a que preço cada
    fonte se refere."""
    linhas: list[tuple[str, str, Fonte]] = []
    for v in plan.opcoes_voo:
        valor = f"{_fmt_moeda(v.preco_min, v.moeda)} a {_fmt_moeda(v.preco_max, v.moeda)}"
        linhas.append((f"Voo {v.companhia} ({v.origem} → {v.destino})", valor, v.fonte))
    for h in plan.opcoes_hospedagem:
        linhas.append((f"Hospedagem: {h.nome}", f"{_fmt_moeda(h.preco_por_noite, h.moeda)}/noite", h.fonte))
    for r in plan.refeicoes:
        linhas.append((f"Restaurante: {r.nome}", r.faixa_preco or "—", r.fonte))
    for dia in plan.itinerario:
        for a in dia.manha + dia.tarde + dia.noite:
            if a.custo_estimado > 0 and a.fonte:
                linhas.append(
                    (f"Atividade: {a.titulo} (dia {dia.dia})", _fmt_moeda(a.custo_estimado, a.moeda), a.fonte)
                )
    moeda_exibicao = plan.brief.moeda_exibicao
    for fonte in plan.orcamento.fontes:
        texto = (fonte.observacao or "").lower()
        if "aliment" in texto:
            rotulo = f"Alimentação (estimativa): {_fmt_moeda(plan.orcamento.alimentacao, moeda_exibicao)}"
        elif "transporte" in texto:
            valor = _fmt_moeda(plan.orcamento.transporte_local, moeda_exibicao)
            rotulo = f"Transporte local (estimativa): {valor}"
        else:
            rotulo = "Estimativa heurística de orçamento"
        linhas.append((rotulo, "—", fonte))
    if plan.cambio:
        linhas.append(
            (
                f"Câmbio {plan.cambio.moeda_origem} → {plan.cambio.moeda_destino}",
                f"{plan.cambio.taxa:.4f}",
                plan.cambio.fonte,
            )
        )
    return linhas


def gerar_markdown(plan: TripPlan) -> str:
    """Gera o plano completo em Markdown autocontido (RF-30, RF-32, RF-33)."""
    brief = plan.brief
    moeda = brief.moeda_exibicao
    linhas: list[str] = []

    linhas.append(f"# Roteiro de viagem — {brief.destino}")
    linhas.append("")
    linhas.append(f"_Gerado em {plan.gerado_em.strftime('%d/%m/%Y %H:%M UTC')}_")
    linhas.append("")
    linhas.append(plan.resumo)
    linhas.append("")

    if plan.avisos:
        linhas.append("## Avisos")
        for a in plan.avisos:
            linhas.append(f"- ⚠️ {a}")
        linhas.append("")

    linhas.append("## Opções de voo")
    if plan.opcoes_voo:
        for v in plan.opcoes_voo:
            marca = " ⭐ recomendada" if v.recomendada else ""
            link = f" — [comparar preços]({v.link})" if v.link else ""
            linhas.append(
                f"- **{v.companhia}**{marca} — {v.origem} → {v.destino}: "
                f"{_fmt_moeda(v.preco_min, v.moeda)} a {_fmt_moeda(v.preco_max, v.moeda)} "
                f"({v.escalas} escala(s)){link} — *{v.fonte.tipo}*"
            )
            if v.justificativa:
                linhas.append(f"  - {v.justificativa}")
    else:
        linhas.append("_Nenhuma opção de voo encontrada — informe a origem para estimar preços._")
    linhas.append("")

    linhas.append("## Opções de hospedagem")
    if plan.opcoes_hospedagem:
        for h in plan.opcoes_hospedagem:
            marca = " ⭐ recomendada" if h.recomendada else ""
            link = f" — [link]({h.link})" if h.link else ""
            linhas.append(
                f"- **{h.nome}**{marca} ({h.tipo}) — {_fmt_moeda(h.preco_por_noite, h.moeda)}/noite "
                f"— {h.localizacao}{link} — *{h.fonte.tipo}*"
            )
            if h.justificativa:
                linhas.append(f"  - {h.justificativa}")
    else:
        linhas.append("_Nenhuma opção de hospedagem encontrada._")
    linhas.append("")

    linhas.append("## Itinerário dia a dia")
    for dia in plan.itinerario:
        data_txt = f" — {dia.data.strftime('%d/%m/%Y')}" if dia.data else ""
        linhas.append(f"### Dia {dia.dia}{data_txt} — {dia.regiao}")
        if dia.observacao:
            linhas.append(f"_{dia.observacao}_")
        for bloco_nome, bloco in (("Manhã", dia.manha), ("Tarde", dia.tarde), ("Noite", dia.noite)):
            linhas.append(f"**{bloco_nome}:**")
            if bloco:
                for a in bloco:
                    custo = f" ({_fmt_moeda(a.custo_estimado, a.moeda)})" if a.custo_estimado else ""
                    linhas.append(f"- {a.titulo}{custo}")
                    if a.descricao:
                        linhas.append(f"  - {a.descricao}")
            else:
                linhas.append("- _Bloco livre_")
        linhas.append(f"_Custo estimado do dia: {_fmt_moeda(dia.custo_estimado_dia, moeda)}_")
        linhas.append("")

    linhas.append("## Restaurantes sugeridos")
    if plan.refeicoes:
        for r in plan.refeicoes:
            linhas.append(
                f"- **{r.nome}** ({r.tipo_refeicao}, {r.culinaria or 'culinária variada'}) — "
                f"{r.compatibilidade} — *{r.fonte.tipo}*"
            )
    else:
        linhas.append("_Nenhuma sugestão de restaurante encontrada para os critérios informados._")
    linhas.append("")

    o = plan.orcamento
    linhas.append("## Orçamento detalhado")
    linhas.append(f"| Categoria | Valor ({moeda}) |")
    linhas.append("|---|---|")
    linhas.append(f"| Voos | {o.voos:.2f} |")
    linhas.append(f"| Hospedagem | {o.hospedagem:.2f} |")
    linhas.append(f"| Alimentação (estimativa) | {o.alimentacao:.2f} |")
    linhas.append(f"| Passeios | {o.passeios:.2f} |")
    linhas.append(f"| Transporte local (estimativa) | {o.transporte_local:.2f} |")
    linhas.append(f"| Contingência | {o.contingencia:.2f} |")
    linhas.append(f"| **Total** | **{o.total:.2f}** |")
    if o.teto_informado is not None:
        status = "dentro do teto" if o.dentro_do_teto else "acima do teto"
        linhas.append(f"\nTeto informado: {o.teto_informado:.2f} — **{status}**.")
    for alerta in o.alertas:
        linhas.append(f"\n⚠️ {alerta}")
    linhas.append("")

    if plan.cambio:
        c = plan.cambio
        linhas.append("## Câmbio")
        linhas.append(
            f"1 {c.moeda_origem} = {c.taxa:.4f} {c.moeda_destino} "
            f"(consultado em {c.fonte.consultado_em.strftime('%d/%m/%Y %H:%M UTC')})"
        )
        linhas.append("")

    ck = plan.checklist
    linhas.append("## Checklist prático")
    if ck.documentos:
        linhas.append("**Documentos:** " + ", ".join(ck.documentos))
    if ck.requisitos_entrada:
        linhas.append("\n**Requisitos de entrada:**")
        for req in ck.requisitos_entrada:
            linhas.append(f"- {req}")
    if ck.clima:
        linhas.append(f"\n**Clima:** {ck.clima}")
    if ck.moeda_e_cambio:
        linhas.append(f"\n**Moeda:** {ck.moeda_e_cambio}")
    if ck.tomada_adaptador:
        linhas.append(f"\n**Tomada/adaptador:** {ck.tomada_adaptador}")
    if ck.o_que_levar:
        linhas.append("\n**O que levar:** " + ", ".join(ck.o_que_levar))
    linhas.append("")

    linhas.append("## Fontes e confiabilidade")
    linhas.append("| Item | Valor | Tipo | Confiança | Consultado em |")
    linhas.append("|---|---|---|---|---|")
    for item, valor, f in montar_linhas_fontes(plan):
        linhas.append(
            f"| {item} | {valor} | {f.tipo} | {f.confianca} | "
            f"{f.consultado_em.strftime('%d/%m/%Y %H:%M UTC')} |"
        )
    linhas.append("")

    linhas.append("---")
    linhas.append(AVISO_RODAPE)

    return "\n".join(linhas)
