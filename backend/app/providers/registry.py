import logging

from app.config import Settings
from app.models.plan import CotacaoCambio
from app.providers.base import (
    CriteriosAtracoes,
    CriteriosCambio,
    CriteriosHospedagem,
    CriteriosRestaurantes,
    CriteriosVoo,
    ResultadoBusca,
)
from app.providers.circuit_breaker import CircuitBreaker
from app.providers.mock import (
    ExchangeRateProviderMock,
    MockAtracoesProvider,
    MockHospedagemProvider,
    MockRestaurantesProvider,
    WebFlightEstimatorMock,
)
from app.providers.real import BookingProvider, ExchangeRateProvider, TripadvisorProvider

logger = logging.getLogger("travel_planner.providers")


class ProviderRegistry:
    """Seleciona provedor real ou mock em runtime (RF-16, §10).

    Credencial presente e provedor saudável (circuit breaker fechado) → real.
    Caso contrário → mock, com aviso propagado para `TripPlan.avisos`.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._breaker = CircuitBreaker(limite_falhas=3, janela_segundos=300.0)

        self._booking_real = BookingProvider(settings.booking_api_key) if settings.booking_api_key else None
        self._tripadvisor_real = (
            TripadvisorProvider(settings.tripadvisor_api_key) if settings.tripadvisor_api_key else None
        )
        self._exchange_real = (
            ExchangeRateProvider(settings.exchange_api_url) if settings.exchange_api_url else None
        )

        self._hospedagem_mock = MockHospedagemProvider()
        self._atracoes_mock = MockAtracoesProvider()
        self._restaurantes_mock = MockRestaurantesProvider()
        self._voos = WebFlightEstimatorMock()
        self._cambio_mock = ExchangeRateProviderMock()

    async def buscar_hospedagem(self, criterios: CriteriosHospedagem, avisos: list[str]) -> ResultadoBusca:
        return await self._com_fallback(
            "booking",
            self._booking_real,
            lambda p: p.buscar(criterios),
            lambda: self._hospedagem_mock.buscar(criterios),
            avisos,
        )

    async def buscar_atracoes(self, criterios: CriteriosAtracoes, avisos: list[str]) -> ResultadoBusca:
        return await self._com_fallback(
            "tripadvisor",
            self._tripadvisor_real,
            lambda p: p.buscar_atracoes(criterios),
            lambda: self._atracoes_mock.buscar(criterios),
            avisos,
        )

    async def buscar_restaurantes(
        self, criterios: CriteriosRestaurantes, avisos: list[str]
    ) -> ResultadoBusca:
        return await self._com_fallback(
            "tripadvisor",
            self._tripadvisor_real,
            lambda p: p.buscar_restaurantes(criterios),
            lambda: self._restaurantes_mock.buscar(criterios),
            avisos,
        )

    async def estimar_voos(self, criterios: CriteriosVoo, avisos: list[str]) -> ResultadoBusca:
        # RF-12: voos são sempre "estimativa" — não há modo "real" nesta camada.
        return await self._voos.estimar(criterios)

    async def cotar_cambio(self, criterios: CriteriosCambio, avisos: list[str]) -> CotacaoCambio | None:
        resultado = await self._com_fallback(
            "exchange-api",
            self._exchange_real,
            lambda p: p.cotar(criterios),
            lambda: self._cambio_mock.cotar(criterios),
            avisos,
            singular=True,
        )
        return resultado

    def status_provedores(self) -> dict[str, str]:
        """Status para /api/health: real | degradado | indisponivel | mock."""
        resultado: dict[str, str] = {}
        for nome, real in (
            ("booking", self._booking_real),
            ("tripadvisor", self._tripadvisor_real),
            ("exchange-api", self._exchange_real),
        ):
            if real is None:
                resultado[nome] = "mock"
            elif not self._breaker.disponivel(nome):
                resultado[nome] = "indisponivel"
            else:
                resultado[nome] = "real"
        resultado["voos"] = "estimativa"
        return resultado

    async def _com_fallback(
        self,
        nome_provedor: str,
        provedor_real,
        chamar_real,
        chamar_mock,
        avisos: list[str],
        singular: bool = False,
    ):
        if provedor_real is not None and self._breaker.disponivel(nome_provedor):
            try:
                resultado = await chamar_real(provedor_real)
                self._breaker.registrar_sucesso(nome_provedor)
                return resultado
            except Exception as exc:  # noqa: BLE001 - fallback intencional (RNF-06)
                logger.warning("provedor real '%s' falhou: %s", nome_provedor, exc)
                self._breaker.registrar_falha(nome_provedor)
                avisos.append(f"Provedor {nome_provedor} indisponível no momento; usando dados simulados.")
        elif provedor_real is not None:
            avisos.append(
                f"Provedor {nome_provedor} temporariamente desativado (falhas recentes); "
                "usando dados simulados."
            )
        else:
            avisos.append(f"Sem credencial configurada para {nome_provedor}; usando dados simulados.")
        return await chamar_mock()
