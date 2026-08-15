import type { TripPlan } from '../api/types'
import { SourceBadge } from './SourceBadge'
import { ExportButtons } from './ExportButtons'

function fmt(valor: string, moeda: string) {
  const n = Number(valor)
  return `${n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${moeda}`
}

export function PlanView({ plan, sessionId }: { plan: TripPlan; sessionId: string }) {
  const moeda = plan.brief.moeda_exibicao

  return (
    <section className="panel plan" aria-label="Roteiro de viagem">
      <div className="plan__cabecalho">
        <h2>Seu roteiro</h2>
        <ExportButtons sessionId={sessionId} />
      </div>
      <p className="plan__resumo">{plan.resumo}</p>

      {plan.avisos.length > 0 && (
        <ul className="avisos" aria-label="Avisos do plano">
          {plan.avisos.map((a, i) => (
            <li key={i}>⚠️ {a}</li>
          ))}
        </ul>
      )}

      <details open>
        <summary>Opções de voo</summary>
        {plan.opcoes_voo.length === 0 ? (
          <p className="vazio">Informe a origem para estimarmos o preço dos voos.</p>
        ) : (
          <ul className="cartoes">
            {plan.opcoes_voo.map((v, i) => (
              <li key={i} className={`cartao ${v.recomendada ? 'cartao--recomendada' : ''}`}>
                <div className="cartao__topo">
                  <strong>{v.companhia}</strong>
                  <SourceBadge fonte={v.fonte} />
                </div>
                <p>
                  {v.origem} → {v.destino} · {fmt(v.preco_min, v.moeda)} a {fmt(v.preco_max, v.moeda)}
                </p>
                <p className="detalhe">{v.escalas === 0 ? 'Sem escalas' : `${v.escalas} escala(s)`}</p>
                {v.justificativa && <p className="justificativa">{v.justificativa}</p>}
              </li>
            ))}
          </ul>
        )}
      </details>

      <details open>
        <summary>Opções de hospedagem</summary>
        <ul className="cartoes">
          {plan.opcoes_hospedagem.map((h, i) => (
            <li key={i} className={`cartao ${h.recomendada ? 'cartao--recomendada' : ''}`}>
              <div className="cartao__topo">
                <strong>{h.nome}</strong>
                <SourceBadge fonte={h.fonte} />
              </div>
              <p>
                {h.tipo} · {fmt(h.preco_por_noite, h.moeda)}/noite · {h.localizacao}
              </p>
              {h.link && (
                <a href={h.link} target="_blank" rel="noreferrer">
                  Ver oferta
                </a>
              )}
              {h.justificativa && <p className="justificativa">{h.justificativa}</p>}
            </li>
          ))}
        </ul>
      </details>

      <details open>
        <summary>Itinerário dia a dia</summary>
        <ol className="itinerario">
          {plan.itinerario.map((dia) => (
            <li key={dia.dia} className="dia">
              <h3>
                Dia {dia.dia}
                {dia.data ? ` — ${dia.data}` : ''} · {dia.regiao}
              </h3>
              {dia.observacao && <p className="detalhe">{dia.observacao}</p>}
              {(['manha', 'tarde', 'noite'] as const).map((bloco) => (
                <div key={bloco} className="bloco">
                  <span className="bloco__titulo">
                    {bloco === 'manha' ? 'Manhã' : bloco === 'tarde' ? 'Tarde' : 'Noite'}
                  </span>
                  {dia[bloco].length === 0 ? (
                    <span className="vazio">Livre</span>
                  ) : (
                    <ul>
                      {dia[bloco].map((a, i) => (
                        <li key={i}>
                          {a.titulo}
                          {Number(a.custo_estimado) > 0 && ` (${fmt(a.custo_estimado, moeda)})`}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
              <p className="detalhe">Custo estimado do dia: {fmt(dia.custo_estimado_dia, moeda)}</p>
            </li>
          ))}
        </ol>
      </details>

      <details open>
        <summary>Restaurantes sugeridos</summary>
        {plan.refeicoes.length === 0 ? (
          <p className="vazio">Nenhuma sugestão encontrada para os critérios informados.</p>
        ) : (
          <ul className="cartoes">
            {plan.refeicoes.map((r, i) => (
              <li key={i} className="cartao">
                <div className="cartao__topo">
                  <strong>{r.nome}</strong>
                  <SourceBadge fonte={r.fonte} />
                </div>
                <p>
                  {r.tipo_refeicao} · {r.culinaria ?? 'culinária variada'}
                </p>
                <p className="justificativa">{r.compatibilidade}</p>
              </li>
            ))}
          </ul>
        )}
      </details>

      <details open>
        <summary>Orçamento</summary>
        <table className="orcamento">
          <tbody>
            <tr>
              <td>Voos</td>
              <td>{fmt(plan.orcamento.voos, moeda)}</td>
            </tr>
            <tr>
              <td>Hospedagem</td>
              <td>{fmt(plan.orcamento.hospedagem, moeda)}</td>
            </tr>
            <tr>
              <td>Alimentação</td>
              <td>{fmt(plan.orcamento.alimentacao, moeda)}</td>
            </tr>
            <tr>
              <td>Passeios</td>
              <td>{fmt(plan.orcamento.passeios, moeda)}</td>
            </tr>
            <tr>
              <td>Transporte local</td>
              <td>{fmt(plan.orcamento.transporte_local, moeda)}</td>
            </tr>
            <tr>
              <td>Contingência</td>
              <td>{fmt(plan.orcamento.contingencia, moeda)}</td>
            </tr>
            <tr className="orcamento__total">
              <td>Total</td>
              <td>{fmt(plan.orcamento.total, moeda)}</td>
            </tr>
          </tbody>
        </table>
        {plan.orcamento.teto_informado && (
          <p className={plan.orcamento.dentro_do_teto ? 'dentro-teto' : 'fora-teto'}>
            Teto informado: {fmt(plan.orcamento.teto_informado, moeda)} —{' '}
            {plan.orcamento.dentro_do_teto ? 'dentro do teto' : 'acima do teto'}
          </p>
        )}
        {plan.orcamento.alertas.map((a, i) => (
          <p key={i} className="avisos">
            ⚠️ {a}
          </p>
        ))}
      </details>

      {plan.cambio && (
        <details>
          <summary>Câmbio</summary>
          <p>
            1 {plan.cambio.moeda_origem} = {Number(plan.cambio.taxa).toFixed(4)} {plan.cambio.moeda_destino}
            <SourceBadge fonte={plan.cambio.fonte} />
          </p>
        </details>
      )}

      <details>
        <summary>Checklist prático</summary>
        <ul className="checklist">
          {plan.checklist.documentos.map((d, i) => (
            <li key={`doc-${i}`}>{d}</li>
          ))}
        </ul>
        {plan.checklist.requisitos_entrada.length > 0 && (
          <>
            <h4>Requisitos de entrada</h4>
            <ul className="checklist">
              {plan.checklist.requisitos_entrada.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </>
        )}
        {plan.checklist.clima && <p>{plan.checklist.clima}</p>}
        {plan.checklist.tomada_adaptador && <p>{plan.checklist.tomada_adaptador}</p>}
      </details>

      <details>
        <summary>Fontes e confiabilidade</summary>
        <table className="fontes">
          <thead>
            <tr>
              <th>Item</th>
              <th>Tipo</th>
              <th>Confiança</th>
            </tr>
          </thead>
          <tbody>
            {plan.fontes.map((f, i) => (
              <tr key={i}>
                <td>{f.observacao ?? f.provedor}</td>
                <td>
                  <SourceBadge fonte={f} />
                </td>
                <td>{f.confianca}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>

      <p className="rodape-legal">
        Os preços apresentados são estimativas sujeitas a variação. Este sistema não realiza
        reservas nem processa pagamentos.
      </p>
    </section>
  )
}
