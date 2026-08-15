import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from app.agent.planner import gerar_plano
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOL_HANDLERS, TOOL_SCHEMAS, AgentContext
from app.llm.base import LLMClient, LLMMessage, LLMTodosModelosFalharamError

logger = logging.getLogger("travel_planner.agent")
metricas = logging.getLogger("travel_planner.metrics")

MAX_ITERACOES_POR_TURNO = 8


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def conta_perguntas(texto: str) -> int:
    """Conta quantas perguntas há em um texto (RF-03: no máximo 2 por turno)."""
    return texto.count("?")


def estimar_tokens(texto: str) -> int:
    """Heurística simples (~4 caracteres/token) para controle de custo
    (RNF-08) sem depender de um tokenizer específico de modelo."""
    return max(1, len(texto) // 4)


def _log_estruturado(**campos: Any) -> None:
    """Log estruturado em JSON (RNF-12): session_id, ferramenta/modelo,
    latência e custo estimado, para depurar uma sessão inteira."""
    metricas.info(_dumps(campos))


async def processar_mensagem(
    ctx: AgentContext, llm: LLMClient, texto_usuario: str
) -> AsyncIterator[dict[str, Any]]:
    """Processa uma mensagem do usuário, emitindo eventos compatíveis com o
    contrato SSE de `/api/chat` (§8): token, tool_call, brief_update,
    plan_ready, error, done.
    """
    sessao = ctx.sessao
    limite_chamadas = ctx.settings.max_tool_calls_per_session
    limite_tokens = ctx.settings.max_tokens_per_session

    if not sessao.historico:
        sessao.historico.append(LLMMessage(role="system", content=SYSTEM_PROMPT))
    sessao.historico.append(LLMMessage(role="user", content=texto_usuario))
    sessao.tokens_usados += estimar_tokens(texto_usuario)

    for _ in range(MAX_ITERACOES_POR_TURNO):
        if sessao.chamadas_de_ferramenta >= limite_chamadas or sessao.tokens_usados >= limite_tokens:
            texto_final = (
                "Atingi o limite de uso desta sessão (buscas ou tokens). Vou seguir com as "
                "informações que já tenho até aqui."
            )
            sessao.historico.append(LLMMessage(role="assistant", content=texto_final))
            yield {"evento": "token", "dados": texto_final}
            break

        inicio = time.monotonic()
        resposta_final = None
        try:
            async for chunk in llm.stream(sessao.historico, tools=TOOL_SCHEMAS):
                if chunk.delta:
                    yield {"evento": "token", "dados": chunk.delta}
                if chunk.resposta_final:
                    resposta_final = chunk.resposta_final
        except LLMTodosModelosFalharamError as exc:
            logger.error("todos os modelos da cadeia falharam: %s", exc)
            yield {"evento": "error", "dados": {"codigo": "llm_indisponivel", "mensagem": str(exc)}}
            return
        except Exception as exc:  # noqa: BLE001 - falha no meio do stream (após já ter emitido texto)
            logger.error("stream do LLM interrompido no meio: %s", exc)
            yield {"evento": "error", "dados": {"codigo": "llm_stream_interrompido", "mensagem": str(exc)}}
            return

        latencia_ms = round((time.monotonic() - inicio) * 1000, 1)
        texto_resposta = resposta_final.content or "" if resposta_final else ""
        sessao.tokens_usados += estimar_tokens(texto_resposta)
        _log_estruturado(
            session_id=sessao.session_id,
            evento="llm_resposta",
            modelo=resposta_final.modelo_usado if resposta_final else None,
            latencia_ms=latencia_ms,
            tokens_estimados=sessao.tokens_usados,
            tem_tool_calls=bool(resposta_final and resposta_final.tool_calls),
        )

        if resposta_final and resposta_final.tool_calls:
            sessao.historico.append(
                LLMMessage(
                    role="assistant", content=resposta_final.content, tool_calls=resposta_final.tool_calls
                )
            )
            for chamada in resposta_final.tool_calls:
                if sessao.chamadas_de_ferramenta >= limite_chamadas:
                    resultado: dict[str, Any] = {
                        "erro": "limite de chamadas de ferramenta atingido nesta sessão"
                    }
                else:
                    sessao.chamadas_de_ferramenta += 1
                    handler = TOOL_HANDLERS.get(chamada.name)
                    inicio_ferramenta = time.monotonic()
                    if handler is None:
                        resultado = {"erro": f"ferramenta desconhecida: {chamada.name}"}
                    else:
                        try:
                            resultado = await handler(ctx, **chamada.arguments)
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("ferramenta %s falhou: %s", chamada.name, exc)
                            resultado = {"erro": str(exc)}
                    _log_estruturado(
                        session_id=sessao.session_id,
                        evento="tool_call",
                        ferramenta=chamada.name,
                        latencia_ms=round((time.monotonic() - inicio_ferramenta) * 1000, 1),
                    )

                yield {
                    "evento": "tool_call",
                    "dados": {"ferramenta": chamada.name, "argumentos": chamada.arguments},
                }
                if chamada.name == "atualizar_briefing":
                    yield {"evento": "brief_update", "dados": sessao.brief.model_dump(mode="json")}

                resultado_texto = _dumps(resultado)
                sessao.tokens_usados += estimar_tokens(resultado_texto)
                sessao.historico.append(
                    LLMMessage(
                        role="tool",
                        tool_call_id=chamada.id,
                        name=chamada.name,
                        content=resultado_texto,
                    )
                )
            continue  # deixa o LLM reagir aos resultados das ferramentas

        if conta_perguntas(texto_resposta) > 2:
            logger.warning("resposta do agente contém mais de 2 perguntas (RF-03)")
        if texto_resposta:
            sessao.historico.append(LLMMessage(role="assistant", content=texto_resposta))
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
        assinatura_atual = sessao.brief.model_dump_json()
        if assinatura_atual != sessao.assinatura_do_ultimo_plano:
            try:
                plano = await gerar_plano(ctx)
                sessao.plan = plano
                sessao.assinatura_do_ultimo_plano = assinatura_atual
                yield {"evento": "plan_ready", "dados": plano.model_dump(mode="json")}
            except Exception as exc:  # noqa: BLE001
                logger.error("falha ao montar o plano: %s", exc)
                yield {
                    "evento": "error",
                    "dados": {"codigo": "falha_ao_planejar", "mensagem": str(exc)},
                }

    yield {"evento": "done", "dados": None}
