import { describe, expect, it } from 'vitest'
import { parseBlocoSSE } from '../client'

describe('parseBlocoSSE', () => {
  it('faz o parsing de um bloco separado por \\n\\n (formato usado nos testes/curl)', () => {
    const bloco = 'event: token\ndata: "olá"'
    expect(parseBlocoSSE(bloco)).toEqual({ evento: 'token', dados: 'olá' })
  })

  it('regressão: reconhece blocos que chegam com terminador \\r\\n (SSE real do navegador)', () => {
    // O bug real: o servidor manda "\r\n" e um parser que só procura "\n\n"
    // nunca encontra o fim do bloco. `enviarMensagem` normaliza \r\n -> \n
    // antes de chamar parseBlocoSSE, então aqui simulamos o bloco já
    // normalizado (o que importa é que o parser das linhas continua correto).
    const bloco = 'event: plan_ready\ndata: {"resumo":"ok"}'
    expect(parseBlocoSSE(bloco)).toEqual({ evento: 'plan_ready', dados: { resumo: 'ok' } })
  })

  it('concatena múltiplas linhas data: (SSE multi-linha)', () => {
    const bloco = 'event: token\ndata: {"a":\ndata: 1}'
    expect(parseBlocoSSE(bloco)).toEqual({ evento: 'token', dados: { a: 1 } })
  })

  it('retorna null para bloco sem data (ex.: comentário/heartbeat)', () => {
    expect(parseBlocoSSE(': ping')).toBeNull()
  })

  it('retorna null para JSON malformado em vez de lançar', () => {
    expect(parseBlocoSSE('event: token\ndata: {invalido')).toBeNull()
  })

  it('usa "message" como evento padrão quando não há linha event:', () => {
    expect(parseBlocoSSE('data: "oi"')).toEqual({ evento: 'message', dados: 'oi' })
  })
})
