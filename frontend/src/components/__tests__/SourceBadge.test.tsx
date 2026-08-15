import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SourceBadge } from '../SourceBadge'
import type { Source } from '../../api/types'

function source(type: Source['type']): Source {
  return {
    type,
    provider: 'fixture',
    url: null,
    retrieved_at: '2026-01-01T00:00:00Z',
    confidence: 'low',
    note: null,
  }
}

describe('SourceBadge', () => {
  it('distingue visualmente real, estimate e mock (RNF-01)', () => {
    const { rerender } = render(<SourceBadge source={source('real')} />)
    expect(screen.getByText('Dado real')).toBeInTheDocument()

    rerender(<SourceBadge source={source('estimate')} />)
    expect(screen.getByText('Estimativa')).toBeInTheDocument()

    rerender(<SourceBadge source={source('mock')} />)
    expect(screen.getByText('Simulado')).toBeInTheDocument()
  })

  it('não renderiza nada quando não há source', () => {
    const { container } = render(<SourceBadge source={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
