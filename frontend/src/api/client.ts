import type { TripBrief, TripPlan } from './types'

// Em dev, fala direto com o backend (CORS liberado em app/main.py) em vez de
// passar pelo proxy do Vite: o http-proxy do Vite duplica o header
// `Connection` em respostas chunked, o que quebra o streaming SSE no
// Chromium. Em produção, aponte VITE_API_URL para a origem do backend.
const ORIGEM_API = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '')
const API_BASE = `${ORIGEM_API}/api`

export interface SessaoResposta {
  session_id: string
  ttl_minutos: number
}

export async function criarSessao(): Promise<SessaoResposta> {
  const resp = await fetch(`${API_BASE}/session`, { method: 'POST' })
  if (!resp.ok) throw new Error('Não foi possível criar a sessão.')
  return resp.json()
}

export async function obterBriefing(sessionId: string): Promise<TripBrief> {
  const resp = await fetch(`${API_BASE}/session/${sessionId}/brief`)
  if (!resp.ok) throw new Error('Não foi possível obter o briefing.')
  return resp.json()
}

export async function obterPlano(sessionId: string): Promise<TripPlan | null> {
  const resp = await fetch(`${API_BASE}/session/${sessionId}/plan`)
  if (resp.status === 409) return null
  if (!resp.ok) throw new Error('Não foi possível obter o plano.')
  return resp.json()
}

export function urlExportacao(sessionId: string, formato: 'md' | 'pdf'): string {
  return `${API_BASE}/session/${sessionId}/export?format=${formato}`
}

export type EventoChat =
  | { evento: 'token'; dados: string }
  | { evento: 'tool_call'; dados: { ferramenta: string; argumentos: Record<string, unknown> } }
  | { evento: 'brief_update'; dados: TripBrief }
  | { evento: 'plan_ready'; dados: TripPlan }
  | { evento: 'error'; dados: { codigo: string; mensagem: string } }
  | { evento: 'done'; dados: null }

/** Consome o SSE de /api/chat (RF-06) manualmente via fetch, pois EventSource
 * nativo não suporta requisições POST com corpo. */
export async function* enviarMensagem(
  sessionId: string,
  mensagem: string,
): AsyncGenerator<EventoChat> {
  const resp = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, mensagem }),
  })
  if (!resp.ok || !resp.body) {
    throw new Error('Falha ao conectar ao chat.')
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    // Normaliza terminadores de linha: o servidor envia "\r\n" (padrão SSE).
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')

    let indiceSeparador: number
    while ((indiceSeparador = buffer.indexOf('\n\n')) !== -1) {
      const bloco = buffer.slice(0, indiceSeparador)
      buffer = buffer.slice(indiceSeparador + 2)

      let evento = 'message'
      let dados = ''
      for (const linha of bloco.split('\n')) {
        if (linha.startsWith('event:')) evento = linha.slice(6).trim()
        else if (linha.startsWith('data:')) dados += linha.slice(5).trim()
      }
      if (!dados) continue
      try {
        const dadosParsed = JSON.parse(dados)
        yield { evento, dados: dadosParsed } as EventoChat
      } catch {
        // ignora blocos malformados (ex.: heartbeat/comentário SSE)
      }
    }
  }
}
