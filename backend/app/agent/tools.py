import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from app.agent.budget import calculate_budget
from app.agent.cache import cache_key, cached_call
from app.config import Settings
from app.geo import heuristic_weather_description, is_international, outlet_for_destination
from app.models.common import Source
from app.providers.base import (
    AccommodationCriteria,
    AttractionsCriteria,
    ExchangeCriteria,
    FlightCriteria,
    RestaurantsCriteria,
)
from app.providers.registry import ProviderRegistry
from app.session.store import SessionState


@dataclass
class AgentContext:
    session: SessionState
    registry: ProviderRegistry
    settings: Settings


def _slug(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().strip().lower()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


async def tool_update_brief(ctx: AgentContext, **fields: Any) -> dict:
    ctx.session.brief = ctx.session.brief.merge(**fields).with_default_inferences()
    return {
        "brief": ctx.session.brief.model_dump(mode="json"),
        "missing_fields": ctx.session.brief.missing_fields(),
        "ready_to_plan": ctx.session.brief.ready_to_plan(),
    }


async def _with_count_and_cache(ctx: AgentContext, key: str, produce):
    """Envolve uma busca de provedor com cache por sessão (RF-17) e conta a
    chamada contra o teto por sessão (RNF-08) — usado tanto pelas ferramentas
    expostas ao LLM quanto pelo pipeline determinístico do planner, para que
    ambos os caminhos respeitem o mesmo orçamento de chamadas."""
    ctx.session.tool_calls_made += 1
    return await cached_call(ctx.session, key, ctx.settings.cache_ttl_minutes, produce)


async def search_accommodation_cached(
    ctx: AgentContext,
    city: str,
    check_in: date | None,
    check_out: date | None,
    guests: int,
    warnings: list[str],
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
):
    criteria = AccommodationCriteria(
        city=city,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        min_price=min_price,
        max_price=max_price,
        currency=ctx.session.brief.display_currency,
    )
    key = cache_key(
        "search_accommodation", city=_slug(city), check_in=str(check_in), check_out=str(check_out)
    )
    return await _with_count_and_cache(
        ctx, key, lambda: ctx.registry.search_accommodation(criteria, warnings)
    )


async def search_attractions_cached(
    ctx: AgentContext, city: str, interests: list[str], profile: str, warnings: list[str]
):
    criteria = AttractionsCriteria(city=city, interests=interests, profile=profile)
    key = cache_key("search_attractions", city=_slug(city), interests=sorted(interests))
    return await _with_count_and_cache(ctx, key, lambda: ctx.registry.search_attractions(criteria, warnings))


async def search_restaurants_cached(
    ctx: AgentContext, city: str, restrictions: list[str], warnings: list[str], price_range: str | None = None
):
    criteria = RestaurantsCriteria(city=city, restrictions=restrictions, price_range=price_range)
    key = cache_key("search_restaurants", city=_slug(city), restrictions=sorted(restrictions))
    return await _with_count_and_cache(ctx, key, lambda: ctx.registry.search_restaurants(criteria, warnings))


async def estimate_flights_cached(
    ctx: AgentContext,
    origin: str,
    destination: str,
    departure_date: date | None,
    return_date: date | None,
    passengers: int,
    warnings: list[str],
):
    criteria = FlightCriteria(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        passengers=passengers,
        currency=ctx.session.brief.display_currency,
    )
    key = cache_key("estimate_flights", origin=_slug(origin), destination=_slug(destination))
    return await _with_count_and_cache(ctx, key, lambda: ctx.registry.estimate_flights(criteria, warnings))


async def get_exchange_rate_cached(
    ctx: AgentContext, source_currency: str, target_currency: str, warnings: list[str]
):
    criteria = ExchangeCriteria(source_currency=source_currency, target_currency=target_currency)
    key = cache_key("get_exchange_rate", source_currency=source_currency, target_currency=target_currency)
    return await _with_count_and_cache(ctx, key, lambda: ctx.registry.get_exchange_rate(criteria, warnings))


async def tool_search_accommodation(
    ctx: AgentContext,
    city: str,
    check_in: str | None = None,
    check_out: str | None = None,
    guests: int = 1,
    min_price: float | None = None,
    max_price: float | None = None,
) -> dict:
    warnings: list[str] = []
    result = await search_accommodation_cached(
        ctx,
        city,
        _parse_date(check_in),
        _parse_date(check_out),
        guests,
        warnings,
        Decimal(str(min_price)) if min_price is not None else None,
        Decimal(str(max_price)) if max_price is not None else None,
    )
    return {
        "options": [o.model_dump(mode="json") for o in result.items],
        "empty_reason": result.empty_reason,
        "warnings": warnings,
    }


async def tool_search_attractions(
    ctx: AgentContext,
    city: str,
    interests: list[str] | None = None,
    profile: str = "geral",
) -> dict:
    warnings: list[str] = []
    result = await search_attractions_cached(ctx, city, interests or [], profile, warnings)
    return {
        "attractions": [a.model_dump(mode="json") for a in result.items],
        "empty_reason": result.empty_reason,
        "warnings": warnings,
    }


async def tool_search_restaurants(
    ctx: AgentContext,
    city: str,
    restrictions: list[str] | None = None,
    price_range: str | None = None,
) -> dict:
    warnings: list[str] = []
    result = await search_restaurants_cached(ctx, city, restrictions or [], warnings, price_range)
    return {
        "restaurants": [r.model_dump(mode="json") for r in result.items],
        "empty_reason": result.empty_reason,
        "warnings": warnings,
    }


async def tool_estimate_flights(
    ctx: AgentContext,
    origin: str,
    destination: str,
    departure_date: str | None = None,
    return_date: str | None = None,
    passengers: int = 1,
) -> dict:
    warnings: list[str] = []
    result = await estimate_flights_cached(
        ctx, origin, destination, _parse_date(departure_date), _parse_date(return_date), passengers, warnings
    )
    return {
        "options": [o.model_dump(mode="json") for o in result.items],
        "empty_reason": result.empty_reason,
        "warnings": warnings,
    }


async def tool_get_exchange_rate(ctx: AgentContext, source_currency: str, target_currency: str) -> dict:
    warnings: list[str] = []
    rate = await get_exchange_rate_cached(ctx, source_currency, target_currency, warnings)
    if rate is None:
        return {"rate": None, "empty_reason": "Par de moedas não suportado.", "warnings": warnings}
    return {"rate": rate.model_dump(mode="json"), "empty_reason": None, "warnings": warnings}


async def tool_practical_info(
    ctx: AgentContext,
    destination: str,
    nationality: str | None = None,
    period: str | None = None,
) -> dict:
    """Checklist prático: clima, documentação, tomada/adaptador, moeda (RF-27/28).

    Heurística leve e sempre rotulada como estimativa — nunca dado oficial.
    """
    international = is_international(destination, ctx.session.brief.budget_currency)
    entry_requirements: list[str] = []
    if international:
        entry_requirements = [
            f"Verifique exigência de visto/autorização de viagem para {nationality or 'sua nacionalidade'} "
            f"rumo a {destination} na fonte oficial do consulado/imigração antes de comprar passagens.",
            "Confirme validade mínima do passaporte exigida pelo país de destino (geralmente 6 meses).",
        ]
    source = Source(
        type="estimate",
        provider="web",
        url=None,
        retrieved_at=datetime.now(UTC),
        confidence="low",
        note="Informação heurística geral; sempre confirme em fonte oficial antes da viagem.",
    )
    base_documents = ["Reserva de hospedagem impressa/digital"]
    base_documents += (
        ["Passaporte válido", "Verificar exigência de visto"]
        if international
        else ["Documento de identidade com foto"]
    )
    month_number = ctx.session.brief.start_date.month if ctx.session.brief.start_date else None
    checklist = {
        "documents": base_documents,
        "weather": heuristic_weather_description(destination, period, month_number),
        "currency_and_exchange": ctx.session.brief.display_currency,
        "power_outlet": f"Padrão local: {outlet_for_destination(destination)}. Leve adaptador universal.",
        "what_to_pack": [
            "Adaptador de tomada",
            "Medicamentos de uso pessoal",
            "Cópia de documentos",
        ],
        "entry_requirements": entry_requirements,
    }
    return {"checklist": checklist, "source": source.model_dump(mode="json")}


async def tool_calculate_budget(
    ctx: AgentContext,
    flights: float = 0,
    accommodation: float = 0,
    food: float = 0,
    activities: float = 0,
    local_transport: float = 0,
    stated_cap: float | None = None,
) -> dict:
    budget = calculate_budget(
        flights=Decimal(str(flights)),
        accommodation=Decimal(str(accommodation)),
        food=Decimal(str(food)),
        activities=Decimal(str(activities)),
        local_transport=Decimal(str(local_transport)),
        stated_cap=Decimal(str(stated_cap)) if stated_cap is not None else (ctx.session.brief.total_budget),
        tolerance=ctx.session.brief.budget_tolerance,
    )
    return {"budget": budget.model_dump(mode="json")}


TOOL_HANDLERS = {
    "update_brief": tool_update_brief,
    "search_accommodation": tool_search_accommodation,
    "search_attractions": tool_search_attractions,
    "search_restaurants": tool_search_restaurants,
    "estimate_flights": tool_estimate_flights,
    "get_exchange_rate": tool_get_exchange_rate,
    "practical_info": tool_practical_info,
    "calculate_budget": tool_calculate_budget,
}


TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "update_brief",
            "description": "Atualiza o TripBrief com os campos que o usuário informou nesta mensagem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string"},
                    "destination": {"type": "string"},
                    "start_date": {"type": "string", "format": "date"},
                    "end_date": {"type": "string", "format": "date"},
                    "reference_month": {"type": "string"},
                    "duration_days": {"type": "integer"},
                    "flexible_dates": {"type": "boolean"},
                    "adults": {"type": "integer"},
                    "children_ages": {"type": "array", "items": {"type": "integer"}},
                    "total_budget": {"type": "number"},
                    "budget_currency": {"type": "string"},
                    "display_currency": {"type": "string"},
                    "trip_type": {
                        "type": "string",
                        "enum": [
                            "sightseeing",
                            "romantic",
                            "family",
                            "adventure",
                            "cultural",
                            "relaxation",
                        ],
                    },
                    "interests": {"type": "array", "items": {"type": "string"}},
                    "dietary_restrictions": {"type": "array", "items": {"type": "string"}},
                    "mobility_restrictions": {"type": "string"},
                    "other_restrictions": {"type": "array", "items": {"type": "string"}},
                    "pace": {"type": "string", "enum": ["light", "moderate", "intense"]},
                    "nationality": {"type": "string"},
                    "inferred_fields": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_accommodation",
            "description": "Busca opções de hospedagem no destino.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "check_in": {"type": "string", "format": "date"},
                    "check_out": {"type": "string", "format": "date"},
                    "guests": {"type": "integer"},
                    "min_price": {"type": "number"},
                    "max_price": {"type": "number"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_attractions",
            "description": "Busca atrações e passeios compatíveis com os interesses do viajante.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "interests": {"type": "array", "items": {"type": "string"}},
                    "profile": {"type": "string"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_restaurants",
            "description": "Busca restaurantes respeitando restrições alimentares.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "restrictions": {"type": "array", "items": {"type": "string"}},
                    "price_range": {"type": "string"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estimate_flights",
            "description": "Estima faixa de preço de voos por rota e época (nunca valor único).",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string"},
                    "destination": {"type": "string"},
                    "departure_date": {"type": "string", "format": "date"},
                    "return_date": {"type": "string", "format": "date"},
                    "passengers": {"type": "integer"},
                },
                "required": ["origin", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_exchange_rate",
            "description": "Cota câmbio entre duas moedas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_currency": {"type": "string"},
                    "target_currency": {"type": "string"},
                },
                "required": ["source_currency", "target_currency"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "practical_info",
            "description": "Retorna clima, documentação, tomada/adaptador e moeda para o destino.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string"},
                    "nationality": {"type": "string"},
                    "period": {"type": "string"},
                },
                "required": ["destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_budget",
            "description": "Calcula o orçamento por categoria, com contingência e alertas de estouro.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flights": {"type": "number"},
                    "accommodation": {"type": "number"},
                    "food": {"type": "number"},
                    "activities": {"type": "number"},
                    "local_transport": {"type": "number"},
                    "stated_cap": {"type": "number"},
                },
            },
        },
    },
]
