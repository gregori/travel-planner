import hashlib
import json
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.session.store import SessionState

T = TypeVar("T")


def chave_cache(ferramenta: str, **kwargs) -> str:
    payload = json.dumps({"ferramenta": ferramenta, **kwargs}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


async def chamada_cacheada(
    sessao: SessionState,
    chave: str,
    ttl_minutos: int,
    produzir: Callable[[], Awaitable[T]],
) -> T:
    """Cache de buscas por sessão (RF-17), com TTL (RNF-08)."""
    agora = time.monotonic()
    if chave in sessao.cache_buscas:
        armazenado_em, valor = sessao.cache_buscas[chave]
        if agora - armazenado_em < ttl_minutos * 60:
            return valor  # type: ignore[return-value]
    valor = await produzir()
    sessao.cache_buscas[chave] = (agora, valor)
    return valor
