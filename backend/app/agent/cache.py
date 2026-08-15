import hashlib
import json
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.session.store import SessionState

T = TypeVar("T")


def cache_key(tool: str, **kwargs) -> str:
    payload = json.dumps({"tool": tool, **kwargs}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


async def cached_call(
    session: SessionState,
    key: str,
    ttl_minutes: int,
    produce: Callable[[], Awaitable[T]],
) -> T:
    """Cache de buscas por sessão (RF-17), com TTL (RNF-08)."""
    now = time.monotonic()
    if key in session.search_cache:
        stored_at, value = session.search_cache[key]
        if now - stored_at < ttl_minutes * 60:
            return value  # type: ignore[return-value]
    value = await produce()
    session.search_cache[key] = (now, value)
    return value
