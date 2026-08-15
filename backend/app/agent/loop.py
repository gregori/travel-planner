import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from app.agent.planner import gerar_plano
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOL_HANDLERS, TOOL_SCHEMAS, AgentContext
from app.llm.base import LLMClient, LLMMessage, LLMTodosModelosFalharamError

logger = logging.getLogger("travel_planner.agent")

MAX_ITERACOES_POR_TURNO = 8


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def conta_perguntas(texto: str) -> int:
    """Conta quantas perguntas há em um texto (RF-03: no máximo 2 por turno)."""
    return texto.count("?")


async def processar_mensagem(
    ctx: AgentContext, llm: LLMClient, texto_usuario: str
) -> AsyncIterator[dict[str, Any]]:
    """Processa uma mensagem do usuário, emitindo eventos compatíveis com o
    contrato SSE de `/api/chat` (§8): token, tool_call, brief_update,
    plan_ready, error, done.
    """
    sessao = ctx.sessao
    limite_chamadas = ctx.settings.max_tool_calls_per_session

    if not sessao.historico:
        sessao.historico.append(LLMMessage(role="system", content=SYSTEM_PROMPT))
    sessao.historico.append(LLMMessage(role="user", content=texto_usuario))

    for _ in range(MAX_ITERACOES_POR_TURNO):
        if sessao.chamadas_de_ferramenta >= limite_chamadas:
            texto_final = (
                "Atingi o limite de buscas para esta sessão. Vou seguir com as "
                "informações que já tenho até aqui."
            )
            sessao.historico.append(LLMMessage(role="assistant", content=texto_final))
            yield {"evento": "token", "dados": texto_final}
            break

        try:
            resposta = await llm.complete(sessao.historico, tools=TOOL_SCHEMAS)
        except LLMTodosModelosFalharamError as exc:
            logger.error("todos os modelos da cadeia falharam: %s", exc)
            yield {"evento": "error", "dados": {"codigo": "llm_indisponivel", "mensagem": str(exc)}}
            return

        if resposta.tool_calls:
            sessao.historico.append(
                LLMMessage(role="assistant", content=resposta.content, tool_calls=resposta.tool_calls)
            )
            for chamada in resposta.tool_calls:
                if sessao.chamadas_de_ferramenta >= limite_chamadas:
                    resultado: dict[str, Any] = {
                        "erro": "limite de chamadas de ferramenta atingido nesta sessão"
                    }
                else:
                    sessao.chamadas_de_ferramenta += 1
                    handler = TOOL_HANDLERS.get(chamada.name)
                    if handler is None:
                        resultado = {"erro": f"ferramenta desconhecida: {chamada.name}"}
                    else:
                        try:
                            resultado = await handler(ctx, **chamada.arguments)
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("ferramenta %s falhou: %s", chamada.name, exc)
                            resultado = {"erro": str(exc)}

                yield {
                    "evento": "tool_call",
                    "dados": {"ferramenta": chamada.name, "argumentos": chamada.arguments},
                }
                if chamada.name == "atualizar_briefing":
                    yield {"evento": "brief_update", "dados": sessao.brief.model_dump(mode="json")}

                sessao.historico.append(
                    LLMMessage(
                        role="tool",
                        tool_call_id=chamada.id,
                        name=chamada.name,
                        content=_dumps(resultado),
                    )
                )
            continue  # deixa o LLM reagir aos resultados das ferramentas

        texto = resposta.content or ""
        sessao.historico.append(LLMMessage(role="assistant", content=texto))
        if conta_perguntas(texto) > 2:
            logger.warning("resposta do agente contém mais de 2 perguntas (RF-03)")
        yield {"evento": "token", "dados": texto}
        break
    else:
        yield {
            "evento": "error",
            "dados": {
                "codigo": "loop_nao_convergiu",
                "mensagem": "Muitas chamadas de ferramenta em sequência.",
            },
        }

    if sessao.brief.pronto_para_planejar():
        try:
            plano = await gerar_plano(ctx)
            sessao.plan = plano
            yield {"evento": "plan_ready", "dados": plano.model_dump(mode="json")}
        except Exception as exc:  # noqa: BLE001
            logger.error("falha ao montar o plano: %s", exc)
            yield {
                "evento": "error",
                "dados": {"codigo": "falha_ao_planejar", "mensagem": str(exc)},
            }

    yield {"evento": "done", "dados": None}
