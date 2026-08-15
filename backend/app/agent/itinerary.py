from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from app.models.brief import TripBrief
from app.models.plan import Atividade, Deslocamento, DiaItinerario, SugestaoRefeicao

MAX_ATIVIDADES_POR_RITMO = {"leve": 2, "moderado": 3, "intenso": 4}
MAX_ATIVIDADES_RESTRITO = 2  # RF-22: crianças ou mobilidade reduzida


def _max_atividades_principais(brief: TripBrief) -> int:
    if brief.tem_criancas or brief.restricoes_mobilidade:
        return MAX_ATIVIDADES_RESTRITO
    return MAX_ATIVIDADES_POR_RITMO.get(brief.ritmo, 3)


def _atividade_livre(regiao: str) -> Atividade:
    return Atividade(
        titulo="Tempo livre / descanso",
        descricao="Sem atração específica encontrada para este bloco — aproveite para explorar "
        "por conta própria ou descansar.",
        regiao=regiao,
        duracao_min=None,
        custo_estimado=Decimal("0"),
        fonte=None,
    )


def _tomar_ate(disponiveis: list[Atividade], n: int) -> list[Atividade]:
    """Consome (pop) até `n` atividades da lista compartilhada da região, para
    que não sejam reaproveitadas em outro dia."""
    escolhidas: list[Atividade] = []
    for _ in range(min(n, len(disponiveis))):
        escolhidas.append(disponiveis.pop(0))
    return escolhidas


def _tomar_refeicao(refeicoes: list[SugestaoRefeicao], regiao: str) -> list[Atividade]:
    if not refeicoes:
        return []
    ref = refeicoes.pop(0)
    return [
        Atividade(
            titulo=f"Jantar: {ref.nome}",
            descricao=ref.compatibilidade,
            regiao=regiao,
            custo_estimado=Decimal("0"),
            fonte=ref.fonte,
        )
    ]


def montar_itinerario(
    brief: TripBrief,
    dias_total: int,
    atividades_pool: list[Atividade],
    refeicoes_pool: list[SugestaoRefeicao],
) -> list[DiaItinerario]:
    """Constrói o itinerário dia a dia (RF-20..23).

    - Agrupa atividades do mesmo dia por região (RF-21).
    - Limita atividades principais por ritmo/perfil (RF-22).
    - Reserva os dias de chegada/partida para logística, sem sobrepor
      atrações a check-in/check-out/deslocamento ao aeroporto (RF-23).
    """
    max_principais = _max_atividades_principais(brief)

    por_regiao: dict[str, list[Atividade]] = defaultdict(list)
    for a in atividades_pool:
        por_regiao[a.regiao or "Centro"].append(a)
    regioes_disponiveis = list(por_regiao.keys()) or ["Centro"]

    refeicoes_restantes = list(refeicoes_pool)
    data_base = brief.data_ida

    dias: list[DiaItinerario] = []
    for indice_dia in range(1, dias_total + 1):
        eh_chegada = indice_dia == 1
        eh_partida = indice_dia == dias_total and dias_total > 1
        regiao_do_dia = regioes_disponiveis[(indice_dia - 1) % len(regioes_disponiveis)]
        disponiveis = por_regiao.get(regiao_do_dia, [])

        manha: list[Atividade] = []
        tarde: list[Atividade] = []
        noite: list[Atividade] = []
        deslocamentos: list[Deslocamento] = []
        observacao = None

        if eh_chegada:
            manha = [
                Atividade(
                    titulo="Chegada e check-in",
                    descricao="Desembarque, deslocamento ao aeroporto/estação e check-in na "
                    "hospedagem. Sem atividades agendadas para não conflitar com o voo (RF-23).",
                    regiao=regiao_do_dia,
                    custo_estimado=Decimal("0"),
                )
            ]
            tarde = _tomar_ate(disponiveis, 1) or [_atividade_livre(regiao_do_dia)]
            noite = _tomar_refeicao(refeicoes_restantes, regiao_do_dia) or [_atividade_livre(regiao_do_dia)]
            observacao = "Dia de chegada: ritmo leve para absorver o deslocamento (RF-23)."
        elif eh_partida:
            manha = _tomar_ate(disponiveis, 1) or [_atividade_livre(regiao_do_dia)]
            tarde = [
                Atividade(
                    titulo="Checkout e deslocamento ao aeroporto",
                    descricao="Checkout da hospedagem e deslocamento com margem de segurança "
                    "para o horário do voo de volta (RF-23).",
                    regiao=regiao_do_dia,
                    custo_estimado=Decimal("0"),
                )
            ]
            noite = []
            observacao = "Dia de partida: sem atividades à noite para não conflitar com o voo (RF-23)."
        else:
            principais = _tomar_ate(disponiveis, max_principais)
            if not principais:
                principais = [_atividade_livre(regiao_do_dia)]
            metade = max(1, len(principais) // 2) if len(principais) > 1 else len(principais)
            manha = principais[:metade] or [_atividade_livre(regiao_do_dia)]
            tarde = principais[metade:] or []
            noite = _tomar_refeicao(refeicoes_restantes, regiao_do_dia) or [_atividade_livre(regiao_do_dia)]
            if brief.tem_criancas or brief.restricoes_mobilidade:
                observacao = "Ritmo ajustado: pausa explícita à tarde entre as atividades (RF-22)."

        if manha and tarde:
            deslocamentos.append(Deslocamento(de_bloco="manha", para_bloco="tarde", duracao_min=20))
        if tarde and noite:
            deslocamentos.append(Deslocamento(de_bloco="tarde", para_bloco="noite", duracao_min=20))

        custo_dia = sum((a.custo_estimado for a in manha + tarde + noite), Decimal("0"))

        dias.append(
            DiaItinerario(
                dia=indice_dia,
                data=(data_base + timedelta(days=indice_dia - 1)) if data_base else None,
                regiao=regiao_do_dia,
                manha=manha,
                tarde=tarde,
                noite=noite,
                deslocamentos=deslocamentos,
                custo_estimado_dia=custo_dia,
                observacao=observacao,
            )
        )

    return dias
