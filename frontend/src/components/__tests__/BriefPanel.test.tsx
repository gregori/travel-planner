import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { BriefPanel } from '../BriefPanel'
import type { TripBrief } from '../../api/types'

const BRIEF_VAZIO: TripBrief = {
  origem: null,
  destino: null,
  data_ida: null,
  data_volta: null,
  mes_referencia: null,
  duracao_dias: null,
  datas_flexiveis: false,
  adultos: null,
  criancas_idades: [],
  orcamento_total: null,
  moeda_orcamento: 'BRL',
  moeda_exibicao: 'BRL',
  tolerancia_orcamento: 0.1,
  tipo_viagem: null,
  interesses: [],
  restricoes_alimentares: [],
  restricoes_mobilidade: null,
  outras_restricoes: [],
  ritmo: 'moderado',
  nacionalidade: null,
  campos_inferidos: [],
}

describe('BriefPanel', () => {
  it('lista número de viajantes como faltante quando adultos é null (RF-02)', () => {
    render(<BriefPanel brief={BRIEF_VAZIO} />)
    expect(screen.getByText(/número de viajantes/)).toBeInTheDocument()
  })

  it('mostra o painel completo (não recolhido) quando compacto=false', () => {
    render(<BriefPanel brief={BRIEF_VAZIO} />)
    expect(screen.getByRole('heading', { name: 'Seu briefing' })).toBeInTheDocument()
  })

  it('RF-07: continua visível (só recolhido) quando compacto=true, não desaparece', () => {
    const briefCompleto: TripBrief = { ...BRIEF_VAZIO, destino: 'Lisboa', adultos: 2 }
    render(<BriefPanel brief={briefCompleto} compacto />)
    expect(screen.getByText('Seu briefing')).toBeInTheDocument()
    expect(screen.getByText('Lisboa')).toBeInTheDocument()
  })
})
