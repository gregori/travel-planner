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

from app.models.common import Source
from app.models.plan import AccommodationOption, Activity, ExchangeRate, MealSuggestion
from app.providers.base import (
    AccommodationCriteria,
    AttractionsCriteria,
    ExchangeCriteria,
    RestaurantsCriteria,
    SearchResult,
)

TIMEOUT_SECONDS = 10.0

_retry_external_call = retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=8),
    reraise=True,
)


def _real_source(provider: str, url: str | None, confidence: str = "high") -> Source:
    return Source(
        type="real",
        provider=provider,
        url=url,
        retrieved_at=datetime.now(UTC),
        confidence=confidence,  # type: ignore[arg-type]
        note=None,
    )


class BookingProvider:
    """Provedor de hospedagem real via API do Booking.com."""

    def __init__(self, api_key: str, base_url: str = "https://distribution-xml.booking.com/json") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    @_retry_external_call
    async def search(self, criteria: AccommodationCriteria) -> SearchResult[AccommodationOption]:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.get(
                f"{self._base_url}/hotels",
                headers={"Authorization": f"Bearer {self._api_key}"},
                params={
                    "city": criteria.city,
                    "checkin": criteria.check_in.isoformat() if criteria.check_in else None,
                    "checkout": criteria.check_out.isoformat() if criteria.check_out else None,
                    "guests": criteria.guests,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        items = [
            AccommodationOption(
                name=h["name"],
                type=h.get("type", "hotel"),
                price_per_night=Decimal(str(h["price_per_night"])),
                currency=h.get("currency", criteria.currency),
                location=h.get("location", criteria.city),
                rating=h.get("rating"),
                link=h.get("url"),
                source=_real_source("booking", h.get("url")),
            )
            for h in data.get("hotels", [])
        ]
        reason = None if items else "Booking.com não retornou opções para os critérios informados."
        return SearchResult(items=items, empty_reason=reason)


class TripadvisorProvider:
    """Provedor de atrações e restaurantes real via API do Tripadvisor."""

    def __init__(self, api_key: str, base_url: str = "https://api.content.tripadvisor.com/api/v1") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    @_retry_external_call
    async def search_attractions(self, criteria: AttractionsCriteria) -> SearchResult[Activity]:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.get(
                f"{self._base_url}/location/search",
                headers={"accept": "application/json"},
                params={
                    "key": self._api_key,
                    "searchQuery": criteria.city,
                    "category": "attractions",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        items = [
            Activity(
                title=loc["name"],
                description=loc.get("description"),
                region=loc.get("address_obj", {}).get("city", criteria.city),
                source=_real_source("tripadvisor", loc.get("web_url")),
            )
            for loc in data.get("data", [])
        ]
        reason = None if items else "Tripadvisor não retornou atrações para o destino informado."
        return SearchResult(items=items, empty_reason=reason)

    @_retry_external_call
    async def search_restaurants(self, criteria: RestaurantsCriteria) -> SearchResult[MealSuggestion]:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.get(
                f"{self._base_url}/location/search",
                headers={"accept": "application/json"},
                params={
                    "key": self._api_key,
                    "searchQuery": criteria.city,
                    "category": "restaurants",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        items = [
            MealSuggestion(
                name=loc["name"],
                meal_type="almoço/jantar",
                cuisine=loc.get("cuisine"),
                location=loc.get("address_obj", {}).get("city", criteria.city),
                link=loc.get("web_url"),
                compatibility="Compatibilidade não verificada automaticamente; confirme no local.",
                source=_real_source("tripadvisor", loc.get("web_url"), confidence="medium"),
            )
            for loc in data.get("data", [])
        ]
        reason = None if items else "Tripadvisor não retornou restaurantes para o destino informado."
        return SearchResult(items=items, empty_reason=reason)


class ExchangeRateProvider:
    """Cotação de câmbio real via API pública configurável (ex.: frankfurter.app)."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    @_retry_external_call
    async def get_rate(self, criteria: ExchangeCriteria) -> ExchangeRate | None:
        if criteria.source_currency == criteria.target_currency:
            return ExchangeRate(
                source_currency=criteria.source_currency,
                target_currency=criteria.target_currency,
                rate=Decimal("1.0"),
                source=_real_source("exchange-api", self._base_url),
            )
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.get(
                f"{self._base_url}/latest",
                params={"from": criteria.source_currency, "to": criteria.target_currency},
            )
            resp.raise_for_status()
            data = resp.json()

        rate = data.get("rates", {}).get(criteria.target_currency)
        if rate is None:
            return None
        return ExchangeRate(
            source_currency=criteria.source_currency,
            target_currency=criteria.target_currency,
            rate=Decimal(str(rate)),
            source=_real_source("exchange-api", self._base_url),
        )
