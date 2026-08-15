import json

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
from starlette.responses import JSONResponse, Response

from app.agent.loop import process_message
from app.agent.tools import AgentContext
from app.api.deps import get_llm_client, get_provider_registry, get_session_store, get_settings
from app.api.schemas import ChatRequest, SessionResponse
from app.config import Settings
from app.export.markdown import generate_markdown
from app.export.pdf import generate_pdf_bytes
from app.llm.base import LLMClient
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore

router = APIRouter()


def _error(code: str, message: str, status: int, recoverable: bool = True) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "recoverable": recoverable}},
    )


@router.post("/session", response_model=SessionResponse)
async def create_session(
    request: Request,
    store: SessionStore = Depends(get_session_store),
    settings: Settings = Depends(get_settings),
):
    state = store.create()
    return SessionResponse(session_id=state.session_id, ttl_minutes=settings.session_ttl_minutes)


@router.post("/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    store: SessionStore = Depends(get_session_store),
    registry: ProviderRegistry = Depends(get_provider_registry),
    settings: Settings = Depends(get_settings),
    llm: LLMClient = Depends(get_llm_client),
):
    state = store.get(body.session_id)
    if state is None:
        return _error(
            "invalid_session",
            "Sessão não encontrada ou expirada. Crie uma nova sessão em /api/session.",
            404,
            recoverable=True,
        )
    store.renew(body.session_id)
    ctx = AgentContext(session=state, registry=registry, settings=settings)

    async def generator():
        async for event in process_message(ctx, llm, body.message):
            yield {
                "event": event["event"],
                "data": json.dumps(event["data"], ensure_ascii=False, default=str),
            }

    return EventSourceResponse(generator())


@router.get("/session/{session_id}/brief")
async def get_brief(session_id: str, store: SessionStore = Depends(get_session_store)):
    state = store.get(session_id)
    if state is None:
        return _error("invalid_session", "Sessão não encontrada ou expirada.", 404)
    return state.brief.model_dump(mode="json")


@router.get("/session/{session_id}/plan")
async def get_plan(session_id: str, store: SessionStore = Depends(get_session_store)):
    state = store.get(session_id)
    if state is None:
        return _error("invalid_session", "Sessão não encontrada ou expirada.", 404)
    if state.plan is None:
        return _error(
            "plan_not_available",
            "Ainda não há um plano pronto para esta sessão — continue a conversa.",
            409,
        )
    return state.plan.model_dump(mode="json")


@router.get("/session/{session_id}/export")
async def export_plan(session_id: str, format: str = "md", store: SessionStore = Depends(get_session_store)):
    state = store.get(session_id)
    if state is None:
        return _error("invalid_session", "Sessão não encontrada ou expirada.", 404)
    if state.plan is None:
        return _error(
            "plan_not_available",
            "Ainda não há um plano pronto para exportar.",
            409,
        )

    if format == "md":
        content = generate_markdown(state.plan)
        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": "attachment; filename=roteiro.md"},
        )
    if format == "pdf":
        pdf_content = generate_pdf_bytes(state.plan)
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=roteiro.pdf"},
        )
    return _error("invalid_format", "Formato de exportação deve ser 'md' ou 'pdf'.", 400)


@router.get("/health")
async def health(registry: ProviderRegistry = Depends(get_provider_registry)):
    return {"status": "ok", "providers": registry.provider_status()}
