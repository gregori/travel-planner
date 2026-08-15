import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SourceBadge } from '../SourceBadge'
import type { Fonte } from '../../api/types'

function fonte(tipo: Fonte['tipo']): Fonte {
  return {
    tipo,
    provedor: 'fixture',
    url: null,
    consultado_em: '2026-01-01T00:00:00Z',
    confianca: 'baixa',
    observacao: null,
  }
}

describe('SourceBadge', () => {
  it('distingue visualmente real, estimativa e mock (RNF-01)', () => {
    const { rerender } = render(<SourceBadge fonte={fonte('real')} />)
    expect(screen.getByText('Dado real')).toBeInTheDocument()

    rerender(<SourceBadge fonte={fonte('estimativa')} />)
    expect(screen.getByText('Estimativa')).toBeInTheDocument()

    rerender(<SourceBadge fonte={fonte('mock')} />)
    expect(screen.getByText('Simulado')).toBeInTheDocument()
  })

  it('não renderiza nada quando não há fonte', () => {
    const { container } = render(<SourceBadge fonte={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
