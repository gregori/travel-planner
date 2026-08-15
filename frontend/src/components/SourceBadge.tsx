import type { Source } from '../api/types'

const LABELS: Record<Source['type'], string> = {
  real: 'Dado real',
  estimate: 'Estimativa',
  mock: 'Simulado',
}

export function SourceBadge({ source }: { source: Source | null | undefined }) {
  if (!source) return null
  return (
    <span className={`source-badge source-badge--${source.type}`} title={source.note ?? undefined}>
      {LABELS[source.type]}
    </span>
  )
}
