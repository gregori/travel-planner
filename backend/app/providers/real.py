"""Implementações reais de provedores (RNF-06: timeout 10s, 3 tentativas com
backoff exponencial + jitter por chamada).

Booking.com e Tripadvisor são consumidos via seus respectivos endpoints REST
quando uma credencial está configurada (BOOKING_API_KEY / TRIPADVISOR_API_KEY).
Sem credencial, a camada de seleção (`app.providers.registry`) usa o mock
diretamente — essas classes nunca são instanciadas nesse caso (RF-16).
"""

from datetime import UTC, datetime
from decimal import Decimal

import httpx
from tenacity import retry, stop_after_attempt, wait_random_exponential

from app.models.common import Fonte
from app.models.plan import Atividade, CotacaoCambio, OpcaoHospedagem, SugestaoRefeicao
from app.providers.base import (
    CriteriosAtracoes,
    CriteriosCambio,
    CriteriosHospedagem,
    CriteriosRestaurantes,
    ResultadoBusca,
)

TIMEOUT_SEGUNDOS = 10.0

_retry_chamada_externa = retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=8),
    reraise=True,
)


def _fonte_real(provedor: str, url: str | None, confianca: str = "alta") -> Fonte:
    return Fonte(
        tipo="real",
        provedor=provedor,
        url=url,
        consultado_em=datetime.now(UTC),
        confianca=confianca,  # type: ignore[arg-type]
        observacao=None,
    )


class BookingProvider:
    """Provedor de hospedagem real via API do Booking.com."""

    def __init__(self, api_key: str, base_url: str = "https://distribution-xml.booking.com/json") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    @_retry_chamada_externa
    async def buscar(self, criterios: CriteriosHospedagem) -> ResultadoBusca[OpcaoHospedagem]:
        async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
            resp = await client.get(
                f"{self._base_url}/hotels",
                headers={"Authorization": f"Bearer {self._api_key}"},
                params={
                    "city": criterios.cidade,
                    "checkin": criterios.check_in.isoformat() if criterios.check_in else None,
                    "checkout": criterios.check_out.isoformat() if criterios.check_out else None,
                    "guests": criterios.hospedes,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        itens = [
            OpcaoHospedagem(
                nome=h["name"],
                tipo=h.get("type", "hotel"),
                preco_por_noite=Decimal(str(h["price_per_night"])),
                moeda=h.get("currency", criterios.moeda),
                localizacao=h.get("location", criterios.cidade),
                avaliacao=h.get("rating"),
                link=h.get("url"),
                fonte=_fonte_real("booking", h.get("url")),
            )
            for h in data.get("hotels", [])
        ]
        motivo = None if itens else "Booking.com não retornou opções para os critérios informados."
        return ResultadoBusca(itens=itens, motivo_vazio=motivo)


class TripadvisorProvider:
    """Provedor de atrações e restaurantes real via API do Tripadvisor."""

    def __init__(self, api_key: str, base_url: str = "https://api.content.tripadvisor.com/api/v1") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    @_retry_chamada_externa
    async def buscar_atracoes(self, criterios: CriteriosAtracoes) -> ResultadoBusca[Atividade]:
        async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
            resp = await client.get(
                f"{self._base_url}/location/search",
                headers={"accept": "application/json"},
                params={
                    "key": self._api_key,
                    "searchQuery": criterios.cidade,
                    "category": "attractions",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        itens = [
            Atividade(
                titulo=loc["name"],
                descricao=loc.get("description"),
                regiao=loc.get("address_obj", {}).get("city", criterios.cidade),
                fonte=_fonte_real("tripadvisor", loc.get("web_url")),
            )
            for loc in data.get("data", [])
        ]
        motivo = None if itens else "Tripadvisor não retornou atrações para o destino informado."
        return ResultadoBusca(itens=itens, motivo_vazio=motivo)

    @_retry_chamada_externa
    async def buscar_restaurantes(self, criterios: CriteriosRestaurantes) -> ResultadoBusca[SugestaoRefeicao]:
        async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
            resp = await client.get(
                f"{self._base_url}/location/search",
                headers={"accept": "application/json"},
                params={
                    "key": self._api_key,
                    "searchQuery": criterios.cidade,
                    "category": "restaurants",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        itens = [
            SugestaoRefeicao(
                nome=loc["name"],
                tipo_refeicao="almoço/jantar",
                culinaria=loc.get("cuisine"),
                localizacao=loc.get("address_obj", {}).get("city", criterios.cidade),
                link=loc.get("web_url"),
                compatibilidade="Compatibilidade não verificada automaticamente; confirme no local.",
                fonte=_fonte_real("tripadvisor", loc.get("web_url"), confianca="media"),
            )
            for loc in data.get("data", [])
        ]
        motivo = None if itens else "Tripadvisor não retornou restaurantes para o destino informado."
        return ResultadoBusca(itens=itens, motivo_vazio=motivo)


class ExchangeRateProvider:
    """Cotação de câmbio real via API pública configurável (ex.: frankfurter.app)."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    @_retry_chamada_externa
    async def cotar(self, criterios: CriteriosCambio) -> CotacaoCambio | None:
        if criterios.moeda_origem == criterios.moeda_destino:
            return CotacaoCambio(
                moeda_origem=criterios.moeda_origem,
                moeda_destino=criterios.moeda_destino,
                taxa=Decimal("1.0"),
                fonte=_fonte_real("exchange-api", self._base_url),
            )
        async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
            resp = await client.get(
                f"{self._base_url}/latest",
                params={"from": criterios.moeda_origem, "to": criterios.moeda_destino},
            )
            resp.raise_for_status()
            data = resp.json()

        taxa = data.get("rates", {}).get(criterios.moeda_destino)
        if taxa is None:
            return None
        return CotacaoCambio(
            moeda_origem=criterios.moeda_origem,
            moeda_destino=criterios.moeda_destino,
            taxa=Decimal(str(taxa)),
            fonte=_fonte_real("exchange-api", self._base_url),
        )
