import unicodedata
from dataclasses import dataclass

# Heurística leve para MVP pt-BR: mapeia destinos conhecidos para moeda,
# hemisfério (para estação do ano) e padrão de tomada elétrica local.
# Não é uma fonte geográfica oficial — usada apenas para decidir se cabe
# cotação de câmbio (RF-13), alerta de documentação de entrada (RF-28) e
# checklist prático de clima/tomada (RF-27).


@dataclass(frozen=True)
class DestinationInfo:
    currency: str
    hemisphere: str  # "north" | "south"
    outlet: str


DEFAULT_DOMESTIC_CURRENCY = "BRL"

_INFO_BY_DESTINATION: dict[str, DestinationInfo] = {
    "lisboa": DestinationInfo("EUR", "north", "tipo C/F (230V, dois pinos redondos)"),
    "portugal": DestinationInfo("EUR", "north", "tipo C/F (230V, dois pinos redondos)"),
    "porto": DestinationInfo("EUR", "north", "tipo C/F (230V, dois pinos redondos)"),
    "paris": DestinationInfo("EUR", "north", "tipo C/E (230V, dois pinos redondos)"),
    "franca": DestinationInfo("EUR", "north", "tipo C/E (230V, dois pinos redondos)"),
    "france": DestinationInfo("EUR", "north", "tipo C/E (230V, dois pinos redondos)"),
    "roma": DestinationInfo("EUR", "north", "tipo C/F/L (230V, dois ou três pinos redondos)"),
    "italia": DestinationInfo("EUR", "north", "tipo C/F/L (230V, dois ou três pinos redondos)"),
    "madri": DestinationInfo("EUR", "north", "tipo C/F (230V, dois pinos redondos)"),
    "madrid": DestinationInfo("EUR", "north", "tipo C/F (230V, dois pinos redondos)"),
    "espanha": DestinationInfo("EUR", "north", "tipo C/F (230V, dois pinos redondos)"),
    "londres": DestinationInfo("GBP", "north", "tipo G (230V, três pinos retangulares)"),
    "reino unido": DestinationInfo("GBP", "north", "tipo G (230V, três pinos retangulares)"),
    "nova york": DestinationInfo("USD", "north", "tipo A/B (120V, pinos chatos)"),
    "new york": DestinationInfo("USD", "north", "tipo A/B (120V, pinos chatos)"),
    "eua": DestinationInfo("USD", "north", "tipo A/B (120V, pinos chatos)"),
    "estados unidos": DestinationInfo("USD", "north", "tipo A/B (120V, pinos chatos)"),
    "miami": DestinationInfo("USD", "north", "tipo A/B (120V, pinos chatos)"),
    "orlando": DestinationInfo("USD", "north", "tipo A/B (120V, pinos chatos)"),
    "buenos aires": DestinationInfo("ARS", "south", "tipo C/I (220V)"),
    "argentina": DestinationInfo("ARS", "south", "tipo C/I (220V)"),
    "santiago": DestinationInfo("CLP", "south", "tipo C/L (220V)"),
    "chile": DestinationInfo("CLP", "south", "tipo C/L (220V)"),
    "lima": DestinationInfo("PEN", "south", "tipo A/C (220V)"),
    "peru": DestinationInfo("PEN", "south", "tipo A/C (220V)"),
    "tokyo": DestinationInfo("JPY", "north", "tipo A/B (100V, pinos chatos)"),
    "toquio": DestinationInfo("JPY", "north", "tipo A/B (100V, pinos chatos)"),
    "japao": DestinationInfo("JPY", "north", "tipo A/B (100V, pinos chatos)"),
}

_DEFAULT_BRAZIL_INFO = DestinationInfo("BRL", "south", "tipo N (127V/220V conforme o estado)")

# Heurística leve para resolver nome de cidade -> código IATA do aeroporto
# principal, usada pelo SerpApiFlightsProvider (que exige código de aeroporto,
# não aceita nome de cidade livre). Cobre os destinos dos cenários de aceite
# (§3 REQUIREMENTS.md) e outros grandes hubs; rota não coberta aqui cai para
# estimativa mock (RF-16), não é um erro.
_IATA_BY_CITY: dict[str, str] = {
    "sao paulo": "GRU",
    "rio de janeiro": "GIG",
    "brasilia": "BSB",
    "salvador": "SSA",
    "fortaleza": "FOR",
    "recife": "REC",
    "florianopolis": "FLN",
    "porto alegre": "POA",
    "belo horizonte": "CNF",
    "curitiba": "CWB",
    "manaus": "MAO",
    "natal": "NAT",
    "belem": "BEL",
    "lisboa": "LIS",
    "porto": "OPO",
    "paris": "CDG",
    "roma": "FCO",
    "milao": "MXP",
    "madri": "MAD",
    "madrid": "MAD",
    "barcelona": "BCN",
    "londres": "LHR",
    "nova york": "JFK",
    "new york": "JFK",
    "miami": "MIA",
    "orlando": "MCO",
    "buenos aires": "EZE",
    "santiago": "SCL",
    "lima": "LIM",
    "tokyo": "NRT",
    "toquio": "NRT",
}


def iata_code_for(city: str) -> str | None:
    city_slug = _slug(city)
    for key, code in _IATA_BY_CITY.items():
        if key in city_slug:
            return code
    return None


def _slug(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().strip().lower()


def _destination_info(destination: str) -> DestinationInfo:
    destination_slug = _slug(destination)
    for key, info in _INFO_BY_DESTINATION.items():
        if key in destination_slug:
            return info
    return _DEFAULT_BRAZIL_INFO


def currency_for_destination(destination: str) -> str:
    return _destination_info(destination).currency


def is_international(destination: str, budget_currency: str = DEFAULT_DOMESTIC_CURRENCY) -> bool:
    return currency_for_destination(destination) != budget_currency


def outlet_for_destination(destination: str) -> str:
    return _destination_info(destination).outlet


_SEASON_BY_MONTH_SOUTHERN_HEMISPHERE = {
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
_SEASON_BY_MONTH_NORTHERN_HEMISPHERE = {
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

_SEASON_DESCRIPTION = {
    "verão": "dias quentes; leve roupas leves e protetor solar",
    "inverno": "temperaturas baixas; leve casacos e roupas em camadas",
    "outono": "temperaturas amenas e possibilidade de chuva; leve um casaco leve",
    "primavera": "clima ameno e variável; leve roupas em camadas",
}

_MONTH_NAME_TO_NUMBER = {
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


def season_for_month(destination: str, month_number: int | None) -> str | None:
    if month_number is None:
        return None
    hemisphere = _destination_info(destination).hemisphere
    table = (
        _SEASON_BY_MONTH_SOUTHERN_HEMISPHERE
        if hemisphere == "south"
        else _SEASON_BY_MONTH_NORTHERN_HEMISPHERE
    )
    return table.get(month_number)


def heuristic_weather_description(
    destination: str, reference_month: str | None, month_number: int | None
) -> str:
    """Estimativa heurística de clima por estação do ano — não é previsão
    meteorológica real; o checklist deixa isso explícito (RF-27)."""
    number = month_number or (_MONTH_NAME_TO_NUMBER.get(_slug(reference_month)) if reference_month else None)
    season = season_for_month(destination, number)
    period = reference_month or "o período da viagem"
    if season is None:
        return f"Não foi possível estimar a estação em {period}; consulte a previsão perto da data."
    description = _SEASON_DESCRIPTION[season]
    return (
        f"Em {period}, {destination} deve estar em {season} — {description} "
        "(estimativa por estação, não é previsão do tempo)."
    )
