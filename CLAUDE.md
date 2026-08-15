# CLAUDE.md

Instruções para agentes trabalhando neste repositório.

## O projeto

**Travel Planner** — planejador de viagens com IA. O usuário conversa em
linguagem natural com um agente que coleta os parâmetros da viagem, pesquisa
preços de passagens, hospedagem, alimentação e passeios, e entrega um roteiro
dia a dia com orçamento detalhado, exportável em PDF e Markdown.

## Estado atual

**O projeto ainda não tem código.** Existe apenas a especificação. A próxima
etapa é implementar o MVP conforme `REQUIREMENTS.md`.

## Documentos e ordem de leitura

| Arquivo | Papel |
|---|---|
| `REQUIREMENTS.md` | **Fonte da verdade.** Escopo, requisitos numerados (RF/RNF), modelo de domínio, contratos de API, critérios de aceite. Leia antes de escrever qualquer código. |
| `PROCESS.md` | Processo de construção a seguir. |
| `SELF_IMPROVE.md` | Etapa obrigatória de auto-melhoria ao final do trabalho. |
| `CLAUDE.md` | Este arquivo: convenções e regras permanentes. |

Se algo aqui conflitar com `REQUIREMENTS.md`, **`REQUIREMENTS.md` vence** —
e corrija este arquivo.

## Stack

- **Backend:** Python 3.12+, FastAPI, Pydantic v2, `uv`, `pytest`, `ruff`
- **Frontend:** React + TypeScript + Vite, streaming via SSE
- **LLM:** cliente OpenAI-compatible apontando para gateway configurável
- **Exportação:** Markdown como formato canônico; PDF derivado dele

## Estrutura

```
backend/app/
  api/        # rotas FastAPI, SSE
  agent/      # loop de tool-calling, prompts, ferramentas
  providers/  # protocolos + implementações reais e mock
  models/     # Pydantic: TripBrief, TripPlan, Fonte
  export/     # Markdown e PDF
  session/    # store em memória com TTL
  llm/        # LLMClient, cadeia de fallback, FakeLLM
backend/tests/
  fixtures/   # dados dos 3 cenários de aceite
  e2e/        # um teste por cenário
frontend/src/
  components/ # chat, painel de briefing, visualização do plano
  api/        # cliente SSE
```

## Comandos

| Comando | Efeito |
|---|---|
| `make dev` | sobe backend e frontend em desenvolvimento |
| `make test` | suíte offline com fixtures |
| `make lint` | `ruff` + `tsc --noEmit` |
| `make e2e` | os três cenários de aceite |

`make test` **deve** passar sem rede e sem credenciais.

## Regras invariantes

Estas regras não são negociáveis. Violá-las é um bug, não uma escolha de estilo.

1. **Nunca inventar dados.** Se um provedor não retorna resultado, o sistema diz
   que não encontrou. Preço, atração ou restaurante plausível-porém-inventado é
   falha grave.
2. **Todo valor monetário exibido carrega uma `Fonte`** (`real` / `estimativa` /
   `mock`, com provedor, timestamp e confiança). Um `TripPlan` com custo sem
   fonte deve falhar na validação, não ser renderizado.
3. **Modo mock sempre funciona.** Sem nenhuma credencial configurada, o app roda
   ponta a ponta e avisa visivelmente que os dados são simulados.
4. **IDs de modelo de LLM são configuração, nunca constantes no código.** Use
   `LLM_MODEL_CHAIN` com fallback automático; modelos baratos/gratuitos mudam e
   somem.
5. **Nenhum segredo no repositório.** Só variáveis de ambiente; mantenha
   `.env.example` atualizado.
6. **Falha de provedor externo nunca derruba a requisição.** Timeout, retry com
   backoff, circuit breaker e degradação para mock com aviso.
7. **Sem persistência de dados de usuário.** Sessão em memória com TTL; nada em
   disco ou banco.
8. **O sistema não reserva nem compra nada.** Apenas planeja e linka.

## Convenções

- **Idioma:** produto, UI, mensagens de erro e conteúdo gerado em **pt-BR**.
  Campos dos modelos de domínio seguem os nomes definidos em `REQUIREMENTS.md`
  (em português) — não traduza para inglês.
- **Requisitos por ID:** ao implementar, referencie o requisito (`RF-21`,
  `RNF-06`) na mensagem de commit ou no teste. Cada requisito `M` precisa de
  teste correspondente.
- **Testes primeiro nos pontos críticos:** orçamento, validação de `Fonte` e
  fallback de provedor/LLM têm teste antes da implementação.
- **Fixtures cobrem os 3 cenários de aceite** (família internacional, casal
  romântico, nacional econômico) — ver §11 de `REQUIREMENTS.md`.

## Git

- Trabalhe em branch de feature; **não faça push direto na `main`**.
- Não abra pull request sem pedido explícito.
- Mensagens de commit em português, descrevendo o efeito da mudança.
