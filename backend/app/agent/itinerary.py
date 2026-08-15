import unicodedata
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from app.models.brief import TripBrief
from app.models.plan import Activity, ItineraryDay, MealSuggestion, Transfer

MAX_ACTIVITIES_BY_PACE = {"light": 2, "moderate": 3, "intense": 4}
MAX_ACTIVITIES_RESTRICTED = 2  # RF-22: crianças ou mobilidade reduzida


def _slug(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().strip().lower()


def _max_main_activities(brief: TripBrief) -> int:
    if brief.has_children or brief.mobility_restrictions:
        return MAX_ACTIVITIES_RESTRICTED
    return MAX_ACTIVITIES_BY_PACE.get(brief.pace, 3)


def _free_activity(region: str) -> Activity:
    return Activity(
        title="Tempo livre / descanso",
        description="Sem atração específica encontrada para este bloco — aproveite para explorar "
        "por conta própria ou descansar.",
        region=region,
        duration_min=None,
        estimated_cost=Decimal("0"),
        source=None,
    )


def _take_up_to(available: list[Activity], n: int) -> list[Activity]:
    """Consome (pop) até `n` atividades da lista compartilhada da região, para
    que não sejam reaproveitadas em outro dia."""
    chosen: list[Activity] = []
    for _ in range(min(n, len(available))):
        chosen.append(available.pop(0))
    return chosen


def _take_meal(meals: list[MealSuggestion], region: str) -> list[Activity]:
    """Escolhe uma refeição para o dia, preferindo uma cuja localização real
    bata com a região do dia (RF-21: coerência geográfica) — só cai para a
    próxima disponível se nenhuma refeição estiver naquela região."""
    if not meals:
        return []
    region_slug = _slug(region)
    index = next(
        (i for i, m in enumerate(meals) if m.location and region_slug in _slug(m.location)),
        0,
    )
    meal = meals.pop(index)
    return [
        Activity(
            title=f"Jantar: {meal.name}",
            description=f"{meal.compatibility} ({meal.location or region})",
            region=region,
            estimated_cost=Decimal("0"),
            source=meal.source,
        )
    ]


def build_itinerary(
    brief: TripBrief,
    total_days: int,
    activity_pool: list[Activity],
    meal_pool: list[MealSuggestion],
) -> list[ItineraryDay]:
    """Constrói o itinerário dia a dia (RF-20..23).

    - Agrupa atividades do mesmo dia por região (RF-21).
    - Limita atividades principais por ritmo/perfil (RF-22).
    - Reserva os dias de chegada/partida para logística, sem sobrepor
      atrações a check-in/check-out/deslocamento ao aeroporto (RF-23).
    """
    max_main = _max_main_activities(brief)

    by_region: dict[str, list[Activity]] = defaultdict(list)
    for a in activity_pool:
        by_region[a.region or "Centro"].append(a)
    available_regions = list(by_region.keys()) or ["Centro"]

    remaining_meals = list(meal_pool)
    base_date = brief.start_date

    days: list[ItineraryDay] = []
    for day_index in range(1, total_days + 1):
        is_arrival = day_index == 1
        is_departure = day_index == total_days and total_days > 1
        day_region = available_regions[(day_index - 1) % len(available_regions)]
        available = by_region.get(day_region, [])

        morning: list[Activity] = []
        afternoon: list[Activity] = []
        evening: list[Activity] = []
        transfers: list[Transfer] = []
        note = None

        if is_arrival:
            morning = [
                Activity(
                    title="Chegada e check-in",
                    description="Desembarque, deslocamento ao aeroporto/estação e check-in na "
                    "hospedagem. Sem atividades agendadas para não conflitar com o voo (RF-23).",
                    region=day_region,
                    estimated_cost=Decimal("0"),
                )
            ]
            afternoon = _take_up_to(available, 1) or [_free_activity(day_region)]
            evening = _take_meal(remaining_meals, day_region) or [_free_activity(day_region)]
            note = "Dia de chegada: ritmo leve para absorver o deslocamento (RF-23)."
        elif is_departure:
            morning = _take_up_to(available, 1) or [_free_activity(day_region)]
            afternoon = [
                Activity(
                    title="Checkout e deslocamento ao aeroporto",
                    description="Checkout da hospedagem e deslocamento com margem de segurança "
                    "para o horário do voo de volta (RF-23).",
                    region=day_region,
                    estimated_cost=Decimal("0"),
                )
            ]
            evening = []
            note = "Dia de partida: sem atividades à noite para não conflitar com o voo (RF-23)."
        else:
            main_activities = _take_up_to(available, max_main)
            if not main_activities:
                main_activities = [_free_activity(day_region)]
            half = max(1, len(main_activities) // 2) if len(main_activities) > 1 else len(main_activities)
            morning = main_activities[:half] or [_free_activity(day_region)]
            afternoon = main_activities[half:] or []
            evening = _take_meal(remaining_meals, day_region) or [_free_activity(day_region)]
            if brief.has_children or brief.mobility_restrictions:
                note = "Ritmo ajustado: pausa explícita à tarde entre as atividades (RF-22)."

        if morning and afternoon:
            transfers.append(Transfer(from_block="morning", to_block="afternoon", duration_min=20))
        if afternoon and evening:
            transfers.append(Transfer(from_block="afternoon", to_block="evening", duration_min=20))

        day_cost = sum((a.estimated_cost for a in morning + afternoon + evening), Decimal("0"))

        days.append(
            ItineraryDay(
                day=day_index,
                date=(base_date + timedelta(days=day_index - 1)) if base_date else None,
                region=day_region,
                morning=morning,
                afternoon=afternoon,
                evening=evening,
                transfers=transfers,
                estimated_day_cost=day_cost,
                note=note,
            )
        )

    return days
