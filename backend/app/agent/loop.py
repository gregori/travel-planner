import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from app.agent.planner import generate_plan
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOL_HANDLERS, TOOL_SCHEMAS, AgentContext
from app.llm.base import AllModelsFailedError, LLMClient, LLMMessage

logger = logging.getLogger("travel_planner.agent")
metrics = logging.getLogger("travel_planner.metrics")

MAX_ITERATIONS_PER_TURN = 8


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def count_questions(text: str) -> int:
    """Conta quantas perguntas há em um texto (RF-03: no máximo 2 por turno)."""
    return text.count("?")


def estimate_tokens(text: str) -> int:
    """Heurística simples (~4 caracteres/token) para controle de custo
    (RNF-08) sem depender de um tokenizer específico de modelo."""
    return max(1, len(text) // 4)


def _log_structured(**fields: Any) -> None:
    """Log estruturado em JSON (RNF-12): session_id, ferramenta/modelo,
    latência e custo estimado, para depurar uma sessão inteira."""
    metrics.info(_dumps(fields))


async def process_message(ctx: AgentContext, llm: LLMClient, user_text: str) -> AsyncIterator[dict[str, Any]]:
    """Processa uma mensagem do usuário, emitindo eventos compatíveis com o
    contrato SSE de `/api/chat` (§8): token, tool_call, brief_update,
    plan_ready, error, done.
    """
    session = ctx.session
    call_limit = ctx.settings.max_tool_calls_per_session
    token_limit = ctx.settings.max_tokens_per_session

    if not session.history:
        session.history.append(LLMMessage(role="system", content=SYSTEM_PROMPT))
    session.history.append(LLMMessage(role="user", content=user_text))
    session.tokens_used += estimate_tokens(user_text)

    for _ in range(MAX_ITERATIONS_PER_TURN):
        if session.tool_calls_made >= call_limit or session.tokens_used >= token_limit:
            final_text = (
                "Atingi o limite de uso desta sessão (buscas ou tokens). Vou seguir com as "
                "informações que já tenho até aqui."
            )
            session.history.append(LLMMessage(role="assistant", content=final_text))
            yield {"event": "token", "data": final_text}
            break

        start = time.monotonic()
        final_response = None
        try:
            async for chunk in llm.stream(session.history, tools=TOOL_SCHEMAS):
                if chunk.delta:
                    yield {"event": "token", "data": chunk.delta}
                if chunk.final_response:
                    final_response = chunk.final_response
        except AllModelsFailedError as exc:
            logger.error("todos os modelos da cadeia falharam: %s", exc)
            yield {"event": "error", "data": {"code": "llm_unavailable", "message": str(exc)}}
            return
        except Exception as exc:  # noqa: BLE001 - falha no meio do stream (após já ter emitido texto)
            logger.error("stream do LLM interrompido no meio: %s", exc)
            yield {"event": "error", "data": {"code": "llm_stream_interrupted", "message": str(exc)}}
            return

        latency_ms = round((time.monotonic() - start) * 1000, 1)
        response_text = final_response.content or "" if final_response else ""
        session.tokens_used += estimate_tokens(response_text)
        _log_structured(
            session_id=session.session_id,
            event="llm_response",
            model=final_response.model_used if final_response else None,
            latency_ms=latency_ms,
            estimated_tokens=session.tokens_used,
            has_tool_calls=bool(final_response and final_response.tool_calls),
        )

        if final_response and final_response.tool_calls:
            session.history.append(
                LLMMessage(
                    role="assistant", content=final_response.content, tool_calls=final_response.tool_calls
                )
            )
            for call in final_response.tool_calls:
                if session.tool_calls_made >= call_limit:
                    result: dict[str, Any] = {
                        "error": "limite de chamadas de ferramenta atingido nesta sessão"
                    }
                else:
                    session.tool_calls_made += 1
                    handler = TOOL_HANDLERS.get(call.name)
                    tool_start = time.monotonic()
                    if handler is None:
                        result = {"error": f"ferramenta desconhecida: {call.name}"}
                    else:
                        try:
                            result = await handler(ctx, **call.arguments)
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("ferramenta %s falhou: %s", call.name, exc)
                            result = {"error": str(exc)}
                    _log_structured(
                        session_id=session.session_id,
                        event="tool_call",
                        tool=call.name,
                        latency_ms=round((time.monotonic() - tool_start) * 1000, 1),
                    )

                yield {
                    "event": "tool_call",
                    "data": {"tool": call.name, "arguments": call.arguments},
                }
                if call.name == "update_brief":
                    yield {"event": "brief_update", "data": session.brief.model_dump(mode="json")}

                result_text = _dumps(result)
                session.tokens_used += estimate_tokens(result_text)
                session.history.append(
                    LLMMessage(
                        role="tool",
                        tool_call_id=call.id,
                        name=call.name,
                        content=result_text,
                    )
                )
            continue  # deixa o LLM reagir aos resultados das ferramentas

        if count_questions(response_text) > 2:
            logger.warning("resposta do agente contém mais de 2 perguntas (RF-03)")
        if response_text:
            session.history.append(LLMMessage(role="assistant", content=response_text))
        break
    else:
        yield {
            "event": "error",
            "data": {
                "code": "loop_did_not_converge",
                "message": "Muitas chamadas de ferramenta em sequência.",
            },
        }

    if session.brief.ready_to_plan():
        current_signature = session.brief.model_dump_json()
        if current_signature != session.last_plan_signature:
            try:
                plan = await generate_plan(ctx)
                session.plan = plan
                session.last_plan_signature = current_signature
                yield {"event": "plan_ready", "data": plan.model_dump(mode="json")}
            except Exception as exc:  # noqa: BLE001
                logger.error("falha ao montar o plano: %s", exc)
                yield {
                    "event": "error",
                    "data": {"code": "plan_generation_failed", "message": str(exc)},
                }

    yield {"event": "done", "data": None}
