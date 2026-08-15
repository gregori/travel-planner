from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

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
    # None = ainda não informado pelo usuário (RF-02); só assume 1 adulto
    # como inferência explícita no momento de planejar (RF-05).
    adultos: int | None = None
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
        return (self.adultos or 0) + len(self.criancas_idades)

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
        if self.adultos is None:
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
        """Atualiza o briefing com campos parciais, preservando os já definidos.

        RF-04: quando `duracao_dias` é alterado explicitamente sem novas datas
        exatas no mesmo turno, a `data_volta` antiga (que teria prioridade em
        `duracao_estimada`) é invalidada para que a nova duração realmente
        seja usada no recálculo do plano.
        """
        atualizados = self.model_dump()
        for chave, valor in campos_parciais.items():
            if valor is None:
                continue
            if chave not in atualizados:
                continue
            atualizados[chave] = valor

        duracao_mudou = "duracao_dias" in campos_parciais and campos_parciais["duracao_dias"] is not None
        datas_novas = "data_ida" in campos_parciais or "data_volta" in campos_parciais
        if duracao_mudou and not datas_novas:
            data_ida = atualizados.get("data_ida")
            if data_ida:
                if isinstance(data_ida, str):
                    data_ida = date.fromisoformat(data_ida)
                atualizados["data_volta"] = data_ida + timedelta(days=campos_parciais["duracao_dias"] - 1)
            else:
                atualizados["data_volta"] = None

        return TripBrief(**atualizados)

    def com_inferencias_padrao(self) -> "TripBrief":
        """Aplica inferências determinísticas de ritmo quando o usuário não
        declarou (RF-05, RF-22): viagens com crianças ou mobilidade reduzida
        assumem ritmo leve por padrão."""
        precisa_ritmo_leve = self.tem_criancas or bool(self.restricoes_mobilidade)
        ja_inferido = "ritmo" in self.campos_inferidos
        if precisa_ritmo_leve and self.ritmo == "moderado" and not ja_inferido:
            atualizados = self.model_dump()
            atualizados["ritmo"] = "leve"
            atualizados["campos_inferidos"] = [*self.campos_inferidos, "ritmo"]
            return TripBrief(**atualizados)
        return self
