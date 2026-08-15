import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { BriefPanel } from '../BriefPanel'
import type { TripBrief } from '../../api/types'

const EMPTY_BRIEF: TripBrief = {
  origin: null,
  destination: null,
  start_date: null,
  end_date: null,
  reference_month: null,
  duration_days: null,
  flexible_dates: false,
  adults: null,
  children_ages: [],
  total_budget: null,
  budget_currency: 'BRL',
  display_currency: 'BRL',
  budget_tolerance: 0.1,
  trip_type: null,
  interests: [],
  dietary_restrictions: [],
  mobility_restrictions: null,
  other_restrictions: [],
  pace: 'moderate',
  nationality: null,
  inferred_fields: [],
}

describe('BriefPanel', () => {
  it('lista número de viajantes como faltante quando adultos é null (RF-02)', () => {
    render(<BriefPanel brief={EMPTY_BRIEF} />)
    expect(screen.getByText(/número de viajantes/)).toBeInTheDocument()
  })

  it('mostra o painel completo (não recolhido) quando compact=false', () => {
    render(<BriefPanel brief={EMPTY_BRIEF} />)
    expect(screen.getByRole('heading', { name: 'Seu briefing' })).toBeInTheDocument()
  })

  it('RF-07: continua visível (só recolhido) quando compact=true, não desaparece', () => {
    const fullBrief: TripBrief = { ...EMPTY_BRIEF, destination: 'Lisboa', adults: 2 }
    render(<BriefPanel brief={fullBrief} compact />)
    expect(screen.getByText('Seu briefing')).toBeInTheDocument()
    expect(screen.getByText('Lisboa')).toBeInTheDocument()
  })
})
