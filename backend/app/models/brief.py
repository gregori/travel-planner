from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

TipoViagem = Literal["passeio", "romantica", "familia", "aventura", "cultural", "descanso"]
Ritmo = Literal["leve", "moderado", "intenso"]

# Campos mínimos obrigatórios para gerar um plano (RF-02).
CAMPOS_OBRIGATORIOS = ("destino", "datas_ou_duracao", "viajantes", "orcamento_total")


class TripBrief(BaseModel):
    """O que o agente coleta ao longo da conversa (REQUIREMENTS.md §7.1)."""

    origem: str | None = None
    destino: str | None = None
    data_ida: date | None = None
    data_volta: date | None = None
    mes_referencia: str | None = None
    duracao_dias: int | None = None
    datas_flexiveis: bool = False
    adultos: int = 1
    criancas_idades: list[int] = Field(default_factory=list)
    orcamento_total: Decimal | None = None
    moeda_orcamento: str = "BRL"
    moeda_exibicao: str = "BRL"
    tolerancia_orcamento: float = 0.10
    tipo_viagem: TipoViagem | None = None
    interesses: list[str] = Field(default_factory=list)
    restricoes_alimentares: list[str] = Field(default_factory=list)
    restricoes_mobilidade: str | None = None
    outras_restricoes: list[str] = Field(default_factory=list)
    ritmo: Ritmo = "moderado"
    nacionalidade: str | None = None
    campos_inferidos: list[str] = Field(default_factory=list)

    @property
    def total_viajantes(self) -> int:
        return self.adultos + len(self.criancas_idades)

    @property
    def tem_criancas(self) -> bool:
        return len(self.criancas_idades) > 0

    def campos_faltantes(self) -> list[str]:
        """Campos obrigatórios ainda ausentes (RF-02)."""
        faltantes: list[str] = []
        if not self.destino:
            faltantes.append("destino")
        if not (self.data_ida and self.data_volta) and not (self.mes_referencia and self.duracao_dias):
            faltantes.append("datas (ou mês + duração)")
        if self.total_viajantes < 1:
            faltantes.append("número de viajantes")
        if self.orcamento_total is None:
            faltantes.append("orçamento")
        return faltantes

    def pronto_para_planejar(self) -> bool:
        return len(self.campos_faltantes()) == 0

    def duracao_estimada(self) -> int | None:
        if self.data_ida and self.data_volta:
            return (self.data_volta - self.data_ida).days + 1
        return self.duracao_dias

    def merge(self, **campos_parciais) -> "TripBrief":
        """Atualiza o briefing com campos parciais, preservando os já definidos."""
        atualizados = self.model_dump()
        for chave, valor in campos_parciais.items():
            if valor is None:
                continue
            if chave not in atualizados:
                continue
            atualizados[chave] = valor
        return TripBrief(**atualizados)

    @model_validator(mode="after")
    def _valida_ritmo_com_criancas(self) -> "TripBrief":
        return self
