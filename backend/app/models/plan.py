from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.brief import TripBrief
from app.models.common import Fonte


class Atividade(BaseModel):
    titulo: str
    descricao: str | None = None
    regiao: str | None = None
    duracao_min: int | None = None
    custo_estimado: Decimal = Decimal("0")
    fonte: Fonte | None = None
    horario: time | None = None


class Deslocamento(BaseModel):
    de_bloco: str
    para_bloco: str
    duracao_min: int
    modo: str = "a pé/transporte local"


class DiaItinerario(BaseModel):
    dia: int
    data: date | None = None
    regiao: str
    manha: list[Atividade] = Field(default_factory=list)
    tarde: list[Atividade] = Field(default_factory=list)
    noite: list[Atividade] = Field(default_factory=list)
    deslocamentos: list[Deslocamento] = Field(default_factory=list)
    custo_estimado_dia: Decimal = Decimal("0")
    observacao: str | None = None


class OpcaoVoo(BaseModel):
    companhia: str
    origem: str
    destino: str
    preco_min: Decimal
    preco_max: Decimal
    moeda: str
    duracao_horas: float | None = None
    escalas: int = 0
    recomendada: bool = False
    justificativa: str | None = None
    fonte: Fonte


class OpcaoHospedagem(BaseModel):
    nome: str
    tipo: str = "hotel"
    preco_por_noite: Decimal
    moeda: str
    localizacao: str
    avaliacao: float | None = None
    link: str | None = None
    recomendada: bool = False
    justificativa: str | None = None
    fonte: Fonte


class SugestaoRefeicao(BaseModel):
    nome: str
    tipo_refeicao: str
    culinaria: str | None = None
    faixa_preco: str | None = None
    compatibilidade: str
    localizacao: str | None = None
    link: str | None = None
    fonte: Fonte


class Orcamento(BaseModel):
    voos: Decimal = Decimal("0")
    hospedagem: Decimal = Decimal("0")
    alimentacao: Decimal = Decimal("0")
    passeios: Decimal = Decimal("0")
    transporte_local: Decimal = Decimal("0")
    contingencia: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    teto_informado: Decimal | None = None
    diferenca: Decimal | None = None
    dentro_do_teto: bool = True
    alertas: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _calcula_total_e_diferenca(self) -> "Orcamento":
        soma = (
            self.voos
            + self.hospedagem
            + self.alimentacao
            + self.passeios
            + self.transporte_local
            + self.contingencia
        )
        self.total = soma
        if self.teto_informado is not None:
            self.diferenca = soma - self.teto_informado
            self.dentro_do_teto = self.diferenca <= 0
        return self


class CotacaoCambio(BaseModel):
    moeda_origem: str
    moeda_destino: str
    taxa: Decimal
    fonte: Fonte


class Checklist(BaseModel):
    documentos: list[str] = Field(default_factory=list)
    clima: str | None = None
    moeda_e_cambio: str | None = None
    tomada_adaptador: str | None = None
    o_que_levar: list[str] = Field(default_factory=list)
    requisitos_entrada: list[str] = Field(default_factory=list)


class TripPlan(BaseModel):
    brief: TripBrief
    resumo: str
    opcoes_voo: list[OpcaoVoo] = Field(default_factory=list)
    opcoes_hospedagem: list[OpcaoHospedagem] = Field(default_factory=list)
    itinerario: list[DiaItinerario] = Field(default_factory=list)
    refeicoes: list[SugestaoRefeicao] = Field(default_factory=list)
    orcamento: Orcamento
    cambio: CotacaoCambio | None = None
    checklist: Checklist = Field(default_factory=Checklist)
    fontes: list[Fonte] = Field(default_factory=list)
    avisos: list[str] = Field(default_factory=list)
    gerado_em: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def _valida_regra_invariante_de_fonte(self) -> "TripPlan":
        """Todo campo monetário exibido deve referenciar uma Fonte (RF-15, §7.3)."""
        for voo in self.opcoes_voo:
            if voo.fonte is None:
                raise ValueError("OpcaoVoo sem Fonte: plano inválido")
        for hosp in self.opcoes_hospedagem:
            if hosp.fonte is None:
                raise ValueError("OpcaoHospedagem sem Fonte: plano inválido")
        for ref in self.refeicoes:
            if ref.fonte is None:
                raise ValueError("SugestaoRefeicao sem Fonte: plano inválido")
        return self
