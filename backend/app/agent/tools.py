import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from app.agent.budget import calcular_orcamento
from app.agent.cache import chamada_cacheada, chave_cache
from app.agent.geo import eh_internacional
from app.config import Settings
from app.models.common import Fonte
from app.providers.base import (
    CriteriosAtracoes,
    CriteriosCambio,
    CriteriosHospedagem,
    CriteriosRestaurantes,
    CriteriosVoo,
)
from app.providers.registry import ProviderRegistry
from app.session.store import SessionState


@dataclass
class AgentContext:
    sessao: SessionState
    registry: ProviderRegistry
    settings: Settings


def _slug(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().strip().lower()


def _parse_data(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


async def tool_atualizar_briefing(ctx: AgentContext, **campos: Any) -> dict:
    campos_limpos = {k: v for k, v in campos.items() if v is not None}
    inferidos = list(ctx.sessao.brief.campos_inferidos)
    ctx.sessao.brief = ctx.sessao.brief.merge(**campos_limpos)
    if inferidos:
        ctx.sessao.brief.campos_inferidos = inferidos
    return {
        "briefing": ctx.sessao.brief.model_dump(mode="json"),
        "campos_faltantes": ctx.sessao.brief.campos_faltantes(),
        "pronto_para_planejar": ctx.sessao.brief.pronto_para_planejar(),
    }


async def tool_buscar_hospedagem(
    ctx: AgentContext,
    cidade: str,
    check_in: str | None = None,
    check_out: str | None = None,
    hospedes: int = 1,
    preco_min: float | None = None,
    preco_max: float | None = None,
) -> dict:
    criterios = CriteriosHospedagem(
        cidade=cidade,
        check_in=_parse_data(check_in),
        check_out=_parse_data(check_out),
        hospedes=hospedes,
        preco_min=Decimal(str(preco_min)) if preco_min is not None else None,
        preco_max=Decimal(str(preco_max)) if preco_max is not None else None,
        moeda=ctx.sessao.brief.moeda_exibicao,
    )
    chave = chave_cache("buscar_hospedagem", cidade=_slug(cidade), check_in=check_in, check_out=check_out)
    avisos: list[str] = []
    resultado = await chamada_cacheada(
        ctx.sessao,
        chave,
        ctx.settings.cache_ttl_minutes,
        lambda: ctx.registry.buscar_hospedagem(criterios, avisos),
    )
    return {
        "opcoes": [o.model_dump(mode="json") for o in resultado.itens],
        "motivo_vazio": resultado.motivo_vazio,
        "avisos": avisos,
    }


async def tool_buscar_atracoes(
    ctx: AgentContext,
    cidade: str,
    interesses: list[str] | None = None,
    perfil: str = "geral",
) -> dict:
    criterios = CriteriosAtracoes(cidade=cidade, interesses=interesses or [], perfil=perfil)
    chave = chave_cache("buscar_atracoes", cidade=_slug(cidade), interesses=sorted(interesses or []))
    avisos: list[str] = []
    resultado = await chamada_cacheada(
        ctx.sessao,
        chave,
        ctx.settings.cache_ttl_minutes,
        lambda: ctx.registry.buscar_atracoes(criterios, avisos),
    )
    return {
        "atracoes": [a.model_dump(mode="json") for a in resultado.itens],
        "motivo_vazio": resultado.motivo_vazio,
        "avisos": avisos,
    }


async def tool_buscar_restaurantes(
    ctx: AgentContext,
    cidade: str,
    restricoes: list[str] | None = None,
    faixa_preco: str | None = None,
) -> dict:
    criterios = CriteriosRestaurantes(cidade=cidade, restricoes=restricoes or [], faixa_preco=faixa_preco)
    chave = chave_cache("buscar_restaurantes", cidade=_slug(cidade), restricoes=sorted(restricoes or []))
    avisos: list[str] = []
    resultado = await chamada_cacheada(
        ctx.sessao,
        chave,
        ctx.settings.cache_ttl_minutes,
        lambda: ctx.registry.buscar_restaurantes(criterios, avisos),
    )
    return {
        "restaurantes": [r.model_dump(mode="json") for r in resultado.itens],
        "motivo_vazio": resultado.motivo_vazio,
        "avisos": avisos,
    }


async def tool_estimar_voos(
    ctx: AgentContext,
    origem: str,
    destino: str,
    data_ida: str | None = None,
    data_volta: str | None = None,
    passageiros: int = 1,
) -> dict:
    criterios = CriteriosVoo(
        origem=origem,
        destino=destino,
        data_ida=_parse_data(data_ida),
        data_volta=_parse_data(data_volta),
        passageiros=passageiros,
        moeda=ctx.sessao.brief.moeda_exibicao,
    )
    chave = chave_cache("estimar_voos", origem=_slug(origem), destino=_slug(destino))
    avisos: list[str] = []
    resultado = await chamada_cacheada(
        ctx.sessao,
        chave,
        ctx.settings.cache_ttl_minutes,
        lambda: ctx.registry.estimar_voos(criterios, avisos),
    )
    return {
        "opcoes": [o.model_dump(mode="json") for o in resultado.itens],
        "motivo_vazio": resultado.motivo_vazio,
        "avisos": avisos,
    }


async def tool_cotar_cambio(ctx: AgentContext, moeda_origem: str, moeda_destino: str) -> dict:
    criterios = CriteriosCambio(moeda_origem=moeda_origem, moeda_destino=moeda_destino)
    chave = chave_cache("cotar_cambio", moeda_origem=moeda_origem, moeda_destino=moeda_destino)
    avisos: list[str] = []
    cotacao = await chamada_cacheada(
        ctx.sessao,
        chave,
        ctx.settings.cache_ttl_minutes,
        lambda: ctx.registry.cotar_cambio(criterios, avisos),
    )
    if cotacao is None:
        return {"cotacao": None, "motivo_vazio": "Par de moedas não suportado.", "avisos": avisos}
    return {"cotacao": cotacao.model_dump(mode="json"), "motivo_vazio": None, "avisos": avisos}


async def tool_info_pratica(
    ctx: AgentContext,
    destino: str,
    nacionalidade: str | None = None,
    periodo: str | None = None,
) -> dict:
    """Checklist prático: clima, documentação, tomada/adaptador, moeda (RF-27/28).

    Heurística leve e sempre rotulada como estimativa — nunca dado oficial.
    """
    internacional = eh_internacional(destino, ctx.sessao.brief.moeda_orcamento)
    requisitos_entrada: list[str] = []
    if internacional:
        requisitos_entrada = [
            f"Verifique exigência de visto/autorização de viagem para {nacionalidade or 'sua nacionalidade'} "
            f"rumo a {destino} na fonte oficial do consulado/imigração antes de comprar passagens.",
            "Confirme validade mínima do passaporte exigida pelo país de destino (geralmente 6 meses).",
        ]
    fonte = Fonte(
        tipo="estimativa",
        provedor="web",
        url=None,
        consultado_em=datetime.now(UTC),
        confianca="baixa",
        observacao="Informação heurística geral; sempre confirme em fonte oficial antes da viagem.",
    )
    documentos_base = ["Reserva de hospedagem impressa/digital"]
    documentos_base += (
        ["Passaporte válido", "Verificar exigência de visto"]
        if internacional
        else ["Documento de identidade com foto"]
    )
    checklist = {
        "documentos": documentos_base,
        "clima": f"Consulte a previsão de {periodo or 'período da viagem'} para {destino} próximo à data — "
        "estimativa não substitui previsão atualizada.",
        "moeda_e_cambio": ctx.sessao.brief.moeda_exibicao,
        "tomada_adaptador": "Verifique o padrão de tomada local; leve adaptador universal por precaução.",
        "o_que_levar": [
            "Adaptador de tomada",
            "Medicamentos de uso pessoal",
            "Cópia de documentos",
        ],
        "requisitos_entrada": requisitos_entrada,
    }
    return {"checklist": checklist, "fonte": fonte.model_dump(mode="json")}


async def tool_calcular_orcamento(
    ctx: AgentContext,
    voos: float = 0,
    hospedagem: float = 0,
    alimentacao: float = 0,
    passeios: float = 0,
    transporte_local: float = 0,
    teto_informado: float | None = None,
) -> dict:
    orcamento = calcular_orcamento(
        voos=Decimal(str(voos)),
        hospedagem=Decimal(str(hospedagem)),
        alimentacao=Decimal(str(alimentacao)),
        passeios=Decimal(str(passeios)),
        transporte_local=Decimal(str(transporte_local)),
        teto_informado=Decimal(str(teto_informado))
        if teto_informado is not None
        else (ctx.sessao.brief.orcamento_total),
        tolerancia=ctx.sessao.brief.tolerancia_orcamento,
    )
    return {"orcamento": orcamento.model_dump(mode="json")}


TOOL_HANDLERS = {
    "atualizar_briefing": tool_atualizar_briefing,
    "buscar_hospedagem": tool_buscar_hospedagem,
    "buscar_atracoes": tool_buscar_atracoes,
    "buscar_restaurantes": tool_buscar_restaurantes,
    "estimar_voos": tool_estimar_voos,
    "cotar_cambio": tool_cotar_cambio,
    "info_pratica": tool_info_pratica,
    "calcular_orcamento": tool_calcular_orcamento,
}


TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "atualizar_briefing",
            "description": "Atualiza o TripBrief com os campos que o usuário informou nesta mensagem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origem": {"type": "string"},
                    "destino": {"type": "string"},
                    "data_ida": {"type": "string", "format": "date"},
                    "data_volta": {"type": "string", "format": "date"},
                    "mes_referencia": {"type": "string"},
                    "duracao_dias": {"type": "integer"},
                    "datas_flexiveis": {"type": "boolean"},
                    "adultos": {"type": "integer"},
                    "criancas_idades": {"type": "array", "items": {"type": "integer"}},
                    "orcamento_total": {"type": "number"},
                    "moeda_orcamento": {"type": "string"},
                    "moeda_exibicao": {"type": "string"},
                    "tipo_viagem": {
                        "type": "string",
                        "enum": [
                            "passeio",
                            "romantica",
                            "familia",
                            "aventura",
                            "cultural",
                            "descanso",
                        ],
                    },
                    "interesses": {"type": "array", "items": {"type": "string"}},
                    "restricoes_alimentares": {"type": "array", "items": {"type": "string"}},
                    "restricoes_mobilidade": {"type": "string"},
                    "outras_restricoes": {"type": "array", "items": {"type": "string"}},
                    "ritmo": {"type": "string", "enum": ["leve", "moderado", "intenso"]},
                    "nacionalidade": {"type": "string"},
                    "campos_inferidos": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_hospedagem",
            "description": "Busca opções de hospedagem no destino.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cidade": {"type": "string"},
                    "check_in": {"type": "string", "format": "date"},
                    "check_out": {"type": "string", "format": "date"},
                    "hospedes": {"type": "integer"},
                    "preco_min": {"type": "number"},
                    "preco_max": {"type": "number"},
                },
                "required": ["cidade"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_atracoes",
            "description": "Busca atrações e passeios compatíveis com os interesses do viajante.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cidade": {"type": "string"},
                    "interesses": {"type": "array", "items": {"type": "string"}},
                    "perfil": {"type": "string"},
                },
                "required": ["cidade"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_restaurantes",
            "description": "Busca restaurantes respeitando restrições alimentares.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cidade": {"type": "string"},
                    "restricoes": {"type": "array", "items": {"type": "string"}},
                    "faixa_preco": {"type": "string"},
                },
                "required": ["cidade"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estimar_voos",
            "description": "Estima faixa de preço de voos por rota e época (nunca valor único).",
            "parameters": {
                "type": "object",
                "properties": {
                    "origem": {"type": "string"},
                    "destino": {"type": "string"},
                    "data_ida": {"type": "string", "format": "date"},
                    "data_volta": {"type": "string", "format": "date"},
                    "passageiros": {"type": "integer"},
                },
                "required": ["origem", "destino"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cotar_cambio",
            "description": "Cota câmbio entre duas moedas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "moeda_origem": {"type": "string"},
                    "moeda_destino": {"type": "string"},
                },
                "required": ["moeda_origem", "moeda_destino"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "info_pratica",
            "description": "Retorna clima, documentação, tomada/adaptador e moeda para o destino.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destino": {"type": "string"},
                    "nacionalidade": {"type": "string"},
                    "periodo": {"type": "string"},
                },
                "required": ["destino"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calcular_orcamento",
            "description": "Calcula o orçamento por categoria, com contingência e alertas de estouro.",
            "parameters": {
                "type": "object",
                "properties": {
                    "voos": {"type": "number"},
                    "hospedagem": {"type": "number"},
                    "alimentacao": {"type": "number"},
                    "passeios": {"type": "number"},
                    "transporte_local": {"type": "number"},
                    "teto_informado": {"type": "number"},
                },
            },
        },
    },
]
