import pytest

from app.providers.base import (
    AccommodationCriteria,
    AttractionsCriteria,
    ExchangeCriteria,
    FlightCriteria,
    RestaurantsCriteria,
)
from app.providers.mock import (
    MockAccommodationProvider,
    MockAttractionsProvider,
    MockExchangeRateProvider,
    MockFlightEstimator,
    MockRestaurantsProvider,
)


@pytest.mark.asyncio
async def test_hospedagem_mock_retorna_ao_menos_tres_opcoes_com_fonte():
    provider = MockAccommodationProvider()
    result = await provider.search(
        AccommodationCriteria(city="Lisboa", check_in=None, check_out=None, guests=3)
    )
    assert len(result.items) >= 3
    for option in result.items:
        assert option.source.type == "mock"
        assert option.price_per_night > 0


@pytest.mark.asyncio
async def test_hospedagem_mock_gera_generico_para_cidade_desconhecida():
    provider = MockAccommodationProvider()
    result = await provider.search(
        AccommodationCriteria(city="Cidade Inexistente XYZ", check_in=None, check_out=None, guests=2)
    )
    assert len(result.items) >= 3


@pytest.mark.asyncio
async def test_restaurantes_respeita_restricao_sem_gluten():
    provider = MockRestaurantsProvider()
    result = await provider.search(RestaurantsCriteria(city="Lisboa", restrictions=["sem glúten"]))
    assert len(result.items) > 0
    for r in result.items:
        assert "sem glúten" in r.compatibility or "Atende" in r.compatibility


@pytest.mark.asyncio
async def test_restaurantes_declara_lacuna_quando_nada_atende(monkeypatch):
    provider = MockRestaurantsProvider()
    result = await provider.search(
        RestaurantsCriteria(city="Lisboa", restrictions=["restricao-inexistente-xyz"])
    )
    assert result.items == []
    assert result.empty_reason is not None


@pytest.mark.asyncio
async def test_atracoes_filtra_por_interesse():
    provider = MockAttractionsProvider()
    result = await provider.search(AttractionsCriteria(city="Paris", interests=["romantica"]))
    assert len(result.items) > 0


@pytest.mark.asyncio
async def test_voos_sempre_rotulado_como_estimativa_com_faixa():
    provider = MockFlightEstimator()
    result = await provider.estimate(
        FlightCriteria(
            origin="São Paulo", destination="Lisboa", departure_date=None, return_date=None, passengers=2
        )
    )
    assert len(result.items) >= 2
    for flight in result.items:
        assert flight.source.type == "estimate"
        assert flight.min_price < flight.max_price
    assert sum(1 for f in result.items if f.recommended) == 1


@pytest.mark.asyncio
async def test_cambio_mock_retorna_taxa_conhecida():
    provider = MockExchangeRateProvider()
    rate = await provider.get_rate(ExchangeCriteria(source_currency="EUR", target_currency="BRL"))
    assert rate is not None
    assert rate.rate > 0
    assert rate.source.type == "mock"


@pytest.mark.asyncio
async def test_cambio_mesma_moeda_taxa_um():
    provider = MockExchangeRateProvider()
    rate = await provider.get_rate(ExchangeCriteria(source_currency="BRL", target_currency="BRL"))
    assert rate.rate == 1
