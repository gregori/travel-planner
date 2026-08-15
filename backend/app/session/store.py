import time
import uuid
from dataclasses import dataclass, field

from app.llm.base import LLMMessage
from app.models.brief import TripBrief
from app.models.plan import TripPlan


@dataclass
class SessionState:
    session_id: str
    created_at: float
    expires_at: float
    brief: TripBrief = field(default_factory=TripBrief)
    plan: TripPlan | None = None
    history: list[LLMMessage] = field(default_factory=list)
    tool_calls_made: int = 0
    tokens_used: int = 0
    search_cache: dict[str, tuple[float, object]] = field(default_factory=dict)
    # RF-04: assinatura do briefing usado para gerar o plano atual — se o
    # briefing mudar, o plano é recalculado; se não mudou, evita replanejar
    # a cada turno (RNF-08).
    last_plan_signature: str | None = None

    def is_expired(self) -> bool:
        return time.monotonic() >= self.expires_at


class SessionStore:
    """Sessões efêmeras em memória com TTL (RNF-09). Sem persistência em disco."""

    def __init__(self, ttl_minutes: int = 60) -> None:
        self._ttl_seconds = ttl_minutes * 60
        self._sessions: dict[str, SessionState] = {}

    def create(self) -> SessionState:
        self._purge_expired()
        session_id = str(uuid.uuid4())
        now = time.monotonic()
        state = SessionState(
            session_id=session_id,
            created_at=now,
            expires_at=now + self._ttl_seconds,
        )
        self._sessions[session_id] = state
        return state

    def get(self, session_id: str) -> SessionState | None:
        state = self._sessions.get(session_id)
        if state is None:
            return None
        if state.is_expired():
            del self._sessions[session_id]
            return None
        return state

    def renew(self, session_id: str) -> None:
        state = self._sessions.get(session_id)
        if state is not None:
            state.expires_at = time.monotonic() + self._ttl_seconds

    def _purge_expired(self) -> None:
        expired = [sid for sid, s in self._sessions.items() if s.is_expired()]
        for sid in expired:
            del self._sessions[sid]

    def ttl_remaining_seconds(self, session_id: str) -> float | None:
        state = self.get(session_id)
        if state is None:
            return None
        return max(0.0, state.expires_at - time.monotonic())
