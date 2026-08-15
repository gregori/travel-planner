import unicodedata

# Heurística leve para MVP pt-BR: mapeia destinos conhecidos para a moeda local.
# Não é uma fonte geográfica oficial — usada apenas para decidir se cabe cotação
# de câmbio (RF-13) e alerta de documentação de entrada (RF-28).
_MOEDA_POR_DESTINO = {
    "lisboa": "EUR",
    "portugal": "EUR",
    "porto": "EUR",
    "paris": "EUR",
    "franca": "EUR",
    "france": "EUR",
    "roma": "EUR",
    "italia": "EUR",
    "madri": "EUR",
    "madrid": "EUR",
    "espanha": "EUR",
    "londres": "GBP",
    "reino unido": "GBP",
    "nova york": "USD",
    "new york": "USD",
    "eua": "USD",
    "estados unidos": "USD",
    "miami": "USD",
    "orlando": "USD",
    "buenos aires": "ARS",
    "argentina": "ARS",
    "santiago": "CLP",
    "chile": "CLP",
    "lima": "PEN",
    "peru": "PEN",
    "tokyo": "JPY",
    "toquio": "JPY",
    "japao": "JPY",
}

MOEDA_PADRAO_NACIONAL = "BRL"


def _slug(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().strip().lower()


def moeda_do_destino(destino: str) -> str:
    destino_slug = _slug(destino)
    for chave, moeda in _MOEDA_POR_DESTINO.items():
        if chave in destino_slug:
            return moeda
    return MOEDA_PADRAO_NACIONAL


def eh_internacional(destino: str, moeda_orcamento: str = MOEDA_PADRAO_NACIONAL) -> bool:
    return moeda_do_destino(destino) != moeda_orcamento
