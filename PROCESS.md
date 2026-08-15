# Processo de construção do sistema de planejamento de viagens

Você deve seguir o seguinte processo para construir o projeto:

1. Construa todo o projeto conforme documentado em `REQUIREMENTS.md`.
2. Certifique-se de que todos os critérios de sucesso foram atingidos.
3. Use seu subagent `product_review` para verificar o produto final.
4. Incorpore as alterações apontadas pelo `product_review` e, antes de seguir
   em frente, releia cada achado como um cenário de teste em vez de um texto
   a "resolver": para cada invariante ("todo X exige Y"), escreva ou rode um
   teste que tente construir o estado inválido e confirme que ele falha —
   um validador que nunca é exercitado no caminho inválido não prova nada
   (foi exatamente o que aconteceu aqui: o primeiro validador de `Fonte`
   checava campos que já eram obrigatórios no tipo, então nunca podia
   disparar). Depois de aplicar as correções, rode a suíte completa de novo
   E repita a verificação manual no navegador (passo abaixo) — uma correção
   pode ficar sintaticamente certa e ainda assim ter um bug de rótulo/texto
   que só aparece olhando a tela renderizada (aconteceu com o texto da fonte
   heurística de alimentação/transporte: a correção do `product_review`
   ficou "certa" nos testes automatizados, mas o texto não continha a
   palavra que o rótulo dinâmico procurava, e só a captura de tela revelou
   isso).
5. **IMPORTANTE** siga as instruções de `SELF_IMPROVE.md` para se melhorar.

Você deve completar o passo 5 (self-improvement) antes de parar.

## Lições incorporadas (não reabrir sem motivo novo)

- **Streaming/SSE precisa de teste em navegador de verdade, não só `curl`.**
  `curl -N` tolera terminadores de linha e buffering de um jeito que o
  `fetch()`/`ReadableStream` do Chromium não tolera. Um bug real (parser de
  SSE só reconhecia `\n\n`, mas o servidor manda `\r\n\r\n`) passou por todos
  os testes automatizados e por verificação via `curl` — só apareceu ao
  efetivamente clicar "enviar" numa página carregada no Chromium via
  Playwright. Sempre que uma feature envolver streaming, WebSocket ou
  qualquer coisa sensível a chunking, valide com um navegador real antes de
  considerar pronto.
- **Utilitários compartilhados entre camadas vivem numa camada neutra desde
  o início.** `providers/` importar de `agent/` é uma inversão de
  dependência — descoberta só na correção do `product_review`, quando um
  helper de moeda/geografia precisou ser usado tanto pelo provider mock
  quanto pelo agente. Ao introduzir um helper que mais de uma camada vai
  precisar, coloque-o num módulo de nível de aplicação (`app/`), não dentro
  da camada que o criou primeiro.
- **Dado monetário multi-moeda precisa da moeda de origem anexada no ponto
  de criação do dado**, não inferida depois. A conversão de câmbio de
  hospedagem/voo funcionou desde o início porque esses modelos sempre
  tiveram um campo `moeda`; passeios não tinham esse campo em `Atividade` e
  ficaram sendo exibidos com o valor cru em EUR rotulado como BRL. Ao
  desenhar um modelo que carrega um valor monetário, pergunte "essa moeda
  pode variar por item?" antes de assumir a moeda de exibição do plano.
