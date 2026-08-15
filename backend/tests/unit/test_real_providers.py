from datetime import date

import httpx
import pytest
import respx

from app.providers.base import AccommodationCriteria, ExchangeCriteria
from app.providers.real import BookingProvider, ExchangeRateProvider


@pytest.mark.asyncio
@respx.mock
async def test_booking_provider_tenta_novamente_apos_falha_e_depois_funciona():
    """RNF-06: 3 tentativas com backoff — a 1ª falha não derruba a chamada,
    a 2ª tentativa (dentro do limite) traz o resultado."""
    route = respx.get("https://distribution-xml.booking.com/json/hotels")
    route.side_effect = [
        httpx.Response(503, json={"error": "unavailable"}),
        httpx.Response(200, json={"hotels": [{"name": "Hotel Teste", "price_per_night": 300, "url": None}]}),
    ]
    provider = BookingProvider(api_key="chave-fake")

    result = await provider.search(
        AccommodationCriteria(
            city="Lisboa", check_in=date(2026, 10, 1), check_out=date(2026, 10, 7), guests=2
        )
    )

    assert len(result.items) == 1
    assert result.items[0].name == "Hotel Teste"
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_booking_provider_esgota_tentativas_e_propaga_erro():
    respx.get("https://distribution-xml.booking.com/json/hotels").mock(
        return_value=httpx.Response(503, json={"error": "unavailable"})
    )
    provider = BookingProvider(api_key="chave-fake")

    with pytest.raises(httpx.HTTPStatusError):
        await provider.search(AccommodationCriteria(city="Lisboa", check_in=None, check_out=None, guests=2))


@pytest.mark.asyncio
@respx.mock
async def test_exchange_rate_provider_real_retorna_taxa():
    respx.get("https://api.frankfurter.app/latest").mock(
        return_value=httpx.Response(200, json={"rates": {"BRL": 6.1}})
    )
    provider = ExchangeRateProvider(base_url="https://api.frankfurter.app")

    rate = await provider.get_rate(ExchangeCriteria(source_currency="EUR", target_currency="BRL"))

    assert rate is not None
    assert rate.source.type == "real"
