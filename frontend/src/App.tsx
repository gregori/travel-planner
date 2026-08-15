import { useCallback, useEffect, useRef, useState } from 'react'
import { createSession, sendMessage, getBrief, getPlan } from './api/client'
import type { ChatMessage, TripBrief, TripPlan } from './api/types'
import { Chat } from './components/Chat'
import { BriefPanel } from './components/BriefPanel'
import { PlanView } from './components/PlanView'
import './App.css'

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

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [ttlMinutes, setTtlMinutes] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [brief, setBrief] = useState<TripBrief>(EMPTY_BRIEF)
  const [plan, setPlan] = useState<TripPlan | null>(null)
  const [waiting, setWaiting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true
    ;(async () => {
      try {
        const session = await createSession()
        setSessionId(session.session_id)
        setTtlMinutes(session.ttl_minutes)
        const [currentBrief, currentPlan] = await Promise.all([
          getBrief(session.session_id),
          getPlan(session.session_id),
        ])
        setBrief(currentBrief)
        setPlan(currentPlan)
      } catch {
        setError('Não foi possível conectar ao servidor. Verifique se o backend está no ar.')
      }
    })()
  }, [])

  const handleSend = useCallback(
    async (text: string) => {
      if (!sessionId) return
      setError(null)
      setMessages((current) => [...current, { author: 'user', text }])
      setWaiting(true)
      try {
        let accumulatedResponse = ''
        let bubbleStarted = false
        for await (const event of sendMessage(sessionId, text)) {
          if (event.event === 'token') {
            // RF-06: cada pedaço chega e já é exibido, em vez de esperar a
            // resposta inteira para só então atualizar a tela.
            accumulatedResponse += event.data
            if (!bubbleStarted) {
              bubbleStarted = true
              setMessages((current) => [...current, { author: 'agent', text: accumulatedResponse }])
            } else {
              const currentText = accumulatedResponse
              setMessages((current) => {
                const copy = [...current]
                copy[copy.length - 1] = { author: 'agent', text: currentText }
                return copy
              })
            }
          } else if (event.event === 'brief_update') {
            setBrief(event.data)
          } else if (event.event === 'plan_ready') {
            setPlan(event.data)
          } else if (event.event === 'error') {
            setError(event.data.message)
          }
        }
      } catch {
        setError('A conversa foi interrompida. Tente novamente.')
      } finally {
        setWaiting(false)
      }
    },
    [sessionId],
  )

  return (
    <div className="app">
      <header className="app__header">
        <h1>Travel Planner</h1>
        <p>Planeje sua viagem em uma conversa — roteiro, orçamento e reservas comparadas.</p>
        {ttlMinutes !== null && (
          <p className="app__ttl-notice" role="note">
            Esta sessão não é salva: expira em {ttlMinutes} min de inatividade. Exporte seu plano
            assim que estiver pronto para não perdê-lo.
          </p>
        )}
      </header>

      {error && (
        <div className="app__error" role="alert">
          {error}
        </div>
      )}

      <main className="app__main">
        <Chat messages={messages} waiting={waiting} onSend={handleSend} />
        <div className="app__sidebar">
          {/* RF-07: o briefing continua visível e atualizado mesmo depois do
              plano pronto — não é substituído pelo roteiro. */}
          <BriefPanel brief={brief} compact={plan !== null} />
          {plan && sessionId && <PlanView plan={plan} sessionId={sessionId} />}
        </div>
      </main>
    </div>
  )
}
