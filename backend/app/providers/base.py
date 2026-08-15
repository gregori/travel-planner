from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Generic, Protocol, TypeVar

from app.models.plan import Atividade, CotacaoCambio, OpcaoHospedagem, OpcaoVoo, SugestaoRefeicao

T = TypeVar("T")


@dataclass
class ResultadoBusca(Generic[T]):
    """Envelope de resultado de um provedor.

    Se `itens` vier vazio, `motivo_vazio` explica por quê (RNF-02: nunca
    inventar dados — o agente deve declarar a lacuna, não preencher com
    plausibilidade).
    """

    itens: list[T] = field(default_factory=list)
    degradado: bool = False
    motivo_vazio: str | None = None


@dataclass
class CriteriosHospedagem:
    cidade: str
    check_in: date | None
    check_out: date | None
    hospedes: int
    preco_min: Decimal | None = None
    preco_max: Decimal | None = None
    moeda: str = "BRL"


@dataclass
class CriteriosAtracoes:
    cidade: str
    interesses: list[str] = field(default_factory=list)
    perfil: str = "geral"


@dataclass
class CriteriosRestaurantes:
    cidade: str
    restricoes: list[str] = field(default_factory=list)
    faixa_preco: str | None = None


@dataclass
class CriteriosVoo:
    origem: str
    destino: str
    data_ida: date | None
    data_volta: date | None
    passageiros: int
    moeda: str = "BRL"


@dataclass
class CriteriosCambio:
    moeda_origem: str
    moeda_destino: str


class ProvedorHospedagem(Protocol):
    async def buscar(self, criterios: CriteriosHospedagem) -> ResultadoBusca[OpcaoHospedagem]: ...


class ProvedorAtracoes(Protocol):
    async def buscar(self, criterios: CriteriosAtracoes) -> ResultadoBusca[Atividade]: ...


class ProvedorRestaurantes(Protocol):
    async def buscar(self, criterios: CriteriosRestaurantes) -> ResultadoBusca[SugestaoRefeicao]: ...


class ProvedorVoos(Protocol):
    async def estimar(self, criterios: CriteriosVoo) -> ResultadoBusca[OpcaoVoo]: ...


class ProvedorCambio(Protocol):
    async def cotar(self, criterios: CriteriosCambio) -> CotacaoCambio | None: ...
