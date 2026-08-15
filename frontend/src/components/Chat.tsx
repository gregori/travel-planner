import { useState, type FormEvent } from 'react'
import type { ChatMessage } from '../api/types'

interface ChatProps {
  mensagens: ChatMessage[]
  aguardando: boolean
  onEnviar: (texto: string) => void
}

export function Chat({ mensagens, aguardando, onEnviar }: ChatProps) {
  const [texto, setTexto] = useState('')

  function handleSubmit(evento: FormEvent) {
    evento.preventDefault()
    const valor = texto.trim()
    if (!valor || aguardando) return
    onEnviar(valor)
    setTexto('')
  }

  return (
    <section className="panel chat" aria-label="Conversa com o assistente">
      <h2>Converse com o assistente</h2>
      <div className="chat__mensagens" aria-live="polite" role="log">
        {mensagens.length === 0 && (
          <p className="chat__vazio">
            Conte para onde você quer ir — destino, datas, quantas pessoas e o orçamento — e eu
            monto seu roteiro.
          </p>
        )}
        {mensagens.map((m, i) => (
          <div key={i} className={`chat__bolha chat__bolha--${m.autor}`}>
            {m.texto}
          </div>
        ))}
        {aguardando && (
          <div className="chat__bolha chat__bolha--agente chat__bolha--carregando" aria-label="Assistente digitando">
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
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="Ex.: Quero ir para Lisboa em outubro, 2 adultos e 1 criança"
          disabled={aguardando}
        />
        <button type="submit" disabled={aguardando || !texto.trim()}>
          Enviar
        </button>
      </form>
    </section>
  )
}
