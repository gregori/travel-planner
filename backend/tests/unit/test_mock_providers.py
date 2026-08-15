import pytest

from app.providers.base import (
    CriteriosAtracoes,
    CriteriosCambio,
    CriteriosHospedagem,
    CriteriosRestaurantes,
    CriteriosVoo,
)
from app.providers.mock import (
    ExchangeRateProviderMock,
    MockAtracoesProvider,
    MockHospedagemProvider,
    MockRestaurantesProvider,
    WebFlightEstimatorMock,
)


@pytest.mark.asyncio
async def test_hospedagem_mock_retorna_ao_menos_tres_opcoes_com_fonte():
    provider = MockHospedagemProvider()
    resultado = await provider.buscar(
        CriteriosHospedagem(cidade="Lisboa", check_in=None, check_out=None, hospedes=3)
    )
    assert len(resultado.itens) >= 3
    for opcao in resultado.itens:
        assert opcao.fonte.tipo == "mock"
        assert opcao.preco_por_noite > 0


@pytest.mark.asyncio
async def test_hospedagem_mock_gera_generico_para_cidade_desconhecida():
    provider = MockHospedagemProvider()
    resultado = await provider.buscar(
        CriteriosHospedagem(cidade="Cidade Inexistente XYZ", check_in=None, check_out=None, hospedes=2)
    )
    assert len(resultado.itens) >= 3


@pytest.mark.asyncio
async def test_restaurantes_respeita_restricao_sem_gluten():
    provider = MockRestaurantesProvider()
    resultado = await provider.buscar(CriteriosRestaurantes(cidade="Lisboa", restricoes=["sem glúten"]))
    assert len(resultado.itens) > 0
    for r in resultado.itens:
        assert "sem glúten" in r.compatibilidade or "Atende" in r.compatibilidade


@pytest.mark.asyncio
async def test_restaurantes_declara_lacuna_quando_nada_atende(monkeypatch):
    provider = MockRestaurantesProvider()
    resultado = await provider.buscar(
        CriteriosRestaurantes(cidade="Lisboa", restricoes=["restricao-inexistente-xyz"])
    )
    assert resultado.itens == []
    assert resultado.motivo_vazio is not None


@pytest.mark.asyncio
async def test_atracoes_filtra_por_interesse():
    provider = MockAtracoesProvider()
    resultado = await provider.buscar(CriteriosAtracoes(cidade="Paris", interesses=["romantica"]))
    assert len(resultado.itens) > 0


@pytest.mark.asyncio
async def test_voos_sempre_rotulado_como_estimativa_com_faixa():
    provider = WebFlightEstimatorMock()
    resultado = await provider.estimar(
        CriteriosVoo(origem="São Paulo", destino="Lisboa", data_ida=None, data_volta=None, passageiros=2)
    )
    assert len(resultado.itens) >= 2
    for voo in resultado.itens:
        assert voo.fonte.tipo == "estimativa"
        assert voo.preco_min < voo.preco_max
    assert sum(1 for v in resultado.itens if v.recomendada) == 1


@pytest.mark.asyncio
async def test_cambio_mock_retorna_taxa_conhecida():
    provider = ExchangeRateProviderMock()
    cotacao = await provider.cotar(CriteriosCambio(moeda_origem="EUR", moeda_destino="BRL"))
    assert cotacao is not None
    assert cotacao.taxa > 0
    assert cotacao.fonte.tipo == "mock"


@pytest.mark.asyncio
async def test_cambio_mesma_moeda_taxa_um():
    provider = ExchangeRateProviderMock()
    cotacao = await provider.cotar(CriteriosCambio(moeda_origem="BRL", moeda_destino="BRL"))
    assert cotacao.taxa == 1
