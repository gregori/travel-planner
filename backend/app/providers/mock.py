import json
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.geo import currency_for_destination
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

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return normalized.strip().lower()


def _load(file_name: str) -> dict:
    with open(FIXTURES_DIR / file_name, encoding="utf-8") as f:
        return json.load(f)


def _mock_source(note: str | None = None) -> Source:
    return Source(
        type="mock",
        provider="fixture",
        url=None,
        retrieved_at=datetime.now(UTC),
        confidence="low",
        note=note or "Dado simulado — sem credencial de provedor real configurada.",
    )


class MockAccommodationProvider:
    def __init__(self) -> None:
        self._data = _load("accommodation.json")

    async def search(self, criteria: AccommodationCriteria) -> SearchResult[AccommodationOption]:
        city_slug = _slug(criteria.city)
        records = self._data.get(city_slug)
        if not records:
            records = self._generic_fallback(criteria.city)
        items = [
            AccommodationOption(
                name=r["name"],
                type=r["type"],
                price_per_night=Decimal(str(r["price_per_night"])),
                currency=r["currency"],
                location=r["location"],
                rating=r.get("rating"),
                link=r.get("link"),
                source=_mock_source(),
            )
            for r in records
        ]
        return SearchResult(items=items)

    @staticmethod
    def _generic_fallback(city: str) -> list[dict]:
        return [
            {
                "name": f"Hotel Central {city}",
                "type": "hotel",
                "price_per_night": 350,
                "currency": "BRL",
                "location": f"Centro, {city}",
                "rating": 4.1,
                "link": None,
            },
            {
                "name": f"Pousada {city}",
                "type": "pousada",
                "price_per_night": 220,
                "currency": "BRL",
                "location": f"Região central, {city}",
                "rating": 4.0,
                "link": None,
            },
            {
                "name": f"{city} Suites Turísticas",
                "type": "apart-hotel",
                "price_per_night": 290,
                "currency": "BRL",
                "location": f"Zona turística, {city}",
                "rating": 4.2,
                "link": None,
            },
        ]


class MockAttractionsProvider:
    def __init__(self) -> None:
        self._data = _load("attractions.json")

    async def search(self, criteria: AttractionsCriteria) -> SearchResult[Activity]:
        city_slug = _slug(criteria.city)
        records = self._data.get(city_slug)
        if not records:
            records = self._generic_fallback(criteria.city)
        interests = {i.lower() for i in criteria.interests}
        if interests:
            filtered = [
                r for r in records if interests.intersection({i.lower() for i in r.get("interests", [])})
            ]
            records = filtered or records
        currency = currency_for_destination(criteria.city)
        items = [
            Activity(
                title=r["title"],
                description=r.get("description"),
                region=r.get("region"),
                duration_min=r.get("duration_min"),
                estimated_cost=Decimal(str(r.get("estimated_cost", 0))),
                currency=currency,
                source=_mock_source() if r.get("estimated_cost", 0) else None,
            )
            for r in records
        ]
        return SearchResult(items=items)

    @staticmethod
    def _generic_fallback(city: str) -> list[dict]:
        return [
            {
                "title": f"City tour por {city}",
                "description": "Passeio guiado pelos principais pontos da cidade.",
                "region": "Centro",
                "duration_min": 120,
                "estimated_cost": 30,
                "interests": ["cultural"],
            },
            {
                "title": f"Museu principal de {city}",
                "description": "Acervo histórico e cultural local.",
                "region": "Centro",
                "duration_min": 90,
                "estimated_cost": 15,
                "interests": ["cultural"],
            },
            {
                "title": f"Mirante de {city}",
                "description": "Vista panorâmica, boa opção de tarde livre.",
                "region": "Centro",
                "duration_min": 60,
                "estimated_cost": 0,
                "interests": ["natureza", "familia"],
            },
        ]


class MockRestaurantsProvider:
    def __init__(self) -> None:
        self._data = _load("restaurants.json")

    async def search(self, criteria: RestaurantsCriteria) -> SearchResult[MealSuggestion]:
        city_slug = _slug(criteria.city)
        records = self._data.get(city_slug)
        if not records:
            records = self._generic_fallback(criteria.city)

        normalized_restrictions = {_slug(r) for r in criteria.restrictions}
        items: list[MealSuggestion] = []
        for r in records:
            covered = {_slug(a) for a in r.get("restrictions_covered", [])}
            if normalized_restrictions and not normalized_restrictions.issubset(covered):
                continue
            if normalized_restrictions:
                compatibility = f"Atende: {', '.join(sorted(criteria.restrictions))}."
            else:
                compatibility = "Sem restrições alimentares informadas para verificar."
            items.append(
                MealSuggestion(
                    name=r["name"],
                    meal_type=r["meal_type"],
                    cuisine=r.get("cuisine"),
                    price_range=r.get("price_range"),
                    compatibility=compatibility,
                    location=r.get("location"),
                    link=r.get("link"),
                    source=_mock_source(),
                )
            )

        empty_reason = None
        if not items and normalized_restrictions:
            empty_reason = (
                f"Nenhum restaurante mockado para {criteria.city} atende a todas as "
                f"restrições: {', '.join(criteria.restrictions)}."
            )
        return SearchResult(items=items, empty_reason=empty_reason)

    @staticmethod
    def _generic_fallback(city: str) -> list[dict]:
        return [
            {
                "name": f"Restaurante Central de {city}",
                "meal_type": "almoço/jantar",
                "cuisine": "regional",
                "price_range": "€€",
                "restrictions_covered": ["vegetariano"],
                "location": f"Centro, {city}",
            },
            {
                "name": f"Casa {city}",
                "meal_type": "jantar",
                "cuisine": "contemporânea",
                "price_range": "€€€",
                "restrictions_covered": [],
                "location": f"Zona nobre, {city}",
            },
        ]


class MockFlightEstimator:
    """Estimador de voos. RF-12: preço de voo é **sempre** uma faixa rotulada
    ``estimate`` — nunca ``real``, mesmo quando a busca web está disponível,
    pois não há API de precificação de passagens com garantia de exatidão."""

    def __init__(self) -> None:
        self._data = _load("flights.json")

    async def estimate(self, criteria: FlightCriteria) -> SearchResult[FlightOption]:
        key = f"{_slug(criteria.origin)}-{_slug(criteria.destination)}"
        record = self._data.get(key) or self._data["_default"]
        source = Source(
            type="estimate",
            provider="web",
            url=None,
            retrieved_at=datetime.now(UTC),
            confidence="medium" if key in self._data else "low",
            note="Estimativa por pesquisa web/histórico de rota; faixa, não valor fechado.",
        )
        base_min_price = Decimal(str(record["min_price"]))
        base_max_price = Decimal(str(record["max_price"]))
        options = []
        for index, airline in enumerate(record["airlines"]):
            # Variação determinística por companhia (evita preços idênticos
            # entre opções, mantendo o resultado reproduzível para testes).
            factor = Decimal("1.0") + Decimal(index) * Decimal("0.04")
            options.append(
                FlightOption(
                    airline=airline,
                    origin=criteria.origin,
                    destination=criteria.destination,
                    min_price=(base_min_price * factor).quantize(Decimal("0.01")),
                    max_price=(base_max_price * factor).quantize(Decimal("0.01")),
                    currency=record["currency"],
                    duration_hours=record.get("duration_hours"),
                    stops=record.get("stops", 0) + (0 if index == 0 else index - 1),
                    link=f"https://www.google.com/travel/flights?q={_slug(airline)}+{_slug(criteria.origin)}+{_slug(criteria.destination)}",
                    source=source,
                )
            )
        if len(options) >= 2:
            cheapest = min(options, key=lambda o: o.min_price)
            cheapest.recommended = True
            cheapest.rationale = "Menor preço médio na rota estimada."
        return SearchResult(items=options)


class MockExchangeRateProvider:
    def __init__(self) -> None:
        self._data = _load("exchange_rates.json")

    async def get_rate(self, criteria: ExchangeCriteria) -> ExchangeRate | None:
        if criteria.source_currency == criteria.target_currency:
            rate = Decimal("1.0")
        else:
            key = f"{criteria.source_currency}-{criteria.target_currency}"
            raw_rate = self._data.get(key)
            if raw_rate is None:
                return None
            rate = Decimal(str(raw_rate))
        return ExchangeRate(
            source_currency=criteria.source_currency,
            target_currency=criteria.target_currency,
            rate=rate,
            source=_mock_source("Taxa mock — não usar para conversão financeira real."),
        )
