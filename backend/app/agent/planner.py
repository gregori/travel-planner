from datetime import UTC, datetime
from decimal import Decimal

from app.agent.budget import calcular_orcamento
from app.agent.itinerary import montar_itinerario
from app.agent.tools import (
    AgentContext,
    buscar_atracoes_cacheada,
    buscar_hospedagem_cacheada,
    buscar_restaurantes_cacheada,
    cotar_cambio_cacheado,
    estimar_voos_cacheado,
    tool_info_pratica,
)
from app.geo import eh_internacional, moeda_do_destino
from app.models.common import Fonte
from app.models.plan import Checklist, TripPlan

ALIMENTACAO_DIARIA_POR_PESSOA = Decimal("120")
TRANSPORTE_LOCAL_DIARIO_POR_PESSOA = Decimal("30")


def _perfil(brief) -> str:
    partes = [brief.tipo_viagem or "geral"]
    if brief.tem_criancas:
        partes.append("com crianças")
    if brief.restricoes_mobilidade:
        partes.append("mobilidade reduzida")
    return ", ".join(partes)


def _converter(valor: Decimal, moeda_origem: str, moeda_destino: str, taxa: Decimal | None) -> Decimal:
    if moeda_origem == moeda_destino or valor == 0:
        return valor
    if taxa is not None:
        return valor * taxa
    return valor


def _fonte_heuristica(observacao: str) -> Fonte:
    return Fonte(
        tipo="estimativa",
        provedor="heuristica",
        url=None,
        consultado_em=datetime.now(UTC),
        confianca="baixa",
        observacao=observacao,
    )


def _converter_itinerario_para_moeda_exibicao(
    itinerario, moeda_exibicao: str, taxa_cambio: Decimal | None
) -> None:
    """Converte o custo de cada atividade do pool (potencialmente na moeda do
    destino) para a moeda de exibição, para que o orçamento e o itinerário
    fiquem consistentes numa única moeda (RF-13)."""
    for dia in itinerario:
        for bloco in (dia.manha, dia.tarde, dia.noite):
            for atividade in bloco:
                if atividade.custo_estimado > 0 and atividade.moeda != moeda_exibicao:
                    atividade.custo_estimado = _converter(
                        atividade.custo_estimado, atividade.moeda, moeda_exibicao, taxa_cambio
                    )
                    atividade.moeda = moeda_exibicao
        dia.custo_estimado_dia = sum(
            (a.custo_estimado for a in dia.manha + dia.tarde + dia.noite), Decimal("0")
        )


async def gerar_plano(ctx: AgentContext) -> TripPlan:
    """Pipeline determinístico de geração do TripPlan (RF-20..28).

    A conversa (LLM) decide *quando* planejar; a montagem do plano em si é
    determinística para garantir os critérios de aceite (§11) de forma
    reprodutível, inclusive com `FakeLLM` nos testes (RNF-03). As buscas
    passam pelo mesmo cache/contador de chamadas usado pelas ferramentas do
    agente (RF-17, RNF-08).
    """
    brief = ctx.sessao.brief
    avisos: list[str] = []
    fontes: list[Fonte] = []

    destino = brief.destino or ""
    origem = brief.origem or "Origem não informada"
    dias_total = max(1, brief.duracao_estimada() or 3)

    # Câmbio (RF-13) — só quando a moeda do destino difere da moeda de exibição.
    moeda_local = moeda_do_destino(destino)
    cambio = None
    if moeda_local != brief.moeda_exibicao:
        cambio = await cotar_cambio_cacheado(ctx, moeda_local, brief.moeda_exibicao, avisos)
        if cambio:
            fontes.append(cambio.fonte)
    taxa_cambio = cambio.taxa if cambio else None

    # Hospedagem (RF-10, RF-24: >= 3 opções)
    resultado_h = await buscar_hospedagem_cacheada(
        ctx, destino, brief.data_ida, brief.data_volta, brief.total_viajantes, avisos
    )
    opcoes_hospedagem = resultado_h.itens
    if opcoes_hospedagem:
        mais_barata = min(opcoes_hospedagem, key=lambda h: h.preco_por_noite)
        mais_barata.recomendada = True
        mais_barata.justificativa = "Melhor custo-benefício entre as opções encontradas para o período."
        fontes.extend(h.fonte for h in opcoes_hospedagem)
    else:
        avisos.append(resultado_h.motivo_vazio or f"Nenhuma hospedagem encontrada em {destino}.")

    # Atrações (RF-11)
    resultado_a = await buscar_atracoes_cacheada(ctx, destino, brief.interesses, _perfil(brief), avisos)
    atividades_pool = list(resultado_a.itens)
    if not atividades_pool:
        avisos.append(resultado_a.motivo_vazio or f"Nenhuma atração encontrada em {destino}.")
    fontes.extend(a.fonte for a in atividades_pool if a.fonte)

    # Restaurantes (RF-14)
    resultado_r = await buscar_restaurantes_cacheada(ctx, destino, brief.restricoes_alimentares, avisos)
    refeicoes = list(resultado_r.itens)
    if not refeicoes:
        avisos.append(
            resultado_r.motivo_vazio
            or f"Nenhum restaurante encontrado em {destino} para as restrições informadas."
        )
    fontes.extend(r.fonte for r in refeicoes)

    # Voos (RF-12, RF-24: >= 2 opções)
    opcoes_voo = []
    if brief.origem:
        resultado_v = await estimar_voos_cacheado(
            ctx, origem, destino, brief.data_ida, brief.data_volta, brief.total_viajantes, avisos
        )
        opcoes_voo = resultado_v.itens
        fontes.extend(v.fonte for v in opcoes_voo)

    # Itinerário (RF-20..23)
    itinerario = montar_itinerario(brief, dias_total, list(atividades_pool), list(refeicoes))
    _converter_itinerario_para_moeda_exibicao(itinerario, brief.moeda_exibicao, taxa_cambio)

    # Orçamento (RF-25, RF-26) — usa sempre a opção recomendada (mais barata)
    hospedagem_escolhida = next((h for h in opcoes_hospedagem if h.recomendada), None) or (
        opcoes_hospedagem[0] if opcoes_hospedagem else None
    )
    voo_escolhido = next((v for v in opcoes_voo if v.recomendada), None) or (
        opcoes_voo[0] if opcoes_voo else None
    )
    custo_hospedagem = (
        _converter(
            hospedagem_escolhida.preco_por_noite,
            hospedagem_escolhida.moeda,
            brief.moeda_exibicao,
            taxa_cambio,
        )
        * dias_total
        if hospedagem_escolhida
        else Decimal("0")
    )
    custo_voos = (
        _converter(
            (voo_escolhido.preco_min + voo_escolhido.preco_max) / 2,
            voo_escolhido.moeda,
            brief.moeda_exibicao,
            taxa_cambio,
        )
        * brief.total_viajantes
        if voo_escolhido
        else Decimal("0")
    )
    # Atividades já convertidas para moeda_exibicao acima; soma direta.
    custo_passeios = (
        sum(
            (a.custo_estimado for dia in itinerario for a in dia.manha + dia.tarde + dia.noite),
            Decimal("0"),
        )
        * brief.total_viajantes
    )
    custo_alimentacao = ALIMENTACAO_DIARIA_POR_PESSOA * dias_total * brief.total_viajantes
    custo_transporte_local = TRANSPORTE_LOCAL_DIARIO_POR_PESSOA * dias_total * brief.total_viajantes

    fonte_alimentacao = _fonte_heuristica(
        f"Estimativa heurística de alimentação: {ALIMENTACAO_DIARIA_POR_PESSOA} {brief.moeda_exibicao}"
        "/pessoa/dia — não vem de um provedor específico."
    )
    fonte_transporte = _fonte_heuristica(
        f"Estimativa heurística de transporte local: {TRANSPORTE_LOCAL_DIARIO_POR_PESSOA} "
        f"{brief.moeda_exibicao}/pessoa/dia — não vem de um provedor específico."
    )
    fontes.append(fonte_alimentacao)
    fontes.append(fonte_transporte)

    orcamento = calcular_orcamento(
        voos=custo_voos,
        hospedagem=custo_hospedagem,
        alimentacao=custo_alimentacao,
        passeios=custo_passeios,
        transporte_local=custo_transporte_local,
        teto_informado=brief.orcamento_total,
        tolerancia=brief.tolerancia_orcamento,
        moeda=brief.moeda_exibicao,
        fontes=[fonte_alimentacao, fonte_transporte],
    )
    avisos.extend(orcamento.alertas)

    # Checklist prático (RF-27, RF-28)
    info = await tool_info_pratica(
        ctx, destino=destino, nacionalidade=brief.nacionalidade, periodo=brief.mes_referencia
    )
    checklist = Checklist(**info["checklist"])
    if not eh_internacional(destino, brief.moeda_orcamento):
        checklist.requisitos_entrada = []

    if not opcoes_voo:
        avisos.append("Sem origem informada, não foi possível estimar faixa de preço de voos.")
    if len(opcoes_hospedagem) < 3:
        avisos.append(f"Apenas {len(opcoes_hospedagem)} opções de hospedagem encontradas (recomendado: 3+).")
    if len(opcoes_voo) < 2 and opcoes_voo:
        avisos.append("Apenas 1 opção de voo encontrada (recomendado: 2+).")

    resumo = (
        f"Roteiro de {dias_total} dia(s) para {destino}, partindo de {origem}, para "
        f"{brief.total_viajantes} viajante(s). Orçamento total estimado: "
        f"{orcamento.total:.2f} {brief.moeda_exibicao}."
    )

    return TripPlan(
        brief=brief,
        resumo=resumo,
        opcoes_voo=opcoes_voo,
        opcoes_hospedagem=opcoes_hospedagem,
        itinerario=itinerario,
        refeicoes=refeicoes,
        orcamento=orcamento,
        cambio=cambio,
        checklist=checklist,
        fontes=fontes,
        avisos=list(dict.fromkeys(avisos)),
        gerado_em=datetime.now(UTC),
    )
