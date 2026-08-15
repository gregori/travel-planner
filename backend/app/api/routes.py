import json

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
from starlette.responses import JSONResponse, Response

from app.agent.loop import processar_mensagem
from app.agent.tools import AgentContext
from app.api.deps import get_llm_client, get_provider_registry, get_session_store, get_settings
from app.api.schemas import ChatRequisicao, SessaoResposta
from app.config import Settings
from app.export.markdown import gerar_markdown
from app.export.pdf import gerar_pdf_bytes
from app.llm.base import LLMClient
from app.providers.registry import ProviderRegistry
from app.session.store import SessionStore

router = APIRouter()


def _erro(codigo: str, mensagem: str, status: int, recuperavel: bool = True) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"erro": {"codigo": codigo, "mensagem": mensagem, "recuperavel": recuperavel}},
    )


@router.post("/session", response_model=SessaoResposta)
async def criar_sessao(
    request: Request,
    store: SessionStore = Depends(get_session_store),
    settings: Settings = Depends(get_settings),
):
    estado = store.criar()
    return SessaoResposta(session_id=estado.session_id, ttl_minutos=settings.session_ttl_minutes)


@router.post("/chat")
async def chat(
    request: Request,
    corpo: ChatRequisicao,
    store: SessionStore = Depends(get_session_store),
    registry: ProviderRegistry = Depends(get_provider_registry),
    settings: Settings = Depends(get_settings),
    llm: LLMClient = Depends(get_llm_client),
):
    estado = store.obter(corpo.session_id)
    if estado is None:
        return _erro(
            "sessao_invalida",
            "Sessão não encontrada ou expirada. Crie uma nova sessão em /api/session.",
            404,
            recuperavel=True,
        )
    store.renovar(corpo.session_id)
    ctx = AgentContext(sessao=estado, registry=registry, settings=settings)

    async def gerador():
        async for evento in processar_mensagem(ctx, llm, corpo.mensagem):
            yield {
                "event": evento["evento"],
                "data": json.dumps(evento["dados"], ensure_ascii=False, default=str),
            }

    return EventSourceResponse(gerador())


@router.get("/session/{session_id}/brief")
async def obter_briefing(session_id: str, store: SessionStore = Depends(get_session_store)):
    estado = store.obter(session_id)
    if estado is None:
        return _erro("sessao_invalida", "Sessão não encontrada ou expirada.", 404)
    return estado.brief.model_dump(mode="json")


@router.get("/session/{session_id}/plan")
async def obter_plano(session_id: str, store: SessionStore = Depends(get_session_store)):
    estado = store.obter(session_id)
    if estado is None:
        return _erro("sessao_invalida", "Sessão não encontrada ou expirada.", 404)
    if estado.plan is None:
        return _erro(
            "plano_nao_disponivel",
            "Ainda não há um plano pronto para esta sessão — continue a conversa.",
            409,
        )
    return estado.plan.model_dump(mode="json")


@router.get("/session/{session_id}/export")
async def exportar_plano(
    session_id: str, format: str = "md", store: SessionStore = Depends(get_session_store)
):
    estado = store.obter(session_id)
    if estado is None:
        return _erro("sessao_invalida", "Sessão não encontrada ou expirada.", 404)
    if estado.plan is None:
        return _erro(
            "plano_nao_disponivel",
            "Ainda não há um plano pronto para exportar.",
            409,
        )

    if format == "md":
        conteudo = gerar_markdown(estado.plan)
        return Response(
            content=conteudo,
            media_type="text/markdown",
            headers={"Content-Disposition": "attachment; filename=roteiro.md"},
        )
    if format == "pdf":
        conteudo_pdf = gerar_pdf_bytes(estado.plan)
        return Response(
            content=conteudo_pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=roteiro.pdf"},
        )
    return _erro("formato_invalido", "Formato de exportação deve ser 'md' ou 'pdf'.", 400)


@router.get("/health")
async def health(registry: ProviderRegistry = Depends(get_provider_registry)):
    return {"status": "ok", "provedores": registry.status_provedores()}
