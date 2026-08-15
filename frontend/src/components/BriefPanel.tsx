import type { TripBrief } from '../api/types'

const TRIP_TYPE_LABELS: Record<string, string> = {
  sightseeing: 'Passeio',
  romantic: 'Romântica',
  family: 'Família',
  adventure: 'Aventura',
  cultural: 'Cultural',
  relaxation: 'Descanso',
}

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null
  return (
    <div className="brief-field">
      <span className="brief-field__label">{label}</span>
      <span className="brief-field__value">{value}</span>
    </div>
  )
}

/** RF-07: painel de briefing, atualizado a cada turno. Quando `compact` é
 * true (plano já pronto), fica recolhido por padrão para não competir com o
 * roteiro, mas continua acessível e atualizado — não desaparece. */
export function BriefPanel({ brief, compact = false }: { brief: TripBrief; compact?: boolean }) {
  const period = brief.start_date && brief.end_date
    ? `${brief.start_date} → ${brief.end_date}`
    : brief.reference_month && brief.duration_days
      ? `${brief.reference_month} · ${brief.duration_days} dia(s)`
      : null

  const travelers = brief.adults || brief.children_ages.length
    ? `${brief.adults ?? '?'} adulto(s)` +
      (brief.children_ages.length ? ` + ${brief.children_ages.length} criança(s)` : '')
    : null

  const missing = missingFields(brief)

  const content = (
    <>
      <div className="brief-grid">
        <Field label="Origem" value={brief.origin} />
        <Field label="Destino" value={brief.destination} />
        <Field label="Período" value={period} />
        <Field label="Viajantes" value={travelers} />
        <Field
          label="Orçamento"
          value={brief.total_budget ? `${brief.total_budget} ${brief.budget_currency}` : null}
        />
        <Field label="Tipo de viagem" value={brief.trip_type ? TRIP_TYPE_LABELS[brief.trip_type] : null} />
        <Field label="Ritmo" value={brief.pace} />
        {brief.dietary_restrictions.length > 0 && (
          <Field label="Restrições alimentares" value={brief.dietary_restrictions.join(', ')} />
        )}
      </div>

      {brief.inferred_fields.length > 0 && (
        <p className="brief-inferred">
          <strong>Inferido automaticamente:</strong> {brief.inferred_fields.join(', ')}
        </p>
      )}

      {missing.length > 0 && (
        <p className="brief-missing">
          Ainda faltam: <strong>{missing.join(', ')}</strong>
        </p>
      )}
    </>
  )

  if (compact) {
    return (
      <details className="panel brief-panel--compact" aria-label="Resumo da viagem">
        <summary>Seu briefing</summary>
        {content}
      </details>
    )
  }

  return (
    <section className="panel" aria-label="Resumo da viagem">
      <h2>Seu briefing</h2>
      {content}
    </section>
  )
}

function missingFields(brief: TripBrief): string[] {
  const missing: string[] = []
  if (!brief.destination) missing.push('destino')
  const hasDates = brief.start_date && brief.end_date
  const hasMonth = brief.reference_month && brief.duration_days
  if (!hasDates && !hasMonth) missing.push('datas (ou mês + duração)')
  if (brief.adults === null) missing.push('número de viajantes')
  if (!brief.total_budget) missing.push('orçamento')
  return missing
}
