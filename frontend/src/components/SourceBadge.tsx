import type { Fonte } from '../api/types'

const RÓTULOS: Record<Fonte['tipo'], string> = {
  real: 'Dado real',
  estimativa: 'Estimativa',
  mock: 'Simulado',
}

export function SourceBadge({ fonte }: { fonte: Fonte | null | undefined }) {
  if (!fonte) return null
  return (
    <span className={`source-badge source-badge--${fonte.tipo}`} title={fonte.observacao ?? undefined}>
      {RÓTULOS[fonte.tipo]}
    </span>
  )
}
