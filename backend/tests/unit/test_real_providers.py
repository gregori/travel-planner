from datetime import date
from decimal import Decimal

import httpx
import pytest
import respx

from app.providers.base import AccommodationCriteria, AttractionsCriteria, ExchangeCriteria, FlightCriteria
from app.providers.real import (
    ExchangeRateProvider,
    GeoapifyProvider,
    LiteApiHotelsProvider,
    SerpApiFlightsProvider,
)


@pytest.mark.asyncio
@respx.mock
async def test_liteapi_provider_tenta_novamente_apos_falha_e_depois_funciona():
    """RNF-06: 3 tentativas com backoff — a 1ª falha não derruba a chamada,
    a 2ª tentativa (dentro do limite) traz o resultado."""
    route = respx.post("https://api.liteapi.travel/v3.0/hotels/rates")
    route.side_effect = [
        httpx.Response(503, json={"error": "unavailable"}),
        httpx.Response(
            200,
            json={
                "data": [
                    {
                        "hotelId": "lp1",
                        "roomTypes": [
                            {
                                "rates": [
                                    {"retailRate": {"total": [{"amount": 600, "currency": "BRL"}]}},
                                ]
                            }
                        ],
                    }
                ],
            },
        ),
    ]
    respx.get("https://api.liteapi.travel/v3.0/data/hotels").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "lp1", "name": "Hotel Teste", "address": "Centro, Lisboa", "rating": 8.5}]},
        )
    )
    provider = LiteApiHotelsProvider(api_key="chave-fake")

    result = await provider.search(
        AccommodationCriteria(
            city="Lisboa", check_in=date(2026, 10, 1), check_out=date(2026, 10, 7), guests=2
        )
    )

    assert len(result.items) == 1
    assert result.items[0].name == "Hotel Teste"
    assert result.items[0].price_per_night == (Decimal("600") / 6).quantize(Decimal("0.01"))
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_liteapi_provider_esgota_tentativas_e_propaga_erro():
    respx.post("https://api.liteapi.travel/v3.0/hotels/rates").mock(
        return_value=httpx.Response(503, json={"error": "unavailable"})
    )
    provider = LiteApiHotelsProvider(api_key="chave-fake")

    with pytest.raises(httpx.HTTPStatusError):
        await provider.search(
            AccommodationCriteria(
                city="Lisboa", check_in=date(2026, 10, 1), check_out=date(2026, 10, 7), guests=2
            )
        )


@pytest.mark.asyncio
async def test_liteapi_provider_sem_datas_levanta_erro_claro():
    provider = LiteApiHotelsProvider(api_key="chave-fake")

    with pytest.raises(ValueError, match="check_in"):
        await provider.search(AccommodationCriteria(city="Lisboa", check_in=None, check_out=None, guests=2))


@pytest.mark.asyncio
@respx.mock
async def test_serpapi_flights_provider_retorna_opcoes_reais():
    respx.get("https://serpapi.com/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "best_flights": [
                    {
                        "flights": [{"airline": "TAP", "flight_number": "TP 123"}],
                        "price": 4500,
                        "total_duration": 600,
                    }
                ],
                "other_flights": [
                    {
                        "flights": [{"airline": "LATAM"}, {"airline": "LATAM"}],
                        "price": 5200,
                        "total_duration": 720,
                    }
                ],
            },
        )
    )
    provider = SerpApiFlightsProvider(api_key="chave-fake")

    result = await provider.estimate(
        FlightCriteria(
            origin="São Paulo",
            destination="Lisboa",
            departure_date=date(2026, 10, 1),
            return_date=None,
            passengers=1,
        )
    )

    assert len(result.items) == 2
    assert all(o.source.type == "real" for o in result.items)
    cheapest = next(o for o in result.items if o.recommended)
    assert cheapest.min_price == 4500
    assert cheapest.stops == 0


@pytest.mark.asyncio
async def test_serpapi_flights_provider_rota_sem_iata_levanta_erro():
    provider = SerpApiFlightsProvider(api_key="chave-fake")

    with pytest.raises(ValueError, match="IATA"):
        await provider.estimate(
            FlightCriteria(
                origin="Cidade Desconhecida XYZ",
                destination="Lisboa",
                departure_date=date(2026, 10, 1),
                return_date=None,
                passengers=1,
            )
        )


@pytest.mark.asyncio
@respx.mock
async def test_geoapify_provider_retorna_atracoes():
    respx.get("https://api.geoapify.com/v1/geocode/search").mock(
        return_value=httpx.Response(200, json={"results": [{"lon": -9.14, "lat": 38.72}]})
    )
    respx.get("https://api.geoapify.com/v2/places").mock(
        return_value=httpx.Response(
            200,
            json={
                "features": [
                    {
                        "properties": {
                            "name": "Torre de Belém",
                            "formatted": "Lisboa, Portugal",
                            "city": "Lisboa",
                        }
                    }
                ]
            },
        )
    )
    provider = GeoapifyProvider(api_key="chave-fake")

    result = await provider.search_attractions(AttractionsCriteria(city="Lisboa"))

    assert len(result.items) == 1
    assert result.items[0].title == "Torre de Belém"


@pytest.mark.asyncio
@respx.mock
async def test_geoapify_provider_cidade_nao_encontrada_retorna_vazio_com_motivo():
    respx.get("https://api.geoapify.com/v1/geocode/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    provider = GeoapifyProvider(api_key="chave-fake")

    result = await provider.search_attractions(AttractionsCriteria(city="Cidade Inexistente"))

    assert result.items == []
    assert result.empty_reason is not None


@pytest.mark.asyncio
@respx.mock
async def test_exchange_rate_provider_real_retorna_taxa():
    respx.get("https://api.frankfurter.dev/v1/latest").mock(
        return_value=httpx.Response(200, json={"rates": {"BRL": 6.1}})
    )
    provider = ExchangeRateProvider(base_url="https://api.frankfurter.dev/v1")

    rate = await provider.get_rate(ExchangeCriteria(source_currency="EUR", target_currency="BRL"))

    assert rate is not None
    assert rate.source.type == "real"
