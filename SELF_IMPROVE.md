# Self-Improvement Step

IMPORTANT: You MUST complete this step before stopping.

1. Look back at your work in building this project, including any challenges
   you encountered, bugs you hit and feedback you received (especially from
   `product_review`, if you ran it).
2. Identify the strengths and weaknesses. Be concrete: not "communication
   could be better" but "I wrote a validator that checked fields that were
   already non-optional at the type level, so it could never actually fail —
   I should have tried to construct the invalid state and confirmed the
   validator rejects it before calling it done." A weakness without a
   reproducible example is not useful to a future run.
3. Self-improvement: update `PROCESS.md` to factor in your learnings so the
   process itself is improved next time. Prefer adding a concrete rule tied
   to the exact failure mode you hit over a generic reminder ("write more
   tests" is not actionable; "when a validator's job is to reject an invalid
   state, write a test that constructs that exact invalid state" is).
4. Recursive self-improvement: update *this* file so you are more effective
   at self-improvement next time. This means two things, not one:
   - Improve the process described above (steps 1-3) if you found a better
     way to reflect than what's written here.
   - Append to the "Histórico de aprendizados" log below — one dated entry
     per run, a few bullets max. Do not delete or rewrite previous entries;
     this file's value compounds only if the log actually accumulates.
     If a past entry's lesson turns out to be wrong or superseded, add a new
     entry that says so rather than silently editing the old one.

IMPORTANT: You MUST include step 4, recursive self-improvement. Every time
you run, this document should be taken to the next level based on your
learnings — not just re-saved with the same content.

## Como refletir (perguntas para se fazer antes de escrever o log)

- Que bug real eu (ou o `product_review`) encontrei que um teste ingênuo não
  pegaria? O que especificamente fazia o teste ingênuo parecer suficiente?
- Alguma verificação minha "passou" sem realmente exercitar o caminho que
  deveria falhar? (validador nunca alcançável, mock que não representa o
  caso real, teste que checa a forma da resposta mas não o conteúdo)
- Eu testei a feature do jeito que um usuário real vai usá-la (navegador,
  não só `curl`/API direta), ou só confiei que "os testes passam"?
- Depois de corrigir os achados do `product_review`, eu revalidei de ponta a
  ponta, ou só confiei que a correção estava certa porque compilou/os testes
  automatizados existentes continuaram verdes?

## Histórico de aprendizados

### Execução 1 (2026-08-15)

- **Validador morto não é validador.** O primeiro validador de `Fonte` em
  `TripPlan` checava `opcoes_voo[i].fonte is None`, mas `fonte` já era um
  campo obrigatório do Pydantic nesses modelos — a checagem nunca podia
  disparar. O `product_review` só encontrou isso porque construiu um
  `TripPlan` deliberadamente inválido e observou que ele validava sem erro.
  Regra adotada: ao escrever um validador de invariante, escrever também
  (ou pedir) o teste que constrói o estado inválido e confirma a falha,
  antes de considerar a invariante implementada.
- **SSE/streaming só se prova certo num navegador real.** Um bug de parsing
  (`\n\n` vs `\r\n\r\n`) passou por testes automatizados e por verificação
  manual via `curl -N` — ambos toleram diferenças de terminador de linha que
  o `fetch()`/`ReadableStream` do Chromium não tolera. Só apareceu ao rodar
  Playwright contra a página de verdade. Regra adotada: para qualquer
  feature de streaming, a verificação manual tem que ser num navegador,
  não no terminal.
- **Corrigir o achado do review não é o fim — revalidar é.** Ao corrigir o
  rótulo de "Fontes e confiabilidade" para linkar item↔preço, o texto da
  `Fonte` heurística de alimentação/transporte não continha a palavra que a
  lógica de rotulagem procurava (`"aliment"`/`"transporte"`), então as duas
  categorias caíam no rótulo genérico — um bug novo, introduzido pela
  própria correção, que só apareceu numa captura de tela, não nos testes
  (que checavam a presença da seção, não o conteúdo exato de cada linha).
  Regra adotada: depois de aplicar correções de um `product_review`, rodar a
  suíte *e* repetir a verificação manual (navegador) antes de considerar o
  ciclo fechado.
- **Camada errada para utilitário compartilhado.** Um helper de
  moeda/geografia foi criado dentro de `agent/` e depois precisou ser usado
  por `providers/` também — uma dependência de baixo para cima. Só ficou
  óbvio ao tentar importar. Regra adotada: helper que mais de uma camada vai
  usar nasce num módulo neutro (`app/`), não dentro da primeira camada que
  precisou dele.
