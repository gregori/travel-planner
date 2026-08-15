import { useCallback, useEffect, useRef, useState } from 'react'
import { criarSessao, enviarMensagem, obterBriefing, obterPlano } from './api/client'
import type { ChatMessage, TripBrief, TripPlan } from './api/types'
import { Chat } from './components/Chat'
import { BriefPanel } from './components/BriefPanel'
import { PlanView } from './components/PlanView'
import './App.css'

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

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [ttlMinutos, setTtlMinutos] = useState<number | null>(null)
  const [mensagens, setMensagens] = useState<ChatMessage[]>([])
  const [brief, setBrief] = useState<TripBrief>(BRIEF_VAZIO)
  const [plan, setPlan] = useState<TripPlan | null>(null)
  const [aguardando, setAguardando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const iniciou = useRef(false)

  useEffect(() => {
    if (iniciou.current) return
    iniciou.current = true
    ;(async () => {
      try {
        const sessao = await criarSessao()
        setSessionId(sessao.session_id)
        setTtlMinutos(sessao.ttl_minutos)
        const [briefAtual, planoAtual] = await Promise.all([
          obterBriefing(sessao.session_id),
          obterPlano(sessao.session_id),
        ])
        setBrief(briefAtual)
        setPlan(planoAtual)
      } catch {
        setErro('Não foi possível conectar ao servidor. Verifique se o backend está no ar.')
      }
    })()
  }, [])

  const handleEnviar = useCallback(
    async (texto: string) => {
      if (!sessionId) return
      setErro(null)
      setMensagens((atual) => [...atual, { autor: 'usuario', texto }])
      setAguardando(true)
      try {
        let respostaAcumulada = ''
        let bolhaIniciada = false
        for await (const evento of enviarMensagem(sessionId, texto)) {
          if (evento.evento === 'token') {
            // RF-06: cada pedaço chega e já é exibido, em vez de esperar a
            // resposta inteira para só então atualizar a tela.
            respostaAcumulada += evento.dados
            if (!bolhaIniciada) {
              bolhaIniciada = true
              setMensagens((atual) => [...atual, { autor: 'agente', texto: respostaAcumulada }])
            } else {
              const textoAtual = respostaAcumulada
              setMensagens((atual) => {
                const copia = [...atual]
                copia[copia.length - 1] = { autor: 'agente', texto: textoAtual }
                return copia
              })
            }
          } else if (evento.evento === 'brief_update') {
            setBrief(evento.dados)
          } else if (evento.evento === 'plan_ready') {
            setPlan(evento.dados)
          } else if (evento.evento === 'error') {
            setErro(evento.dados.mensagem)
          }
        }
      } catch {
        setErro('A conversa foi interrompida. Tente novamente.')
      } finally {
        setAguardando(false)
      }
    },
    [sessionId],
  )

  return (
    <div className="app">
      <header className="app__header">
        <h1>Travel Planner</h1>
        <p>Planeje sua viagem em uma conversa — roteiro, orçamento e reservas comparadas.</p>
        {ttlMinutos !== null && (
          <p className="app__ttl-aviso" role="note">
            Esta sessão não é salva: expira em {ttlMinutos} min de inatividade. Exporte seu plano
            assim que estiver pronto para não perdê-lo.
          </p>
        )}
      </header>

      {erro && (
        <div className="app__erro" role="alert">
          {erro}
        </div>
      )}

      <main className="app__main">
        <Chat mensagens={mensagens} aguardando={aguardando} onEnviar={handleEnviar} />
        <div className="app__lateral">
          {/* RF-07: o briefing continua visível e atualizado mesmo depois do
              plano pronto — não é substituído pelo roteiro. */}
          <BriefPanel brief={brief} compacto={plan !== null} />
          {plan && sessionId && <PlanView plan={plan} sessionId={sessionId} />}
        </div>
      </main>
    </div>
  )
}
