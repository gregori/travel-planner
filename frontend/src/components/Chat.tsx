import { useState, type FormEvent } from 'react'
import type { ChatMessage } from '../api/types'

interface ChatProps {
  messages: ChatMessage[]
  waiting: boolean
  onSend: (text: string) => void
}

export function Chat({ messages, waiting, onSend }: ChatProps) {
  const [text, setText] = useState('')

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const value = text.trim()
    if (!value || waiting) return
    onSend(value)
    setText('')
  }

  return (
    <section className="panel chat" aria-label="Conversa com o assistente">
      <h2>Converse com o assistente</h2>
      <div className="chat__messages" aria-live="polite" role="log">
        {messages.length === 0 && (
          <p className="chat__empty">
            Conte para onde você quer ir — destino, datas, quantas pessoas e o orçamento — e eu
            monto seu roteiro.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat__bubble chat__bubble--${m.author}`}>
            {m.text}
          </div>
        ))}
        {waiting && (
          <div className="chat__bubble chat__bubble--agent chat__bubble--loading" aria-label="Assistente digitando">
            <span className="dot" />
            <span className="dot" />
            <span className="dot" />
          </div>
        )}
      </div>
      <form className="chat__form" onSubmit={handleSubmit}>
        <label htmlFor="chat-input" className="visually-hidden">
          Mensagem para o assistente
        </label>
        <input
          id="chat-input"
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ex.: Quero ir para Lisboa em outubro, 2 adultos e 1 criança"
          disabled={waiting}
        />
        <button type="submit" disabled={waiting || !text.trim()}>
          Enviar
        </button>
      </form>
    </section>
  )
}
