from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

TripType = Literal["sightseeing", "romantic", "family", "adventure", "cultural", "relaxation"]
Pace = Literal["light", "moderate", "intense"]

# Campos mínimos obrigatórios para gerar um plano (RF-02).
REQUIRED_FIELDS = ("destination", "dates_or_duration", "travelers", "total_budget")


class TripBrief(BaseModel):
    """O que o agente coleta ao longo da conversa (REQUIREMENTS.md §7.1)."""

    origin: str | None = None
    destination: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    reference_month: str | None = None
    duration_days: int | None = None
    flexible_dates: bool = False
    # None = ainda não informado pelo usuário (RF-02); só assume 1 adulto
    # como inferência explícita no momento de planejar (RF-05).
    adults: int | None = None
    children_ages: list[int] = Field(default_factory=list)
    total_budget: Decimal | None = None
    budget_currency: str = "BRL"
    display_currency: str = "BRL"
    budget_tolerance: float = 0.10
    trip_type: TripType | None = None
    interests: list[str] = Field(default_factory=list)
    dietary_restrictions: list[str] = Field(default_factory=list)
    mobility_restrictions: str | None = None
    other_restrictions: list[str] = Field(default_factory=list)
    pace: Pace = "moderate"
    nationality: str | None = None
    inferred_fields: list[str] = Field(default_factory=list)

    @property
    def total_travelers(self) -> int:
        return (self.adults or 0) + len(self.children_ages)

    @property
    def has_children(self) -> bool:
        return len(self.children_ages) > 0

    def missing_fields(self) -> list[str]:
        """Campos obrigatórios ainda ausentes (RF-02)."""
        missing: list[str] = []
        if not self.destination:
            missing.append("destino")
        if not (self.start_date and self.end_date) and not (self.reference_month and self.duration_days):
            missing.append("datas (ou mês + duração)")
        if self.adults is None:
            missing.append("número de viajantes")
        if self.total_budget is None:
            missing.append("orçamento")
        return missing

    def ready_to_plan(self) -> bool:
        return len(self.missing_fields()) == 0

    def estimated_duration(self) -> int | None:
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return self.duration_days

    def merge(self, **partial_fields) -> "TripBrief":
        """Atualiza o briefing com campos parciais, preservando os já definidos.

        RF-04: quando `duration_days` é alterado explicitamente sem novas datas
        exatas no mesmo turno, o `end_date` antigo (que teria prioridade em
        `estimated_duration`) é invalidado para que a nova duração realmente
        seja usada no recálculo do plano.
        """
        updated = self.model_dump()
        for key, value in partial_fields.items():
            if value is None:
                continue
            if key not in updated:
                continue
            updated[key] = value

        duration_changed = "duration_days" in partial_fields and partial_fields["duration_days"] is not None
        new_dates = "start_date" in partial_fields or "end_date" in partial_fields
        if duration_changed and not new_dates:
            start_date = updated.get("start_date")
            if start_date:
                if isinstance(start_date, str):
                    start_date = date.fromisoformat(start_date)
                updated["end_date"] = start_date + timedelta(days=partial_fields["duration_days"] - 1)
            else:
                updated["end_date"] = None

        return TripBrief(**updated)

    def with_default_inferences(self) -> "TripBrief":
        """Aplica inferências determinísticas de ritmo quando o usuário não
        declarou (RF-05, RF-22): viagens com crianças ou mobilidade reduzida
        assumem ritmo leve por padrão."""
        needs_light_pace = self.has_children or bool(self.mobility_restrictions)
        already_inferred = "pace" in self.inferred_fields
        if needs_light_pace and self.pace == "moderate" and not already_inferred:
            updated = self.model_dump()
            updated["pace"] = "light"
            updated["inferred_fields"] = [*self.inferred_fields, "pace"]
            return TripBrief(**updated)
        return self
