import pytest

from app.agent.tools import AgentContext
from app.config import Settings
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore


@pytest.fixture
def settings() -> Settings:
    return Settings(
        llm_base_url="http://llm.invalid",
        llm_api_key="",
        llm_model_chain="fake-model-primario",
        booking_api_key=None,
        tripadvisor_api_key=None,
        exchange_api_url="",
        session_ttl_minutes=60,
        max_tool_calls_per_session=25,
        max_tokens_per_session=200_000,
        cache_ttl_minutes=15,
    )


@pytest.fixture
def registry(settings: Settings) -> ProviderRegistry:
    return ProviderRegistry(settings)


@pytest.fixture
def session_store(settings: Settings) -> SessionStore:
    return SessionStore(ttl_minutos=settings.session_ttl_minutes)


@pytest.fixture
def agent_ctx(settings: Settings, registry: ProviderRegistry, session_store: SessionStore) -> AgentContext:
    estado = session_store.criar()
    return AgentContext(sessao=estado, registry=registry, settings=settings)
