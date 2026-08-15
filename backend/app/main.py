import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.config import Settings, get_settings
from app.llm.openai_client import OpenAICompatibleLLM
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("travel_planner")


def _validar_cadeia_de_modelos(settings: Settings) -> None:
    """Validação estrutural da cadeia de fallback (RNF-07, §9).

    Não faz chamadas de rede no startup (mantém testes/CI offline — RNF-03).
    A validação funcional de cada modelo ocorre no primeiro uso real; qual
    modelo respondeu é registrado em log a cada chamada.
    """
    cadeia = settings.model_chain_lista
    if not cadeia:
        raise RuntimeError("LLM_MODEL_CHAIN não pode ser vazio — configure ao menos um modelo.")
    logger.info("cadeia de modelos configurada: %s", cadeia)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _validar_cadeia_de_modelos(settings)

    app.state.settings = settings
    app.state.session_store = SessionStore(ttl_minutos=settings.session_ttl_minutes)
    app.state.provider_registry = ProviderRegistry(settings)
    app.state.llm_client = OpenAICompatibleLLM(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model_chain=settings.model_chain_lista,
    )
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Travel Planner API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    settings_padrao = get_settings()
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[f"{settings_padrao.rate_limit_per_minute}/minute"],
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    from app.api.routes import router

    app.include_router(router, prefix="/api")
    return app


app = create_app()
