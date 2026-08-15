from datetime import UTC, datetime
from decimal import Decimal

from app.agent.budget import calculate_budget
from app.agent.itinerary import build_itinerary
from app.agent.tools import (
    AgentContext,
    estimate_flights_cached,
    get_exchange_rate_cached,
    search_accommodation_cached,
    search_attractions_cached,
    search_restaurants_cached,
    tool_practical_info,
)
from app.geo import currency_for_destination, is_international
from app.models.common import Source
from app.models.plan import Checklist, TripPlan

DAILY_FOOD_PER_PERSON = Decimal("120")
DAILY_LOCAL_TRANSPORT_PER_PERSON = Decimal("30")


def _profile(brief) -> str:
    parts = [brief.trip_type or "geral"]
    if brief.has_children:
        parts.append("com crianças")
    if brief.mobility_restrictions:
        parts.append("mobilidade reduzida")
    return ", ".join(parts)


def _convert(value: Decimal, source_currency: str, target_currency: str, rate: Decimal | None) -> Decimal:
    if source_currency == target_currency or value == 0:
        return value
    if rate is not None:
        return value * rate
    return value


def _heuristic_source(note: str) -> Source:
    return Source(
        type="estimate",
        provider="heuristica",
        url=None,
        retrieved_at=datetime.now(UTC),
        confidence="low",
        note=note,
    )


def _convert_itinerary_to_display_currency(
    itinerary, display_currency: str, exchange_rate: Decimal | None
) -> None:
    """Converte o custo de cada atividade do pool (potencialmente na moeda do
    destino) para a moeda de exibição, para que o orçamento e o itinerário
    fiquem consistentes numa única moeda (RF-13)."""
    for day in itinerary:
        for block in (day.morning, day.afternoon, day.evening):
            for activity in block:
                if activity.estimated_cost > 0 and activity.currency != display_currency:
                    activity.estimated_cost = _convert(
                        activity.estimated_cost, activity.currency, display_currency, exchange_rate
                    )
                    activity.currency = display_currency
        day.estimated_day_cost = sum(
            (a.estimated_cost for a in day.morning + day.afternoon + day.evening), Decimal("0")
        )


async def generate_plan(ctx: AgentContext) -> TripPlan:
    """Pipeline determinístico de geração do TripPlan (RF-20..28).

    A conversa (LLM) decide *quando* planejar; a montagem do plano em si é
    determinística para garantir os critérios de aceite (§11) de forma
    reprodutível, inclusive com `FakeLLM` nos testes (RNF-03). As buscas
    passam pelo mesmo cache/contador de chamadas usado pelas ferramentas do
    agente (RF-17, RNF-08).
    """
    brief = ctx.session.brief
    warnings: list[str] = []
    sources: list[Source] = []

    destination = brief.destination or ""
    origin = brief.origin or "Origem não informada"
    total_days = max(1, brief.estimated_duration() or 3)

    # Câmbio (RF-13) — só quando a moeda do destino difere da moeda de exibição.
    local_currency = currency_for_destination(destination)
    exchange_rate = None
    if local_currency != brief.display_currency:
        exchange_rate = await get_exchange_rate_cached(ctx, local_currency, brief.display_currency, warnings)
        if exchange_rate:
            sources.append(exchange_rate.source)
    rate_value = exchange_rate.rate if exchange_rate else None

    # Hospedagem (RF-10, RF-24: >= 3 opções)
    accommodation_result = await search_accommodation_cached(
        ctx, destination, brief.start_date, brief.end_date, brief.total_travelers, warnings
    )
    accommodation_options = accommodation_result.items
    if accommodation_options:
        cheapest = min(accommodation_options, key=lambda h: h.price_per_night)
        cheapest.recommended = True
        cheapest.rationale = "Melhor custo-benefício entre as opções encontradas para o período."
        sources.extend(h.source for h in accommodation_options)
    else:
        warnings.append(
            accommodation_result.empty_reason or f"Nenhuma hospedagem encontrada em {destination}."
        )

    # Atrações (RF-11)
    attractions_result = await search_attractions_cached(
        ctx, destination, brief.interests, _profile(brief), warnings
    )
    activity_pool = list(attractions_result.items)
    if not activity_pool:
        warnings.append(attractions_result.empty_reason or f"Nenhuma atração encontrada em {destination}.")
    sources.extend(a.source for a in activity_pool if a.source)

    # Restaurantes (RF-14)
    restaurants_result = await search_restaurants_cached(
        ctx, destination, brief.dietary_restrictions, warnings
    )
    meals = list(restaurants_result.items)
    if not meals:
        warnings.append(
            restaurants_result.empty_reason
            or f"Nenhum restaurante encontrado em {destination} para as restrições informadas."
        )
    sources.extend(m.source for m in meals)

    # Voos (RF-12, RF-24: >= 2 opções)
    flight_options = []
    if brief.origin:
        flights_result = await estimate_flights_cached(
            ctx, origin, destination, brief.start_date, brief.end_date, brief.total_travelers, warnings
        )
        flight_options = flights_result.items
        sources.extend(f.source for f in flight_options)

    # Itinerário (RF-20..23)
    itinerary = build_itinerary(brief, total_days, list(activity_pool), list(meals))
    _convert_itinerary_to_display_currency(itinerary, brief.display_currency, rate_value)

    # Orçamento (RF-25, RF-26) — usa sempre a opção recomendada (mais barata)
    chosen_accommodation = next((h for h in accommodation_options if h.recommended), None) or (
        accommodation_options[0] if accommodation_options else None
    )
    chosen_flight = next((f for f in flight_options if f.recommended), None) or (
        flight_options[0] if flight_options else None
    )
    accommodation_cost = (
        _convert(
            chosen_accommodation.price_per_night,
            chosen_accommodation.currency,
            brief.display_currency,
            rate_value,
        )
        * total_days
        if chosen_accommodation
        else Decimal("0")
    )
    flights_cost = (
        _convert(
            (chosen_flight.min_price + chosen_flight.max_price) / 2,
            chosen_flight.currency,
            brief.display_currency,
            rate_value,
        )
        * brief.total_travelers
        if chosen_flight
        else Decimal("0")
    )
    # Atividades já convertidas para display_currency acima; soma direta.
    activities_cost = (
        sum(
            (a.estimated_cost for day in itinerary for a in day.morning + day.afternoon + day.evening),
            Decimal("0"),
        )
        * brief.total_travelers
    )
    food_cost = DAILY_FOOD_PER_PERSON * total_days * brief.total_travelers
    local_transport_cost = DAILY_LOCAL_TRANSPORT_PER_PERSON * total_days * brief.total_travelers

    food_source = _heuristic_source(
        f"Estimativa heurística de alimentação: {DAILY_FOOD_PER_PERSON} {brief.display_currency}"
        "/pessoa/dia — não vem de um provedor específico."
    )
    local_transport_source = _heuristic_source(
        f"Estimativa heurística de transporte local: {DAILY_LOCAL_TRANSPORT_PER_PERSON} "
        f"{brief.display_currency}/pessoa/dia — não vem de um provedor específico."
    )
    sources.append(food_source)
    sources.append(local_transport_source)

    budget = calculate_budget(
        flights=flights_cost,
        accommodation=accommodation_cost,
        food=food_cost,
        activities=activities_cost,
        local_transport=local_transport_cost,
        stated_cap=brief.total_budget,
        tolerance=brief.budget_tolerance,
        currency=brief.display_currency,
        sources=[food_source, local_transport_source],
    )
    warnings.extend(budget.alerts)

    # Checklist prático (RF-27, RF-28)
    info = await tool_practical_info(
        ctx, destination=destination, nationality=brief.nationality, period=brief.reference_month
    )
    checklist = Checklist(**info["checklist"])
    if not is_international(destination, brief.budget_currency):
        checklist.entry_requirements = []

    if not flight_options:
        warnings.append("Sem origem informada, não foi possível estimar faixa de preço de voos.")
    if len(accommodation_options) < 3:
        warnings.append(
            f"Apenas {len(accommodation_options)} opções de hospedagem encontradas (recomendado: 3+)."
        )
    if len(flight_options) < 2 and flight_options:
        warnings.append("Apenas 1 opção de voo encontrada (recomendado: 2+).")

    summary = (
        f"Roteiro de {total_days} dia(s) para {destination}, partindo de {origin}, para "
        f"{brief.total_travelers} viajante(s). Orçamento total estimado: "
        f"{budget.total:.2f} {brief.display_currency}."
    )

    return TripPlan(
        brief=brief,
        summary=summary,
        flight_options=flight_options,
        accommodation_options=accommodation_options,
        itinerary=itinerary,
        meals=meals,
        budget=budget,
        exchange_rate=exchange_rate,
        checklist=checklist,
        sources=sources,
        warnings=list(dict.fromkeys(warnings)),
        generated_at=datetime.now(UTC),
    )
