import time
import uuid
from dataclasses import dataclass, field

from app.llm.base import LLMMessage
from app.models.brief import TripBrief
from app.models.plan import TripPlan


@dataclass
class SessionState:
    session_id: str
    criado_em: float
    expira_em: float
    brief: TripBrief = field(default_factory=TripBrief)
    plan: TripPlan | None = None
    historico: list[LLMMessage] = field(default_factory=list)
    chamadas_de_ferramenta: int = 0
    tokens_usados: int = 0
    cache_buscas: dict[str, tuple[float, object]] = field(default_factory=dict)
    # RF-04: assinatura do briefing usado para gerar o plano atual — se o
    # briefing mudar, o plano é recalculado; se não mudou, evita replanejar
    # a cada turno (RNF-08).
    assinatura_do_ultimo_plano: str | None = None

    def expirada(self) -> bool:
        return time.monotonic() >= self.expira_em


class SessionStore:
    """Sessões efêmeras em memória com TTL (RNF-09). Sem persistência em disco."""

    def __init__(self, ttl_minutos: int = 60) -> None:
        self._ttl_segundos = ttl_minutos * 60
        self._sessoes: dict[str, SessionState] = {}

    def criar(self) -> SessionState:
        self._purgar_expiradas()
        session_id = str(uuid.uuid4())
        agora = time.monotonic()
        estado = SessionState(
            session_id=session_id,
            criado_em=agora,
            expira_em=agora + self._ttl_segundos,
        )
        self._sessoes[session_id] = estado
        return estado

    def obter(self, session_id: str) -> SessionState | None:
        estado = self._sessoes.get(session_id)
        if estado is None:
            return None
        if estado.expirada():
            del self._sessoes[session_id]
            return None
        return estado

    def renovar(self, session_id: str) -> None:
        estado = self._sessoes.get(session_id)
        if estado is not None:
            estado.expira_em = time.monotonic() + self._ttl_segundos

    def _purgar_expiradas(self) -> None:
        expiradas = [sid for sid, s in self._sessoes.items() if s.expirada()]
        for sid in expiradas:
            del self._sessoes[sid]

    def ttl_restante_segundos(self, session_id: str) -> float | None:
        estado = self.obter(session_id)
        if estado is None:
            return None
        return max(0.0, estado.expira_em - time.monotonic())
