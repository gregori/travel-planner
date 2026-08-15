from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Generic, Protocol, TypeVar

from app.models.plan import AccommodationOption, Activity, ExchangeRate, FlightOption, MealSuggestion

T = TypeVar("T")


@dataclass
class SearchResult(Generic[T]):
    """Envelope de resultado de um provedor.

    Se `items` vier vazio, `empty_reason` explica por quê (RNF-02: nunca
    inventar dados — o agente deve declarar a lacuna, não preencher com
    plausibilidade).
    """

    items: list[T] = field(default_factory=list)
    degraded: bool = False
    empty_reason: str | None = None


@dataclass
class AccommodationCriteria:
    city: str
    check_in: date | None
    check_out: date | None
    guests: int
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    currency: str = "BRL"


@dataclass
class AttractionsCriteria:
    city: str
    interests: list[str] = field(default_factory=list)
    profile: str = "geral"


@dataclass
class RestaurantsCriteria:
    city: str
    restrictions: list[str] = field(default_factory=list)
    price_range: str | None = None


@dataclass
class FlightCriteria:
    origin: str
    destination: str
    departure_date: date | None
    return_date: date | None
    passengers: int
    currency: str = "BRL"


@dataclass
class ExchangeCriteria:
    source_currency: str
    target_currency: str


class AccommodationProvider(Protocol):
    async def search(self, criteria: AccommodationCriteria) -> SearchResult[AccommodationOption]: ...


class AttractionsProvider(Protocol):
    async def search(self, criteria: AttractionsCriteria) -> SearchResult[Activity]: ...


class RestaurantsProvider(Protocol):
    async def search(self, criteria: RestaurantsCriteria) -> SearchResult[MealSuggestion]: ...


class FlightsProvider(Protocol):
    async def estimate(self, criteria: FlightCriteria) -> SearchResult[FlightOption]: ...


class ExchangeRateProviderProtocol(Protocol):
    async def get_rate(self, criteria: ExchangeCriteria) -> ExchangeRate | None: ...
