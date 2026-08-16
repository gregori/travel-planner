import pytest

from app.config import Settings
from app.providers.base import AccommodationCriteria
from app.providers.registry import ProviderRegistry


@pytest.mark.asyncio
async def test_sem_credencial_usa_mock_e_avisa(settings: Settings):
    registry = ProviderRegistry(settings)
    warnings: list[str] = []
    result = await registry.search_accommodation(
        AccommodationCriteria(city="Lisboa", check_in=None, check_out=None, guests=2), warnings
    )
    assert len(result.items) >= 3
    assert any("credencial" in w for w in warnings)
    assert registry.provider_status()["liteapi"] == "mock"


@pytest.mark.asyncio
async def test_criterios_insuficientes_nao_aciona_circuit_breaker(settings: Settings):
    settings_with_credential = settings.model_copy(update={"liteapi_api_key": "chave-fake"})
    registry = ProviderRegistry(settings_with_credential)

    class RequiresDatesProvider:
        async def search(self, criteria):
            if criteria.check_in is None or criteria.check_out is None:
                raise ValueError("LiteAPI exige check_in e check_out para buscar tarifas.")
            raise AssertionError("não deveria ser chamado com datas neste teste")

    registry._liteapi_real = RequiresDatesProvider()

    warnings: list[str] = []
    result = await registry.search_accommodation(
        AccommodationCriteria(city="Cidade do México", check_in=None, check_out=None, guests=4), warnings
    )
    assert len(result.items) >= 3
    assert any("insuficientes" in w for w in warnings)
    assert not any("indisponível" in w for w in warnings)
    # datas ausentes não são uma falha do provedor — circuit breaker deve seguir fechado
    assert registry.provider_status()["liteapi"] == "real"


@pytest.mark.asyncio
async def test_provedor_real_falhando_aciona_circuit_breaker_e_fallback(settings: Settings):
    settings_with_credential = settings.model_copy(update={"liteapi_api_key": "chave-fake"})
    registry = ProviderRegistry(settings_with_credential)

    class AlwaysFailingProvider:
        async def search(self, criteria):
            raise TimeoutError("timeout simulado")

    registry._liteapi_real = AlwaysFailingProvider()

    for _ in range(3):
        warnings: list[str] = []
        result = await registry.search_accommodation(
            AccommodationCriteria(city="Lisboa", check_in=None, check_out=None, guests=2), warnings
        )
        assert len(result.items) >= 3  # degrada para mock, requisição nunca falha (RNF-06)
        assert any("indisponível" in w or "credencial" in w for w in warnings)

    # após 3 falhas consecutivas, o circuit breaker deve estar aberto
    assert registry.provider_status()["liteapi"] == "unavailable"

    final_warnings: list[str] = []
    result = await registry.search_accommodation(
        AccommodationCriteria(city="Lisboa", check_in=None, check_out=None, guests=2), final_warnings
    )
    assert len(result.items) >= 3
    assert any("temporariamente desativado" in w for w in final_warnings)
