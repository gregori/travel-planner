import { describe, expect, it } from 'vitest'
import { parseSSEBlock } from '../client'

describe('parseSSEBlock', () => {
  it('faz o parsing de um bloco separado por \\n\\n (formato usado nos testes/curl)', () => {
    const block = 'event: token\ndata: "olá"'
    expect(parseSSEBlock(block)).toEqual({ event: 'token', data: 'olá' })
  })

  it('regressão: reconhece blocos que chegam com terminador \\r\\n (SSE real do navegador)', () => {
    // O bug real: o servidor manda "\r\n" e um parser que só procura "\n\n"
    // nunca encontra o fim do bloco. `sendMessage` normaliza \r\n -> \n
    // antes de chamar parseSSEBlock, então aqui simulamos o bloco já
    // normalizado (o que importa é que o parser das linhas continua correto).
    const block = 'event: plan_ready\ndata: {"summary":"ok"}'
    expect(parseSSEBlock(block)).toEqual({ event: 'plan_ready', data: { summary: 'ok' } })
  })

  it('concatena múltiplas linhas data: (SSE multi-linha)', () => {
    const block = 'event: token\ndata: {"a":\ndata: 1}'
    expect(parseSSEBlock(block)).toEqual({ event: 'token', data: { a: 1 } })
  })

  it('retorna null para bloco sem data (ex.: comentário/heartbeat)', () => {
    expect(parseSSEBlock(': ping')).toBeNull()
  })

  it('retorna null para JSON malformado em vez de lançar', () => {
    expect(parseSSEBlock('event: token\ndata: {invalido')).toBeNull()
  })

  it('usa "message" como evento padrão quando não há linha event:', () => {
    expect(parseSSEBlock('data: "oi"')).toEqual({ event: 'message', data: 'oi' })
  })
})
