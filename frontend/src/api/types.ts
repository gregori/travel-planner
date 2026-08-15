export type SourceType = 'real' | 'estimate' | 'mock'
export type ConfidenceLevel = 'high' | 'medium' | 'low'

export interface Source {
  type: SourceType
  provider: string
  url: string | null
  retrieved_at: string
  confidence: ConfidenceLevel
  note: string | null
}

export interface TripBrief {
  origin: string | null
  destination: string | null
  start_date: string | null
  end_date: string | null
  reference_month: string | null
  duration_days: number | null
  flexible_dates: boolean
  adults: number | null
  children_ages: number[]
  total_budget: string | null
  budget_currency: string
  display_currency: string
  budget_tolerance: number
  trip_type: string | null
  interests: string[]
  dietary_restrictions: string[]
  mobility_restrictions: string | null
  other_restrictions: string[]
  pace: 'light' | 'moderate' | 'intense'
  nationality: string | null
  inferred_fields: string[]
}

export interface Activity {
  title: string
  description: string | null
  region: string | null
  duration_min: number | null
  estimated_cost: string
  currency: string
  source: Source | null
  time_of_day: string | null
}

export interface Transfer {
  from_block: string
  to_block: string
  duration_min: number
  mode: string
}

export interface ItineraryDay {
  day: number
  date: string | null
  region: string
  morning: Activity[]
  afternoon: Activity[]
  evening: Activity[]
  transfers: Transfer[]
  estimated_day_cost: string
  note: string | null
}

export interface FlightOption {
  airline: string
  origin: string
  destination: string
  min_price: string
  max_price: string
  currency: string
  duration_hours: number | null
  stops: number
  link: string | null
  recommended: boolean
  rationale: string | null
  source: Source
}

export interface AccommodationOption {
  name: string
  type: string
  price_per_night: string
  currency: string
  location: string
  rating: number | null
  link: string | null
  recommended: boolean
  rationale: string | null
  source: Source
}

export interface MealSuggestion {
  name: string
  meal_type: string
  cuisine: string | null
  price_range: string | null
  compatibility: string
  location: string | null
  link: string | null
  source: Source
}

export interface Budget {
  flights: string
  accommodation: string
  food: string
  activities: string
  local_transport: string
  contingency: string
  total: string
  stated_cap: string | null
  difference: string | null
  within_cap: boolean
  alerts: string[]
  sources: Source[]
}

export interface ExchangeRate {
  source_currency: string
  target_currency: string
  rate: string
  source: Source
}

export interface Checklist {
  documents: string[]
  weather: string | null
  currency_and_exchange: string | null
  power_outlet: string | null
  what_to_pack: string[]
  entry_requirements: string[]
}

export interface TripPlan {
  brief: TripBrief
  summary: string
  flight_options: FlightOption[]
  accommodation_options: AccommodationOption[]
  itinerary: ItineraryDay[]
  meals: MealSuggestion[]
  budget: Budget
  exchange_rate: ExchangeRate | null
  checklist: Checklist
  sources: Source[]
  warnings: string[]
  generated_at: string
}

export interface ChatMessage {
  author: 'user' | 'agent'
  text: string
}

export interface ErrorResponse {
  error: {
    code: string
    message: string
    recoverable: boolean
  }
}
