import unicodedata
from dataclasses import dataclass

# Heurística leve para MVP pt-BR: mapeia destinos conhecidos para moeda,
# hemisfério (para estação do ano) e padrão de tomada elétrica local.
# Não é uma fonte geográfica oficial — usada apenas para decidir se cabe
# cotação de câmbio (RF-13), alerta de documentação de entrada (RF-28) e
# checklist prático de clima/tomada (RF-27).


@dataclass(frozen=True)
class InfoDestino:
    moeda: str
    hemisferio: str  # "norte" | "sul"
    tomada: str


MOEDA_PADRAO_NACIONAL = "BRL"

_INFO_POR_DESTINO: dict[str, InfoDestino] = {
    "lisboa": InfoDestino("EUR", "norte", "tipo C/F (230V, dois pinos redondos)"),
    "portugal": InfoDestino("EUR", "norte", "tipo C/F (230V, dois pinos redondos)"),
    "porto": InfoDestino("EUR", "norte", "tipo C/F (230V, dois pinos redondos)"),
    "paris": InfoDestino("EUR", "norte", "tipo C/E (230V, dois pinos redondos)"),
    "franca": InfoDestino("EUR", "norte", "tipo C/E (230V, dois pinos redondos)"),
    "france": InfoDestino("EUR", "norte", "tipo C/E (230V, dois pinos redondos)"),
    "roma": InfoDestino("EUR", "norte", "tipo C/F/L (230V, dois ou três pinos redondos)"),
    "italia": InfoDestino("EUR", "norte", "tipo C/F/L (230V, dois ou três pinos redondos)"),
    "madri": InfoDestino("EUR", "norte", "tipo C/F (230V, dois pinos redondos)"),
    "madrid": InfoDestino("EUR", "norte", "tipo C/F (230V, dois pinos redondos)"),
    "espanha": InfoDestino("EUR", "norte", "tipo C/F (230V, dois pinos redondos)"),
    "londres": InfoDestino("GBP", "norte", "tipo G (230V, três pinos retangulares)"),
    "reino unido": InfoDestino("GBP", "norte", "tipo G (230V, três pinos retangulares)"),
    "nova york": InfoDestino("USD", "norte", "tipo A/B (120V, pinos chatos)"),
    "new york": InfoDestino("USD", "norte", "tipo A/B (120V, pinos chatos)"),
    "eua": InfoDestino("USD", "norte", "tipo A/B (120V, pinos chatos)"),
    "estados unidos": InfoDestino("USD", "norte", "tipo A/B (120V, pinos chatos)"),
    "miami": InfoDestino("USD", "norte", "tipo A/B (120V, pinos chatos)"),
    "orlando": InfoDestino("USD", "norte", "tipo A/B (120V, pinos chatos)"),
    "buenos aires": InfoDestino("ARS", "sul", "tipo C/I (220V)"),
    "argentina": InfoDestino("ARS", "sul", "tipo C/I (220V)"),
    "santiago": InfoDestino("CLP", "sul", "tipo C/L (220V)"),
    "chile": InfoDestino("CLP", "sul", "tipo C/L (220V)"),
    "lima": InfoDestino("PEN", "sul", "tipo A/C (220V)"),
    "peru": InfoDestino("PEN", "sul", "tipo A/C (220V)"),
    "tokyo": InfoDestino("JPY", "norte", "tipo A/B (100V, pinos chatos)"),
    "toquio": InfoDestino("JPY", "norte", "tipo A/B (100V, pinos chatos)"),
    "japao": InfoDestino("JPY", "norte", "tipo A/B (100V, pinos chatos)"),
}

_INFO_PADRAO_BRASIL = InfoDestino("BRL", "sul", "tipo N (127V/220V conforme o estado)")


def _slug(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().strip().lower()


def _info_destino(destino: str) -> InfoDestino:
    destino_slug = _slug(destino)
    for chave, info in _INFO_POR_DESTINO.items():
        if chave in destino_slug:
            return info
    return _INFO_PADRAO_BRASIL


def moeda_do_destino(destino: str) -> str:
    return _info_destino(destino).moeda


def eh_internacional(destino: str, moeda_orcamento: str = MOEDA_PADRAO_NACIONAL) -> bool:
    return moeda_do_destino(destino) != moeda_orcamento


def tomada_do_destino(destino: str) -> str:
    return _info_destino(destino).tomada


_ESTACAO_POR_MES_HEMISFERIO_SUL = {
    12: "verão",
    1: "verão",
    2: "verão",
    3: "outono",
    4: "outono",
    5: "outono",
    6: "inverno",
    7: "inverno",
    8: "inverno",
    9: "primavera",
    10: "primavera",
    11: "primavera",
}
_ESTACAO_POR_MES_HEMISFERIO_NORTE = {
    12: "inverno",
    1: "inverno",
    2: "inverno",
    3: "primavera",
    4: "primavera",
    5: "primavera",
    6: "verão",
    7: "verão",
    8: "verão",
    9: "outono",
    10: "outono",
    11: "outono",
}

_DESCRICAO_ESTACAO = {
    "verão": "dias quentes; leve roupas leves e protetor solar",
    "inverno": "temperaturas baixas; leve casacos e roupas em camadas",
    "outono": "temperaturas amenas e possibilidade de chuva; leve um casaco leve",
    "primavera": "clima ameno e variável; leve roupas em camadas",
}

_NOME_MES_PARA_NUMERO = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


def estacao_do_ano(destino: str, mes_numero: int | None) -> str | None:
    if mes_numero is None:
        return None
    hemisferio = _info_destino(destino).hemisferio
    tabela = _ESTACAO_POR_MES_HEMISFERIO_SUL if hemisferio == "sul" else _ESTACAO_POR_MES_HEMISFERIO_NORTE
    return tabela.get(mes_numero)


def descricao_clima_heuristica(destino: str, mes_referencia: str | None, mes_numero: int | None) -> str:
    """Estimativa heurística de clima por estação do ano — não é previsão
    meteorológica real; o checklist deixa isso explícito (RF-27)."""
    numero = mes_numero or (_NOME_MES_PARA_NUMERO.get(_slug(mes_referencia)) if mes_referencia else None)
    estacao = estacao_do_ano(destino, numero)
    periodo = mes_referencia or "o período da viagem"
    if estacao is None:
        return f"Não foi possível estimar a estação em {periodo}; consulte a previsão perto da data."
    descricao = _DESCRICAO_ESTACAO[estacao]
    return (
        f"Em {periodo}, {destino} deve estar em {estacao} — {descricao} "
        "(estimativa por estação, não é previsão do tempo)."
    )
