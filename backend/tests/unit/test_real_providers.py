from datetime import date

import httpx
import pytest
import respx

from app.providers.base import CriteriosCambio, CriteriosHospedagem
from app.providers.real import BookingProvider, ExchangeRateProvider


@pytest.mark.asyncio
@respx.mock
async def test_booking_provider_tenta_novamente_apos_falha_e_depois_funciona():
    """RNF-06: 3 tentativas com backoff — a 1ª falha não derruba a chamada,
    a 2ª tentativa (dentro do limite) traz o resultado."""
    rota = respx.get("https://distribution-xml.booking.com/json/hotels")
    rota.side_effect = [
        httpx.Response(503, json={"erro": "indisponivel"}),
        httpx.Response(200, json={"hotels": [{"name": "Hotel Teste", "price_per_night": 300, "url": None}]}),
    ]
    provider = BookingProvider(api_key="chave-fake")

    resultado = await provider.buscar(
        CriteriosHospedagem(
            cidade="Lisboa", check_in=date(2026, 10, 1), check_out=date(2026, 10, 7), hospedes=2
        )
    )

    assert len(resultado.itens) == 1
    assert resultado.itens[0].nome == "Hotel Teste"
    assert rota.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_booking_provider_esgota_tentativas_e_propaga_erro():
    respx.get("https://distribution-xml.booking.com/json/hotels").mock(
        return_value=httpx.Response(503, json={"erro": "indisponivel"})
    )
    provider = BookingProvider(api_key="chave-fake")

    with pytest.raises(httpx.HTTPStatusError):
        await provider.buscar(CriteriosHospedagem(cidade="Lisboa", check_in=None, check_out=None, hospedes=2))


@pytest.mark.asyncio
@respx.mock
async def test_exchange_rate_provider_real_retorna_taxa():
    respx.get("https://api.frankfurter.app/latest").mock(
        return_value=httpx.Response(200, json={"rates": {"BRL": 6.1}})
    )
    provider = ExchangeRateProvider(base_url="https://api.frankfurter.app")

    cotacao = await provider.cotar(CriteriosCambio(moeda_origem="EUR", moeda_destino="BRL"))

    assert cotacao is not None
    assert cotacao.fonte.tipo == "real"
