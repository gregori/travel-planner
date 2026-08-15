import logging

from app.config import Settings
from app.models.plan import ExchangeRate
from app.providers.base import (
    AccommodationCriteria,
    AttractionsCriteria,
    ExchangeCriteria,
    FlightCriteria,
    RestaurantsCriteria,
    SearchResult,
)
from app.providers.circuit_breaker import CircuitBreaker
from app.providers.mock import (
    MockAccommodationProvider,
    MockAttractionsProvider,
    MockExchangeRateProvider,
    MockFlightEstimator,
    MockRestaurantsProvider,
)
from app.providers.real import BookingProvider, ExchangeRateProvider, TripadvisorProvider

logger = logging.getLogger("travel_planner.providers")


class ProviderRegistry:
    """Seleciona provedor real ou mock em runtime (RF-16, §10).

    Credencial presente e provedor saudável (circuit breaker fechado) → real.
    Caso contrário → mock, com aviso propagado para `TripPlan.warnings`.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._breaker = CircuitBreaker(failure_threshold=3, window_seconds=300.0)

        self._booking_real = BookingProvider(settings.booking_api_key) if settings.booking_api_key else None
        self._tripadvisor_real = (
            TripadvisorProvider(settings.tripadvisor_api_key) if settings.tripadvisor_api_key else None
        )
        self._exchange_real = (
            ExchangeRateProvider(settings.exchange_api_url) if settings.exchange_api_url else None
        )

        self._accommodation_mock = MockAccommodationProvider()
        self._attractions_mock = MockAttractionsProvider()
        self._restaurants_mock = MockRestaurantsProvider()
        self._flights = MockFlightEstimator()
        self._exchange_mock = MockExchangeRateProvider()

    async def search_accommodation(
        self, criteria: AccommodationCriteria, warnings: list[str]
    ) -> SearchResult:
        return await self._with_fallback(
            "booking",
            self._booking_real,
            lambda p: p.search(criteria),
            lambda: self._accommodation_mock.search(criteria),
            warnings,
        )

    async def search_attractions(self, criteria: AttractionsCriteria, warnings: list[str]) -> SearchResult:
        return await self._with_fallback(
            "tripadvisor",
            self._tripadvisor_real,
            lambda p: p.search_attractions(criteria),
            lambda: self._attractions_mock.search(criteria),
            warnings,
        )

    async def search_restaurants(self, criteria: RestaurantsCriteria, warnings: list[str]) -> SearchResult:
        return await self._with_fallback(
            "tripadvisor",
            self._tripadvisor_real,
            lambda p: p.search_restaurants(criteria),
            lambda: self._restaurants_mock.search(criteria),
            warnings,
        )

    async def estimate_flights(self, criteria: FlightCriteria, warnings: list[str]) -> SearchResult:
        # RF-12: voos são sempre "estimate" — não há modo "real" nesta camada.
        return await self._flights.estimate(criteria)

    async def get_exchange_rate(self, criteria: ExchangeCriteria, warnings: list[str]) -> ExchangeRate | None:
        result = await self._with_fallback(
            "exchange-api",
            self._exchange_real,
            lambda p: p.get_rate(criteria),
            lambda: self._exchange_mock.get_rate(criteria),
            warnings,
            single=True,
        )
        return result

    def provider_status(self) -> dict[str, str]:
        """Status para /api/health: real | unavailable | mock."""
        result: dict[str, str] = {}
        for name, real in (
            ("booking", self._booking_real),
            ("tripadvisor", self._tripadvisor_real),
            ("exchange-api", self._exchange_real),
        ):
            if real is None:
                result[name] = "mock"
            elif not self._breaker.is_available(name):
                result[name] = "unavailable"
            else:
                result[name] = "real"
        result["flights"] = "estimate"
        return result

    async def _with_fallback(
        self,
        provider_name: str,
        real_provider,
        call_real,
        call_mock,
        warnings: list[str],
        single: bool = False,
    ):
        if real_provider is not None and self._breaker.is_available(provider_name):
            try:
                result = await call_real(real_provider)
                self._breaker.record_success(provider_name)
                return result
            except Exception as exc:  # noqa: BLE001 - fallback intencional (RNF-06)
                logger.warning("provedor real '%s' falhou: %s", provider_name, exc)
                self._breaker.record_failure(provider_name)
                warnings.append(f"Provedor {provider_name} indisponível no momento; usando dados simulados.")
        elif real_provider is not None:
            warnings.append(
                f"Provedor {provider_name} temporariamente desativado (falhas recentes); "
                "usando dados simulados."
            )
        else:
            warnings.append(f"Sem credencial configurada para {provider_name}; usando dados simulados.")
        return await call_mock()
