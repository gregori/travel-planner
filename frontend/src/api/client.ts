import type { TripBrief, TripPlan } from './types'

// Em dev, fala direto com o backend (CORS liberado em app/main.py) em vez de
// passar pelo proxy do Vite: o http-proxy do Vite duplica o header
// `Connection` em respostas chunked, o que quebra o streaming SSE no
// Chromium. Em produção, aponte VITE_API_URL para a origem do backend.
const API_ORIGIN = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '')
const API_BASE = `${API_ORIGIN}/api`

export interface SessionResponse {
  session_id: string
  ttl_minutes: number
}

export async function createSession(): Promise<SessionResponse> {
  const resp = await fetch(`${API_BASE}/session`, { method: 'POST' })
  if (!resp.ok) throw new Error('Não foi possível criar a sessão.')
  return resp.json()
}

export async function getBrief(sessionId: string): Promise<TripBrief> {
  const resp = await fetch(`${API_BASE}/session/${sessionId}/brief`)
  if (!resp.ok) throw new Error('Não foi possível obter o briefing.')
  return resp.json()
}

export async function getPlan(sessionId: string): Promise<TripPlan | null> {
  const resp = await fetch(`${API_BASE}/session/${sessionId}/plan`)
  if (resp.status === 409) return null
  if (!resp.ok) throw new Error('Não foi possível obter o plano.')
  return resp.json()
}

export function exportUrl(sessionId: string, format: 'md' | 'pdf'): string {
  return `${API_BASE}/session/${sessionId}/export?format=${format}`
}

export type ChatEvent =
  | { event: 'token'; data: string }
  | { event: 'tool_call'; data: { tool: string; arguments: Record<string, unknown> } }
  | { event: 'brief_update'; data: TripBrief }
  | { event: 'plan_ready'; data: TripPlan }
  | { event: 'error'; data: { code: string; message: string } }
  | { event: 'done'; data: null }

/** Faz o parsing de um único bloco SSE (linhas `event:`/`data:` separadas por
 * uma linha em branco) em `{ event, data }`. Função pura, extraída de
 * `sendMessage` para ser testável sem precisar simular um stream de
 * verdade — foi aqui que um bug real escapou (blocos separados por `\r\n\r\n`
 * eram ignorados por um parser que só reconhecia `\n\n`). */
export function parseSSEBlock(block: string): { event: string; data: unknown } | null {
  let event = 'message'
  let data = ''
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data += line.slice(5).trim()
  }
  if (!data) return null
  try {
    return { event, data: JSON.parse(data) }
  } catch {
    return null // bloco malformado (ex.: heartbeat/comentário SSE)
  }
}

/** Consome o SSE de /api/chat (RF-06) manualmente via fetch, pois EventSource
 * nativo não suporta requisições POST com corpo. */
export async function* sendMessage(sessionId: string, message: string): AsyncGenerator<ChatEvent> {
  const resp = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message }),
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

    let separatorIndex: number
    while ((separatorIndex = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, separatorIndex)
      buffer = buffer.slice(separatorIndex + 2)
      const event = parseSSEBlock(block)
      if (event) yield event as ChatEvent
    }
  }
}
