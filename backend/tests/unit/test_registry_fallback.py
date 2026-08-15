import pytest

from app.config import Settings
from app.providers.base import CriteriosHospedagem
from app.providers.registry import ProviderRegistry


@pytest.mark.asyncio
async def test_sem_credencial_usa_mock_e_avisa(settings: Settings):
    registry = ProviderRegistry(settings)
    avisos: list[str] = []
    resultado = await registry.buscar_hospedagem(
        CriteriosHospedagem(cidade="Lisboa", check_in=None, check_out=None, hospedes=2), avisos
    )
    assert len(resultado.itens) >= 3
    assert any("credencial" in a for a in avisos)
    assert registry.status_provedores()["booking"] == "mock"


@pytest.mark.asyncio
async def test_provedor_real_falhando_aciona_circuit_breaker_e_fallback(settings: Settings):
    settings_com_credencial = settings.model_copy(update={"booking_api_key": "chave-fake"})
    registry = ProviderRegistry(settings_com_credencial)

    class ProvedorSempreFalha:
        async def buscar(self, criterios):
            raise TimeoutError("timeout simulado")

    registry._booking_real = ProvedorSempreFalha()

    for _ in range(3):
        avisos: list[str] = []
        resultado = await registry.buscar_hospedagem(
            CriteriosHospedagem(cidade="Lisboa", check_in=None, check_out=None, hospedes=2), avisos
        )
        assert len(resultado.itens) >= 3  # degrada para mock, requisição nunca falha (RNF-06)
        assert any("indisponível" in a or "credencial" in a for a in avisos)

    # após 3 falhas consecutivas, o circuit breaker deve estar aberto
    assert registry.status_provedores()["booking"] == "indisponivel"

    avisos_finais: list[str] = []
    resultado = await registry.buscar_hospedagem(
        CriteriosHospedagem(cidade="Lisboa", check_in=None, check_out=None, hospedes=2), avisos_finais
    )
    assert len(resultado.itens) >= 3
    assert any("temporariamente desativado" in a for a in avisos_finais)
