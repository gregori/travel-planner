from datetime import UTC, datetime
from datetime import date as _date
from datetime import time as _time
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.brief import TripBrief
from app.models.common import Source


class Activity(BaseModel):
    title: str
    description: str | None = None
    region: str | None = None
    duration_min: int | None = None
    estimated_cost: Decimal = Decimal("0")
    currency: str = "BRL"
    source: Source | None = None
    time_of_day: _time | None = None

    @model_validator(mode="after")
    def _cost_requires_source(self) -> "Activity":
        """RF-15/RNF-01: todo item com custo > 0 precisa referenciar uma Source."""
        if self.estimated_cost > 0 and self.source is None:
            raise ValueError(f"Activity '{self.title}' tem custo > 0 mas nenhuma Source")
        return self


class Transfer(BaseModel):
    from_block: str
    to_block: str
    duration_min: int
    mode: str = "a pé/transporte local"


class ItineraryDay(BaseModel):
    day: int
    date: _date | None = None
    region: str
    morning: list[Activity] = Field(default_factory=list)
    afternoon: list[Activity] = Field(default_factory=list)
    evening: list[Activity] = Field(default_factory=list)
    transfers: list[Transfer] = Field(default_factory=list)
    estimated_day_cost: Decimal = Decimal("0")
    note: str | None = None


class FlightOption(BaseModel):
    airline: str
    origin: str
    destination: str
    min_price: Decimal
    max_price: Decimal
    currency: str
    duration_hours: float | None = None
    stops: int = 0
    link: str | None = None
    recommended: bool = False
    rationale: str | None = None
    source: Source


class AccommodationOption(BaseModel):
    name: str
    type: str = "hotel"
    price_per_night: Decimal
    currency: str
    location: str
    rating: float | None = None
    link: str | None = None
    recommended: bool = False
    rationale: str | None = None
    source: Source


class MealSuggestion(BaseModel):
    name: str
    meal_type: str
    cuisine: str | None = None
    price_range: str | None = None
    compatibility: str
    location: str | None = None
    link: str | None = None
    source: Source


class Budget(BaseModel):
    flights: Decimal = Decimal("0")
    accommodation: Decimal = Decimal("0")
    food: Decimal = Decimal("0")
    activities: Decimal = Decimal("0")
    local_transport: Decimal = Decimal("0")
    contingency: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    stated_cap: Decimal | None = None
    difference: Decimal | None = None
    within_cap: bool = True
    alerts: list[str] = Field(default_factory=list)
    # RF-15/§7.3: categorias heurísticas (ex.: alimentação, transporte local)
    # não vêm de um item individual com Source própria — a proveniência da
    # estimativa é declarada aqui para que nenhum valor fique sem origem.
    sources: list[Source] = Field(default_factory=list)

    @model_validator(mode="after")
    def _compute_total_and_difference(self) -> "Budget":
        total = (
            self.flights
            + self.accommodation
            + self.food
            + self.activities
            + self.local_transport
            + self.contingency
        )
        self.total = total
        if self.stated_cap is not None:
            self.difference = total - self.stated_cap
            self.within_cap = self.difference <= 0
        return self

    @model_validator(mode="after")
    def _priced_categories_require_source(self) -> "Budget":
        """RF-15/RNF-01: nenhuma categoria com valor > 0 pode ficar sem
        proveniência declarada. Voos/hospedagem/passeios já carregam Source
        nos itens de origem (validado em Activity/FlightOption/
        AccommodationOption); alimentação e transporte local são heurísticas
        e precisam de uma Source própria em `sources`."""
        if (self.food > 0 or self.local_transport > 0) and not self.sources:
            raise ValueError("Budget com food/local_transport > 0 precisa de ao menos uma Source")
        return self


class ExchangeRate(BaseModel):
    source_currency: str
    target_currency: str
    rate: Decimal
    source: Source


class Checklist(BaseModel):
    documents: list[str] = Field(default_factory=list)
    weather: str | None = None
    currency_and_exchange: str | None = None
    power_outlet: str | None = None
    what_to_pack: list[str] = Field(default_factory=list)
    entry_requirements: list[str] = Field(default_factory=list)


class TripPlan(BaseModel):
    brief: TripBrief
    summary: str
    flight_options: list[FlightOption] = Field(default_factory=list)
    accommodation_options: list[AccommodationOption] = Field(default_factory=list)
    itinerary: list[ItineraryDay] = Field(default_factory=list)
    meals: list[MealSuggestion] = Field(default_factory=list)
    budget: Budget
    exchange_rate: ExchangeRate | None = None
    checklist: Checklist = Field(default_factory=Checklist)
    sources: list[Source] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
