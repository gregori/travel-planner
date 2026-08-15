from app.models.plan import TripPlan

AVISO_RODAPE = (
    "> **Aviso:** os preços apresentados são estimativas sujeitas a variação. "
    "Este sistema **não realiza reservas nem processa pagamentos** — use os "
    "links fornecidos para contratar diretamente com os provedores."
)


def _fmt_moeda(valor, moeda: str) -> str:
    return f"{valor:.2f} {moeda}"


def gerar_markdown(plan: TripPlan) -> str:
    """Gera o plano completo em Markdown autocontido (RF-30, RF-32, RF-33)."""
    brief = plan.brief
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
            linhas.append(
                f"- **{v.companhia}**{marca} — {v.origem} → {v.destino}: "
                f"{_fmt_moeda(v.preco_min, v.moeda)} a {_fmt_moeda(v.preco_max, v.moeda)} "
                f"({v.escalas} escala(s)) — *{v.fonte.tipo}*"
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
                    custo = f" (R$ {a.custo_estimado:.2f})" if a.custo_estimado else ""
                    linhas.append(f"- {a.titulo}{custo}")
                    if a.descricao:
                        linhas.append(f"  - {a.descricao}")
            else:
                linhas.append("- _Bloco livre_")
        linhas.append(f"_Custo estimado do dia: R$ {dia.custo_estimado_dia:.2f}_")
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
    linhas.append(f"| Categoria | Valor ({brief.moeda_exibicao}) |")
    linhas.append("|---|---|")
    linhas.append(f"| Voos | {o.voos:.2f} |")
    linhas.append(f"| Hospedagem | {o.hospedagem:.2f} |")
    linhas.append(f"| Alimentação | {o.alimentacao:.2f} |")
    linhas.append(f"| Passeios | {o.passeios:.2f} |")
    linhas.append(f"| Transporte local | {o.transporte_local:.2f} |")
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
    linhas.append("| Item | Tipo | Provedor | Confiança | Consultado em |")
    linhas.append("|---|---|---|---|---|")
    for f in plan.fontes:
        linhas.append(
            f"| {f.observacao or f.provedor} | {f.tipo} | {f.provedor} | {f.confianca} | "
            f"{f.consultado_em.strftime('%d/%m/%Y %H:%M UTC')} |"
        )
    linhas.append("")

    linhas.append("---")
    linhas.append(AVISO_RODAPE)

    return "\n".join(linhas)
