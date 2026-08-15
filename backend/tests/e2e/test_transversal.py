import pytest

from app.agent.loop import processar_mensagem
from app.agent.tools import AgentContext
from app.config import Settings
from app.llm.base import LLMResponse, ToolCall
from app.llm.fake import FakeLLM
from app.providers.base import CriteriosHospedagem
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore

BRIEF_MINIMO = {
    "origem": "São Paulo",
    "destino": "Roma",
    "mes_referencia": "março",
    "duracao_dias": 4,
    "adultos": 1,
    "orcamento_total": 9000,
}


@pytest.mark.asyncio
async def test_app_roda_ponta_a_ponta_sem_nenhuma_credencial(settings: Settings, registry: ProviderRegistry):
    """Sem credenciais configuradas, o app deve funcionar ponta a ponta em modo
    mock, com aviso visível (RF-16)."""
    assert registry.status_provedores()["booking"] == "mock"
    assert registry.status_provedores()["tripadvisor"] == "mock"

    store = SessionStore(ttl_minutos=60)
    estado = store.criar()
    ctx = AgentContext(sessao=estado, registry=registry, settings=settings)
    llm = FakeLLM(
        script=[
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="c1", name="atualizar_briefing", arguments=BRIEF_MINIMO)],
                finish_reason="tool_calls",
            ),
            LLMResponse(content="Vou montar seu roteiro para Roma."),
        ]
    )

    eventos = [e async for e in processar_mensagem(ctx, llm, "Quero ir a Roma")]
    assert "plan_ready" in [e["evento"] for e in eventos]
    assert "error" not in [e["evento"] for e in eventos]
    plano = estado.plan
    assert plano is not None
    assert any(f.tipo == "mock" for f in plano.fontes)
    assert plano.avisos  # avisos de degradação/mock visíveis


@pytest.mark.asyncio
async def test_falha_de_provedor_gera_plano_com_aviso_de_degradacao(settings: Settings):
    settings_com_credencial = settings.model_copy(update={"booking_api_key": "chave-fake"})
    registry = ProviderRegistry(settings_com_credencial)

    class ProvedorComTimeout:
        async def buscar(self, criterios):
            raise TimeoutError("timeout simulado no provedor real")

    registry._booking_real = ProvedorComTimeout()

    avisos: list[str] = []
    resultado = await registry.buscar_hospedagem(
        CriteriosHospedagem(cidade="Lisboa", check_in=None, check_out=None, hospedes=2), avisos
    )
    assert len(resultado.itens) >= 3  # a requisição nunca falha (RNF-06)
    assert any("indisponível" in a for a in avisos)


@pytest.mark.asyncio
async def test_fallback_de_modelo_primario_para_secundario(settings: Settings, registry: ProviderRegistry):
    """RNF-07: se o modelo primário falhar, o sistema tenta o próximo
    automaticamente e registra qual modelo respondeu."""
    store = SessionStore(ttl_minutos=60)
    estado = store.criar()
    ctx = AgentContext(sessao=estado, registry=registry, settings=settings)

    llm = FakeLLM(
        script=[LLMResponse(content="Resposta do modelo secundário.")],
        model_chain=["modelo-primario", "modelo-secundario"],
        falha_modelos={"modelo-primario"},
    )

    eventos = [e async for e in processar_mensagem(ctx, llm, "Olá")]
    assert "error" not in [e["evento"] for e in eventos]
    assert llm.modelos_tentados == ["modelo-primario", "modelo-secundario"]
