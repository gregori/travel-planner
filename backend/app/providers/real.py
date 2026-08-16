"""Implementações reais de provedores (RNF-06: timeout 10s, 3 tentativas com
backoff exponencial + jitter por chamada).

LiteAPI (hotéis), SerpApi (voos) e Geoapify (atrações/restaurantes) são
consumidos via seus respectivos endpoints REST quando uma credencial está
configurada (LITEAPI_API_KEY / SERPAPI_API_KEY / GEOAPIFY_API_KEY). Sem
credencial, a camada de seleção (`app.providers.registry`) usa o mock
diretamente — essas classes nunca são instanciadas nesse caso (RF-16).

LiteAPI expõe endpoints de `prebook`/`book`, mas este app nunca reserva nem
paga (OUT-1 em REQUIREMENTS.md) — `LiteApiHotelsProvider` só chama `search`.
"""

from datetime import UTC, datetime
from decimal import Decimal

import httpx
from tenacity import retry, stop_after_attempt, wait_random_exponential

from app.geo import iata_code_for
from app.models.common import Source
from app.models.plan import AccommodationOption, Activity, ExchangeRate, FlightOption, MealSuggestion
from app.providers.base import (
    AccommodationCriteria,
    AttractionsCriteria,
    ExchangeCriteria,
    FlightCriteria,
    RestaurantsCriteria,
    SearchResult,
)

TIMEOUT_SECONDS = 10.0
DEFAULT_GUEST_NATIONALITY = "BR"
PLACES_SEARCH_RADIUS_METERS = 15_000

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


class LiteApiHotelsProvider:
    """Provedor de hospedagem real via LiteAPI (busca de tarifas — nunca reserva)."""

    def __init__(self, api_key: str, base_url: str = "https://api.liteapi.travel/v3.0") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    @_retry_external_call
    async def search(self, criteria: AccommodationCriteria) -> SearchResult[AccommodationOption]:
        if criteria.check_in is None or criteria.check_out is None:
            raise ValueError("LiteAPI exige check_in e check_out para buscar tarifas.")

        body = {
            "aiSearch": f"hotels in {criteria.city}",
            "checkin": criteria.check_in.isoformat(),
            "checkout": criteria.check_out.isoformat(),
            "currency": criteria.currency,
            "guestNationality": DEFAULT_GUEST_NATIONALITY,
            "occupancies": [{"rooms": 1, "adults": criteria.guests, "children": []}],
        }
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=True) as client:
            resp = await client.post(
                f"{self._base_url}/hotels/rates",
                headers={"X-API-Key": self._api_key, "Content-Type": "application/json"},
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

            cheapest_by_hotel: dict[str, tuple[Decimal, str]] = {}
            for entry in data.get("data", []):
                hotel_id = entry.get("hotelId")
                for room_type in entry.get("roomTypes", []):
                    for rate in room_type.get("rates", []):
                        totals = rate.get("retailRate", {}).get("total", [])
                        if not totals:
                            continue
                        amount = Decimal(str(totals[0]["amount"]))
                        currency = totals[0].get("currency", criteria.currency)
                        current = cheapest_by_hotel.get(hotel_id)
                        if current is None or amount < current[0]:
                            cheapest_by_hotel[hotel_id] = (amount, currency)

            # Só busca metadados (nome/endereço) dos mais baratos — evita uma
            # chamada de detalhe por hotel quando a busca de tarifas já traz
            # dezenas de resultados.
            cheapest_hotel_ids = sorted(cheapest_by_hotel, key=lambda h: cheapest_by_hotel[h][0])[:10]
            hotel_meta: dict[str, dict] = {}
            if cheapest_hotel_ids:
                meta_resp = await client.get(
                    f"{self._base_url}/data/hotels",
                    headers={"X-API-Key": self._api_key},
                    params={"hotelIds": ",".join(cheapest_hotel_ids)},
                )
                meta_resp.raise_for_status()
                hotel_meta = {h["id"]: h for h in meta_resp.json().get("data", [])}

        nights = (criteria.check_out - criteria.check_in).days or 1
        items: list[AccommodationOption] = []
        for hotel_id in cheapest_hotel_ids:
            meta = hotel_meta.get(hotel_id)
            if meta is None:
                continue
            amount, currency = cheapest_by_hotel[hotel_id]
            items.append(
                AccommodationOption(
                    name=meta["name"],
                    type="hotel",
                    price_per_night=(amount / nights).quantize(Decimal("0.01")),
                    currency=currency,
                    location=meta.get("address", meta.get("city_name", criteria.city)),
                    rating=meta.get("rating"),
                    link=None,
                    source=_real_source("liteapi", None),
                )
            )
        reason = None if items else "LiteAPI não retornou tarifas para os critérios informados."
        return SearchResult(items=items, empty_reason=reason)


class SerpApiFlightsProvider:
    """Provedor de voos real via SerpApi (engine google_flights).

    Diferente do mock (`MockFlightEstimator`), aqui o preço vem de uma busca
    ao vivo no Google Flights — por isso `Source.type="real"`, não
    `"estimate"` (decisão de produto que reabre RF-12, ver REQUIREMENTS.md).
    """

    def __init__(self, api_key: str, base_url: str = "https://serpapi.com/search") -> None:
        self._api_key = api_key
        self._base_url = base_url

    @_retry_external_call
    async def estimate(self, criteria: FlightCriteria) -> SearchResult[FlightOption]:
        if criteria.departure_date is None:
            raise ValueError("SerpApi exige departure_date para buscar voos.")
        departure_iata = iata_code_for(criteria.origin)
        arrival_iata = iata_code_for(criteria.destination)
        if departure_iata is None or arrival_iata is None:
            raise ValueError(f"Rota sem código IATA conhecido: {criteria.origin} -> {criteria.destination}")

        params = {
            "engine": "google_flights",
            "api_key": self._api_key,
            "departure_id": departure_iata,
            "arrival_id": arrival_iata,
            "outbound_date": criteria.departure_date.isoformat(),
            "type": "1" if criteria.return_date else "2",
            "adults": criteria.passengers,
            "currency": criteria.currency,
            "hl": "pt",
        }
        if criteria.return_date:
            params["return_date"] = criteria.return_date.isoformat()

        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=True) as client:
            resp = await client.get(self._base_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        itineraries = data.get("best_flights", []) + data.get("other_flights", [])
        link = (
            f"https://www.google.com/travel/flights?q=flights%20from%20{departure_iata}"
            f"%20to%20{arrival_iata}%20on%20{criteria.departure_date.isoformat()}"
        )
        source = _real_source("serpapi", link)
        options: list[FlightOption] = []
        for itinerary in itineraries:
            legs = itinerary.get("flights", [])
            if not legs or "price" not in itinerary:
                continue
            price = Decimal(str(itinerary["price"]))
            total_duration = itinerary.get("total_duration")
            options.append(
                FlightOption(
                    airline=legs[0].get("airline", "N/D"),
                    origin=criteria.origin,
                    destination=criteria.destination,
                    min_price=price,
                    max_price=price,
                    currency=criteria.currency,
                    duration_hours=round(total_duration / 60, 1) if total_duration else None,
                    stops=max(len(legs) - 1, 0),
                    link=link,
                    source=source,
                )
            )
        if len(options) >= 2:
            cheapest = min(options, key=lambda o: o.min_price)
            cheapest.recommended = True
            cheapest.rationale = "Menor preço entre as opções encontradas na busca ao vivo."
        reason = None if options else "SerpApi não retornou voos para a rota e data informadas."
        return SearchResult(items=options, empty_reason=reason)


class GeoapifyProvider:
    """Provedor de atrações e restaurantes real via Geoapify (Geocoding + Places)."""

    def __init__(self, api_key: str, base_url: str = "https://api.geoapify.com") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def _geocode_city(self, client: httpx.AsyncClient, city: str) -> tuple[float, float] | None:
        resp = await client.get(
            f"{self._base_url}/v1/geocode/search",
            params={"text": city, "type": "city", "format": "json", "apiKey": self._api_key},
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None
        return results[0]["lon"], results[0]["lat"]

    async def _search_places(
        self, client: httpx.AsyncClient, lon: float, lat: float, categories: str
    ) -> list[dict]:
        resp = await client.get(
            f"{self._base_url}/v2/places",
            params={
                "categories": categories,
                "filter": f"circle:{lon},{lat},{PLACES_SEARCH_RADIUS_METERS}",
                "bias": f"proximity:{lon},{lat}",
                "limit": 20,
                "lang": "pt",
                "apiKey": self._api_key,
            },
        )
        resp.raise_for_status()
        return resp.json().get("features", [])

    @_retry_external_call
    async def search_attractions(self, criteria: AttractionsCriteria) -> SearchResult[Activity]:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=True) as client:
            point = await self._geocode_city(client, criteria.city)
            if point is None:
                return SearchResult(empty_reason=f"Geoapify não localizou o destino '{criteria.city}'.")
            features = await self._search_places(client, *point, "tourism.attraction,tourism.sights")

        items = [
            Activity(
                title=f["properties"]["name"],
                description=f["properties"].get("formatted"),
                region=f["properties"].get("city", criteria.city),
                source=None,
            )
            for f in features
            if f["properties"].get("name")
        ]
        reason = None if items else "Geoapify não retornou atrações para o destino informado."
        return SearchResult(items=items, empty_reason=reason)

    @_retry_external_call
    async def search_restaurants(self, criteria: RestaurantsCriteria) -> SearchResult[MealSuggestion]:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=True) as client:
            point = await self._geocode_city(client, criteria.city)
            if point is None:
                return SearchResult(empty_reason=f"Geoapify não localizou o destino '{criteria.city}'.")
            features = await self._search_places(client, *point, "catering.restaurant")

        items = [
            MealSuggestion(
                name=f["properties"]["name"],
                meal_type="almoço/jantar",
                cuisine=None,
                location=f["properties"].get("formatted", criteria.city),
                link=f["properties"].get("website"),
                compatibility="Compatibilidade não verificada automaticamente; confirme no local.",
                source=_real_source("geoapify", f["properties"].get("website"), confidence="medium"),
            )
            for f in features
            if f["properties"].get("name")
        ]
        reason = None if items else "Geoapify não retornou restaurantes para o destino informado."
        return SearchResult(items=items, empty_reason=reason)


class ExchangeRateProvider:
    """Cotação de câmbio real via API pública configurável (ex.: frankfurter.dev)."""

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
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=True) as client:
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
