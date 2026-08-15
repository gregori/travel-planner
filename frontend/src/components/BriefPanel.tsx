import type { TripBrief } from '../api/types'

const RÓTULOS_TIPO_VIAGEM: Record<string, string> = {
  passeio: 'Passeio',
  romantica: 'Romântica',
  familia: 'Família',
  aventura: 'Aventura',
  cultural: 'Cultural',
  descanso: 'Descanso',
}

function Campo({ label, valor }: { label: string; valor: string | null | undefined }) {
  if (!valor) return null
  return (
    <div className="brief-field">
      <span className="brief-field__label">{label}</span>
      <span className="brief-field__valor">{valor}</span>
    </div>
  )
}

export function BriefPanel({ brief }: { brief: TripBrief }) {
  const periodo = brief.data_ida && brief.data_volta
    ? `${brief.data_ida} → ${brief.data_volta}`
    : brief.mes_referencia && brief.duracao_dias
      ? `${brief.mes_referencia} · ${brief.duracao_dias} dia(s)`
      : null

  const viajantes = brief.adultos || brief.criancas_idades.length
    ? `${brief.adultos} adulto(s)` +
      (brief.criancas_idades.length ? ` + ${brief.criancas_idades.length} criança(s)` : '')
    : null

  const faltantes = camposFaltantes(brief)

  return (
    <section className="panel" aria-label="Resumo da viagem">
      <h2>Seu briefing</h2>
      <div className="brief-grid">
        <Campo label="Origem" valor={brief.origem} />
        <Campo label="Destino" valor={brief.destino} />
        <Campo label="Período" valor={periodo} />
        <Campo label="Viajantes" valor={viajantes} />
        <Campo
          label="Orçamento"
          valor={brief.orcamento_total ? `${brief.orcamento_total} ${brief.moeda_orcamento}` : null}
        />
        <Campo label="Tipo de viagem" valor={brief.tipo_viagem ? RÓTULOS_TIPO_VIAGEM[brief.tipo_viagem] : null} />
        <Campo label="Ritmo" valor={brief.ritmo} />
        {brief.restricoes_alimentares.length > 0 && (
          <Campo label="Restrições alimentares" valor={brief.restricoes_alimentares.join(', ')} />
        )}
      </div>

      {brief.campos_inferidos.length > 0 && (
        <p className="brief-inferidos">
          <strong>Inferido automaticamente:</strong> {brief.campos_inferidos.join(', ')}
        </p>
      )}

      {faltantes.length > 0 && (
        <p className="brief-faltantes">
          Ainda faltam: <strong>{faltantes.join(', ')}</strong>
        </p>
      )}
    </section>
  )
}

function camposFaltantes(brief: TripBrief): string[] {
  const faltantes: string[] = []
  if (!brief.destino) faltantes.push('destino')
  const temDatas = brief.data_ida && brief.data_volta
  const temMes = brief.mes_referencia && brief.duracao_dias
  if (!temDatas && !temMes) faltantes.push('datas (ou mês + duração)')
  if (!brief.orcamento_total) faltantes.push('orçamento')
  return faltantes
}
