import pytest

from app.agent.loop import process_message
from app.agent.tools import AgentContext
from app.config import Settings
from app.llm.base import LLMResponse, ToolCall
from app.llm.fake import FakeLLM
from app.providers.base import AccommodationCriteria
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore

BRIEF_MINIMO = {
    "origin": "São Paulo",
    "destination": "Roma",
    "reference_month": "março",
    "duration_days": 4,
    "adults": 1,
    "total_budget": 9000,
}


@pytest.mark.asyncio
async def test_app_roda_ponta_a_ponta_sem_nenhuma_credencial(settings: Settings, registry: ProviderRegistry):
    """Sem credenciais configuradas, o app deve funcionar ponta a ponta em modo
    mock, com aviso visível (RF-16)."""
    assert registry.provider_status()["booking"] == "mock"
    assert registry.provider_status()["tripadvisor"] == "mock"

    store = SessionStore(ttl_minutes=60)
    state = store.create()
    ctx = AgentContext(session=state, registry=registry, settings=settings)
    llm = FakeLLM(
        script=[
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="c1", name="update_brief", arguments=BRIEF_MINIMO)],
                finish_reason="tool_calls",
            ),
            LLMResponse(content="Vou montar seu roteiro para Roma."),
        ]
    )

    events = [e async for e in process_message(ctx, llm, "Quero ir a Roma")]
    assert "plan_ready" in [e["event"] for e in events]
    assert "error" not in [e["event"] for e in events]
    plan = state.plan
    assert plan is not None
    assert any(f.type == "mock" for f in plan.sources)
    assert plan.warnings  # avisos de degradação/mock visíveis


@pytest.mark.asyncio
async def test_falha_de_provedor_gera_plano_com_aviso_de_degradacao(settings: Settings):
    settings_with_credential = settings.model_copy(update={"booking_api_key": "chave-fake"})
    registry = ProviderRegistry(settings_with_credential)

    class TimingOutProvider:
        async def search(self, criteria):
            raise TimeoutError("timeout simulado no provedor real")

    registry._booking_real = TimingOutProvider()

    warnings: list[str] = []
    result = await registry.search_accommodation(
        AccommodationCriteria(city="Lisboa", check_in=None, check_out=None, guests=2), warnings
    )
    assert len(result.items) >= 3  # a requisição nunca falha (RNF-06)
    assert any("indisponível" in w for w in warnings)


@pytest.mark.asyncio
async def test_fallback_de_modelo_primario_para_secundario(settings: Settings, registry: ProviderRegistry):
    """RNF-07: se o modelo primário falhar, o sistema tenta o próximo
    automaticamente e registra qual modelo respondeu."""
    store = SessionStore(ttl_minutes=60)
    state = store.create()
    ctx = AgentContext(session=state, registry=registry, settings=settings)

    llm = FakeLLM(
        script=[LLMResponse(content="Resposta do modelo secundário.")],
        model_chain=["modelo-primario", "modelo-secundario"],
        failing_models={"modelo-primario"},
    )

    events = [e async for e in process_message(ctx, llm, "Olá")]
    assert "error" not in [e["event"] for e in events]
    assert llm.models_tried == ["modelo-primario", "modelo-secundario"]
