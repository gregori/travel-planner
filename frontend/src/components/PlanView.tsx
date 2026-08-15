import type { Source, TripPlan } from '../api/types'
import { SourceBadge } from './SourceBadge'
import { ExportButtons } from './ExportButtons'

function fmt(value: string, currency: string) {
  const n = Number(value)
  return `${n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString('pt-BR')
}

interface SourceRow {
  item: string
  value: string
  source: Source
}

/** Espelha `build_source_rows` do backend (app/export/markdown.py):
 * liga cada preço exibido à sua Source, em vez de listar `plan.sources` "solta"
 * sem dizer a que item cada uma se refere (RF-32). */
function buildSourceRows(plan: TripPlan): SourceRow[] {
  const rows: SourceRow[] = []
  for (const v of plan.flight_options) {
    rows.push({
      item: `Voo ${v.airline} (${v.origin} → ${v.destination})`,
      value: `${fmt(v.min_price, v.currency)} a ${fmt(v.max_price, v.currency)}`,
      source: v.source,
    })
  }
  for (const h of plan.accommodation_options) {
    rows.push({
      item: `Hospedagem: ${h.name}`,
      value: `${fmt(h.price_per_night, h.currency)}/noite`,
      source: h.source,
    })
  }
  for (const r of plan.meals) {
    rows.push({ item: `Restaurante: ${r.name}`, value: r.price_range ?? '—', source: r.source })
  }
  for (const day of plan.itinerary) {
    for (const a of [...day.morning, ...day.afternoon, ...day.evening]) {
      if (Number(a.estimated_cost) > 0 && a.source) {
        rows.push({
          item: `Atividade: ${a.title} (dia ${day.day})`,
          value: fmt(a.estimated_cost, a.currency),
          source: a.source,
        })
      }
    }
  }
  const currency = plan.brief.display_currency
  for (const s of plan.budget.sources) {
    const text = (s.note ?? '').toLowerCase()
    if (text.includes('aliment')) {
      rows.push({ item: 'Alimentação (estimativa)', value: fmt(plan.budget.food, currency), source: s })
    } else if (text.includes('transporte')) {
      rows.push({
        item: 'Transporte local (estimativa)',
        value: fmt(plan.budget.local_transport, currency),
        source: s,
      })
    } else {
      rows.push({ item: 'Estimativa heurística de orçamento', value: '—', source: s })
    }
  }
  if (plan.exchange_rate) {
    rows.push({
      item: `Câmbio ${plan.exchange_rate.source_currency} → ${plan.exchange_rate.target_currency}`,
      value: Number(plan.exchange_rate.rate).toFixed(4),
      source: plan.exchange_rate.source,
    })
  }
  return rows
}

export function PlanView({ plan, sessionId }: { plan: TripPlan; sessionId: string }) {
  const currency = plan.brief.display_currency

  return (
    <section className="panel plan" aria-label="Roteiro de viagem">
      <div className="plan__header">
        <h2>Seu roteiro</h2>
        <ExportButtons sessionId={sessionId} />
      </div>
      <p className="plan__summary">{plan.summary}</p>

      {plan.warnings.length > 0 && (
        <ul className="warnings" aria-label="Avisos do plano">
          {plan.warnings.map((a, i) => (
            <li key={i}>⚠️ {a}</li>
          ))}
        </ul>
      )}

      <details open>
        <summary>Opções de voo</summary>
        {plan.flight_options.length === 0 ? (
          <p className="empty">Informe a origem para estimarmos o preço dos voos.</p>
        ) : (
          <ul className="cards">
            {plan.flight_options.map((v, i) => (
              <li key={i} className={`card ${v.recommended ? 'card--recommended' : ''}`}>
                <div className="card__top">
                  <strong>{v.airline}</strong>
                  <SourceBadge source={v.source} />
                </div>
                <p>
                  {v.origin} → {v.destination} · {fmt(v.min_price, v.currency)} a {fmt(v.max_price, v.currency)}
                </p>
                <p className="detail">{v.stops === 0 ? 'Sem escalas' : `${v.stops} escala(s)`}</p>
                {v.link && (
                  <a href={v.link} target="_blank" rel="noreferrer">
                    Comparar preços
                  </a>
                )}
                {v.rationale && <p className="rationale">{v.rationale}</p>}
              </li>
            ))}
          </ul>
        )}
      </details>

      <details open>
        <summary>Opções de hospedagem</summary>
        <ul className="cards">
          {plan.accommodation_options.map((h, i) => (
            <li key={i} className={`card ${h.recommended ? 'card--recommended' : ''}`}>
              <div className="card__top">
                <strong>{h.name}</strong>
                <SourceBadge source={h.source} />
              </div>
              <p>
                {h.type} · {fmt(h.price_per_night, h.currency)}/noite · {h.location}
              </p>
              {h.link && (
                <a href={h.link} target="_blank" rel="noreferrer">
                  Ver oferta
                </a>
              )}
              {h.rationale && <p className="rationale">{h.rationale}</p>}
            </li>
          ))}
        </ul>
      </details>

      <details open>
        <summary>Itinerário dia a dia</summary>
        <ol className="itinerary">
          {plan.itinerary.map((day) => (
            <li key={day.day} className="day">
              <h3>
                Dia {day.day}
                {day.date ? ` — ${day.date}` : ''} · {day.region}
              </h3>
              {day.note && <p className="detail">{day.note}</p>}
              {(['morning', 'afternoon', 'evening'] as const).map((block) => (
                <div key={block} className="block">
                  <span className="block__title">
                    {block === 'morning' ? 'Manhã' : block === 'afternoon' ? 'Tarde' : 'Noite'}
                  </span>
                  {day[block].length === 0 ? (
                    <span className="empty">Livre</span>
                  ) : (
                    <ul>
                      {day[block].map((a, i) => (
                        <li key={i}>
                          {a.title}
                          {Number(a.estimated_cost) > 0 && ` (${fmt(a.estimated_cost, a.currency)})`}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
              <p className="detail">Custo estimado do dia: {fmt(day.estimated_day_cost, currency)}</p>
            </li>
          ))}
        </ol>
      </details>

      <details open>
        <summary>Restaurantes sugeridos</summary>
        {plan.meals.length === 0 ? (
          <p className="empty">Nenhuma sugestão encontrada para os critérios informados.</p>
        ) : (
          <ul className="cards">
            {plan.meals.map((r, i) => (
              <li key={i} className="card">
                <div className="card__top">
                  <strong>{r.name}</strong>
                  <SourceBadge source={r.source} />
                </div>
                <p>
                  {r.meal_type} · {r.cuisine ?? 'culinária variada'}
                </p>
                <p className="rationale">{r.compatibility}</p>
              </li>
            ))}
          </ul>
        )}
      </details>

      <details open>
        <summary>Orçamento</summary>
        <table className="budget">
          <tbody>
            <tr>
              <td>Voos</td>
              <td>{fmt(plan.budget.flights, currency)}</td>
            </tr>
            <tr>
              <td>Hospedagem</td>
              <td>{fmt(plan.budget.accommodation, currency)}</td>
            </tr>
            <tr>
              <td>Alimentação (estimativa)</td>
              <td>{fmt(plan.budget.food, currency)}</td>
            </tr>
            <tr>
              <td>Passeios</td>
              <td>{fmt(plan.budget.activities, currency)}</td>
            </tr>
            <tr>
              <td>Transporte local (estimativa)</td>
              <td>{fmt(plan.budget.local_transport, currency)}</td>
            </tr>
            <tr>
              <td>Contingência</td>
              <td>{fmt(plan.budget.contingency, currency)}</td>
            </tr>
            <tr className="budget__total">
              <td>Total</td>
              <td>{fmt(plan.budget.total, currency)}</td>
            </tr>
          </tbody>
        </table>
        {plan.budget.stated_cap && (
          <p className={plan.budget.within_cap ? 'within-cap' : 'over-cap'}>
            Teto informado: {fmt(plan.budget.stated_cap, currency)} —{' '}
            {plan.budget.within_cap ? 'dentro do teto' : 'acima do teto'}
          </p>
        )}
        {plan.budget.alerts.map((a, i) => (
          <p key={i} className="warnings">
            ⚠️ {a}
          </p>
        ))}
      </details>

      {plan.exchange_rate && (
        <details>
          <summary>Câmbio</summary>
          <p>
            1 {plan.exchange_rate.source_currency} = {Number(plan.exchange_rate.rate).toFixed(4)}{' '}
            {plan.exchange_rate.target_currency} <SourceBadge source={plan.exchange_rate.source} />
          </p>
          <p className="detail">Consultado em {fmtDate(plan.exchange_rate.source.retrieved_at)}</p>
        </details>
      )}

      <details>
        <summary>Checklist prático</summary>
        <ul className="checklist">
          {plan.checklist.documents.map((d, i) => (
            <li key={`doc-${i}`}>{d}</li>
          ))}
        </ul>
        {plan.checklist.entry_requirements.length > 0 && (
          <>
            <h4>Requisitos de entrada</h4>
            <ul className="checklist">
              {plan.checklist.entry_requirements.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </>
        )}
        {plan.checklist.weather && <p>{plan.checklist.weather}</p>}
        {plan.checklist.power_outlet && <p>{plan.checklist.power_outlet}</p>}
      </details>

      <details>
        <summary>Fontes e confiabilidade</summary>
        <table className="sources">
          <thead>
            <tr>
              <th>Item</th>
              <th>Valor</th>
              <th>Tipo</th>
              <th>Confiança</th>
              <th>Consultado em</th>
            </tr>
          </thead>
          <tbody>
            {buildSourceRows(plan).map((row, i) => (
              <tr key={i}>
                <td>{row.item}</td>
                <td>{row.value}</td>
                <td>
                  <SourceBadge source={row.source} />
                </td>
                <td>{row.source.confidence}</td>
                <td>{fmtDate(row.source.retrieved_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>

      <p className="legal-footer">
        Os preços apresentados são estimativas sujeitas a variação. Este sistema não realiza
        reservas nem processa pagamentos.
      </p>
    </section>
  )
}
