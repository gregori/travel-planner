# Travel Planner — Requisitos

> Documento único de requisitos do MVP. Escrito para ser executável por um agente
> de desenvolvimento: cada requisito tem ID, prioridade (MoSCoW) e critério de
> aceite verificável.

---

## 1. Visão

Um planejador de viagens com IA. O usuário conversa em linguagem natural com um
agente que coleta os parâmetros da viagem (destino, datas, orçamento, tipo de
viagem, viajantes, gostos e restrições), pesquisa preços de passagens,
hospedagem, alimentação e passeios, e entrega um roteiro completo dia a dia com
orçamento detalhado — exportável em PDF e Markdown para levar na viagem.

**Proposta de valor:** substituir horas de abas abertas por uma conversa de
poucos minutos, entregando um plano realista, dentro do orçamento e honesto
sobre a confiabilidade de cada preço apresentado.

---

## 2. Escopo

### 2.1 Dentro do escopo (MVP)

- Web app responsiva (chat + visualização do roteiro) com backend próprio.
- Conversa iterativa: o agente pergunta o que falta até ter dados suficientes.
- Busca de hospedagem, atrações e restaurantes em provedores reais.
- Estimativa de preço de voos por pesquisa/inferência, sempre rotulada como tal.
- Cotação de câmbio em tempo real, com conversão de todos os valores para a
  moeda de exibição escolhida. **Apenas informação — nenhuma contratação.**
- Itinerário dia a dia, orçamento por categoria, opções de voo/hospedagem,
  sugestões de restaurantes e checklist prático (documentos, clima, o que levar).
- Exportação do plano final em PDF e Markdown.
- Interface e conteúdo em **pt-BR**; origem, destino e moeda são parâmetros
  livres (o usuário pode partir de qualquer lugar).

### 2.2 Fora do escopo (explicitamente)

| # | Item | Observação |
|---|---|---|
| OUT-1 | Reserva ou compra real | O sistema planeja e linka; nunca reserva nem processa pagamento. |
| OUT-2 | App mobile nativo | Apenas web responsiva. |
| OUT-3 | Monitoramento de preços pós-plano | Sem alertas de queda de preço ou replanejamento automático. |
| OUT-4 | Contratação de câmbio, seguro ou visto | Cotação e informação sim; contratação não. |
| OUT-5 | Contas de usuário e histórico persistente | Sessão efêmera; o arquivo exportado é o artefato durável. |
| OUT-6 | Multi-idioma (i18n) | Somente pt-BR nesta versão. |

### 2.3 Consequências aceitas do escopo

- **Sem persistência ⇒ sem link compartilhável.** A sessão de chat vive em
  memória com TTL; ao expirar, o plano se perde. O usuário deve ser avisado
  disso na UI e incentivado a exportar.
- **Sem contas ⇒ controle de abuso por IP/sessão**, não por usuário.

---

## 3. Personas e cenários canônicos

Os três cenários abaixo formam a **suíte de aceite obrigatória** (§11). Todo
release deve passar nos três.

| ID | Persona | Cenário |
|---|---|---|
| CEN-1 | Família | São Paulo → Lisboa, 7 dias, 2 adultos + 1 criança (6 anos), teto de R$ 25.000, restrição alimentar (sem glúten). Exercita câmbio, voo longo, documentação e ritmo family-friendly. |
| CEN-2 | Casal | Fim de semana romântico, 3 dias, foco em gastronomia, orçamento médio. Cenário curto — valida ritmo e curadoria. |
| CEN-3 | Econômico | 5 dias dentro do Brasil, orçamento apertado. Sem câmbio nem visto; foca em otimização de custo. |

---

## 4. Decisões de produto e arquitetura

Decisões já tomadas — não reabrir sem motivo novo.

| Tema | Decisão |
|---|---|
| Formato | Web app (React) + backend (FastAPI), com exportação de documento |
| Entrada | Conversa iterativa em chat (não formulário) |
| Inteligência | **Agente único com tool-calling** (sem multi-agente) |
| Dados | **Híbrido**: provedor real quando há credencial, mock/estimativa como fallback |
| Orçamento | **Alvo com tolerância e alertas** (pode estourar, mas avisa quanto e onde) |
| Estado | Sessão em memória com TTL; sem banco de dados |
| Exportação | PDF + Markdown |
| Localização | pt-BR; origem/destino/moeda parametrizados |

### 4.1 Stack

- **Backend:** Python 3.12+, FastAPI, Pydantic v2, `uv` para dependências,
  `pytest` para testes, `ruff` para lint/format.
- **Frontend:** React + TypeScript + Vite. Streaming do chat via SSE.
- **LLM:** cliente OpenAI-compatible apontando para um gateway configurável
  (ex.: opencode / OpenRouter), com cadeia de modelos definida por variável de
  ambiente — ver §9.
- **PDF:** geração a partir do Markdown do plano (ex.: WeasyPrint via HTML
  intermediário).

### 4.2 Fluxo

```
Usuário ──chat──▶ /api/chat (SSE)
                     │
                     ▼
              Agente (tool-calling loop)
                     │
      ┌──────────────┼──────────────┬───────────────┐
      ▼              ▼              ▼               ▼
  Hospedagem     Atrações        Voos           Câmbio
  (Booking)     (Tripadvisor)  (busca web)    (API pública)
      └──────────────┴──────────────┴───────────────┘
                     │  toda resposta carrega Source
                     ▼
              TripBrief + TripPlan (sessão em memória)
                     │
                     ▼
              /api/plan/{id}/export → PDF | Markdown
```

---

## 5. Requisitos funcionais

Prioridade: **M**ust / **S**hould / **C**ould. Tudo marcado `M` é bloqueante
para o MVP.

### 5.1 Conversa e coleta de parâmetros

| ID | Pri | Requisito | Critério de aceite |
|---|:--:|---|---|
| RF-01 | M | O agente coleta, ao longo da conversa, os campos do `TripBrief` (§7.1). | Dado um prompt parcial ("quero ir pra Lisboa"), o agente pergunta pelos campos obrigatórios faltantes antes de planejar. |
| RF-02 | M | Campos obrigatórios mínimos para planejar: destino, datas (ou mês + duração), número de viajantes, orçamento. | O agente não gera plano com algum desses ausente; ele pergunta. |
| RF-03 | M | O agente nunca faz mais de **2 perguntas por turno**. | Nenhuma resposta do agente contém 3+ perguntas. |
| RF-04 | M | O usuário pode alterar qualquer parâmetro depois do plano pronto ("na verdade são 5 dias") e o plano é recalculado. | Após alteração, o plano reflete o novo valor e o orçamento é recalculado. |
| RF-05 | S | O agente infere padrões razoáveis de campos não informados (ritmo, tipo de hospedagem) e **declara a inferência** ao usuário. | O resumo do briefing lista o que foi inferido vs. informado. |
| RF-06 | M | Respostas do chat são transmitidas em streaming. | Primeiro token visível em ≤ 3s (RNF-05). |
| RF-07 | S | A UI mostra o briefing acumulado em painel lateral, atualizado a cada turno. | Painel reflete o estado após cada mensagem do agente. |

### 5.2 Pesquisa e dados

| ID | Pri | Requisito | Critério de aceite |
|---|:--:|---|---|
| RF-10 | M | Buscar hospedagem no destino via **Booking.com**, filtrando por datas, hóspedes e faixa de preço. | Retorna ≥ 3 opções com nome, preço/noite, localização e link. |
| RF-11 | M | Buscar atrações e passeios via **Tripadvisor**, filtrados por interesses e perfil dos viajantes. | Retorna atrações compatíveis com os interesses do briefing. |
| RF-12 | M | Estimar preço de voos por rota/época via pesquisa web, retornando **faixa** (mín–máx), nunca valor único falsamente preciso. | Todo voo aparece como faixa e rotulado `estimate`. |
| RF-13 | M | Cotar câmbio em API pública e converter todos os valores para a moeda de exibição. | Valores exibidos na moeda escolhida, com taxa e timestamp visíveis. |
| RF-14 | M | Sugerir restaurantes respeitando **todas** as restrições alimentares do briefing. | Nenhuma sugestão viola uma restrição declarada; a compatibilidade é justificada em uma linha. |
| RF-15 | M | Cada dado externo carrega uma `Source` (§7.3) com tipo (`real`/`estimate`/`mock`), provedor, URL quando houver e `retrieved_at`. | 100% dos itens de custo têm `Source` preenchida. |
| RF-16 | M | Quando um provedor real falha ou não tem credencial, o sistema cai para mock/estimativa e **marca visivelmente** o resultado. | Com credenciais ausentes, o app funciona ponta a ponta e exibe aviso de dados simulados. |
| RF-17 | S | Resultados de busca são cacheados por sessão (§RNF-08). | Duas buscas idênticas no mesmo turno geram uma única chamada externa. |

### 5.3 Geração do plano

| ID | Pri | Requisito | Critério de aceite |
|---|:--:|---|---|
| RF-20 | M | Gerar **itinerário dia a dia** com blocos manhã/tarde/noite. | Todo dia da viagem tem os 3 blocos preenchidos ou justificados como livres. |
| RF-21 | M | O itinerário é **geograficamente coerente**: atrações do mesmo dia agrupadas por região, com tempo de deslocamento estimado entre blocos. | Nenhum dia exige atravessar a cidade mais de 2 vezes. |
| RF-22 | M | Respeitar o **ritmo** conforme o perfil: com crianças ou mobilidade reduzida, no máximo 2 atividades principais por dia e pausas explícitas. | CEN-1 gera no máximo 2 atividades principais/dia. |
| RF-23 | M | Dias de chegada e partida consideram horários de voo, check-in/check-out e deslocamento ao aeroporto. | Nenhuma atividade agendada em conflito com voo ou check-in. |
| RF-24 | M | Apresentar **≥ 2 opções** de voo e **≥ 3 de hospedagem**, com preço, horário/localização e link, indicando a recomendada e o porquê. | Plano contém as alternativas e a justificativa da recomendação. |
| RF-25 | M | Produzir **orçamento detalhado** por categoria: voo, hospedagem, alimentação, passeios, transporte local, reserva de contingência. | Soma das categorias = total exibido; contingência ≥ 10% por padrão. |
| RF-26 | M | Comparar o total com o teto informado. Dentro da tolerância (padrão **10%**): sinaliza. Acima: **alerta explícito** com o valor excedido e as 3 categorias mais caras, sugerindo cortes. | CEN-3 (orçamento apertado) produz alerta acionável quando estoura. |
| RF-27 | M | Gerar **checklist prático**: documentos/visto, previsão de clima para o período, moeda e câmbio, tomada/adaptador, o que levar. | Checklist presente e coerente com destino e época. |
| RF-28 | S | Incluir alertas de documentação por nacionalidade quando a viagem for internacional, sempre com ressalva de verificar fonte oficial. | CEN-1 menciona requisitos de entrada e recomenda verificação oficial. |
| RF-29 | C | Sugerir o que mudaria com ±10% de orçamento. | — |

### 5.4 Exportação

| ID | Pri | Requisito | Critério de aceite |
|---|:--:|---|---|
| RF-30 | M | Exportar o plano em **Markdown** completo e autocontido. | Download do `.md` com itinerário, orçamento, opções, checklist e fontes. |
| RF-31 | M | Exportar o plano em **PDF** formatado e legível impresso. | Download do `.pdf` com o mesmo conteúdo, sem texto cortado. |
| RF-32 | M | O documento exportado inclui a seção **"Fontes e confiabilidade"**, listando cada preço, sua origem e data de consulta. | Seção presente em ambos os formatos. |
| RF-33 | M | O documento traz aviso de que preços são estimativas sujeitas a variação e que o sistema não realiza reservas. | Aviso presente no rodapé de ambos os formatos. |

---

## 6. Requisitos não-funcionais

| ID | Pri | Requisito | Critério de aceite |
|---|:--:|---|---|
| RNF-01 | M | **Transparência de fontes.** Nenhum número é exibido sem origem rastreável. A UI distingue visualmente `real`, `estimativa` e `mock`. | Inspeção da UI e do export mostra os três estados distinguíveis. |
| RNF-02 | M | **Nunca inventar dados.** Se um provedor não retorna resultado, o agente diz que não encontrou — não preenche com plausibilidade. | Teste com provedor retornando vazio: o plano declara a lacuna. |
| RNF-03 | M | **Testes determinísticos.** Suíte roda offline, com provedores mockados por fixtures e cliente LLM fake. Zero chamadas de rede em CI. | `pytest` passa sem credenciais e sem rede. |
| RNF-04 | M | Cobertura de testes ≥ 70% no backend, incluindo um teste ponta a ponta por cenário de aceite. | Relatório de cobertura no CI. |
| RNF-05 | S | **Latência:** primeiro token do chat em ≤ 3s; plano completo em ≤ 90s. | Medido nos cenários de aceite com provedores mockados. |
| RNF-06 | M | **Resiliência de chamadas externas:** timeout de 10s por chamada, 3 tentativas com backoff exponencial + jitter, circuit breaker por provedor e degradação para mock. Falha de um provedor **nunca** derruba a requisição. | Teste com provedor injetando erro/timeout: o plano é gerado com aviso de degradação. |
| RNF-07 | M | **Resiliência de LLM:** cadeia de modelos de fallback configurável; se o modelo primário falhar (erro, rate limit, indisponível), tenta o próximo automaticamente e registra qual foi usado. | Teste com primário falhando: resposta vem do secundário e o log identifica o modelo. |
| RNF-08 | M | **Controle de custo:** teto de chamadas de ferramenta por sessão (padrão 25), teto de tokens por sessão, cache de buscas com TTL (padrão 15 min). Atingido o teto, o agente conclui com o que tem e avisa. | Teste que estoura o teto encerra graciosamente, sem loop. |
| RNF-09 | M | **Sem PII persistida.** Nada é gravado em disco além de logs sem dados pessoais; sessões expiram (TTL padrão 60 min). | Inspeção: nenhuma escrita de dados de usuário em disco/banco. |
| RNF-10 | M | Segredos apenas via variáveis de ambiente; nenhuma chave no repositório. | `.env.example` versionado, `.env` no `.gitignore`. |
| RNF-11 | S | Rate limiting por IP nas rotas de chat e planejamento. | Excedido o limite, retorna 429 com mensagem clara. |
| RNF-12 | S | Logs estruturados (JSON) com `session_id`, ferramenta chamada, latência, modelo usado e custo estimado. | Logs inspecionáveis para depurar uma sessão inteira. |
| RNF-13 | S | UI responsiva e acessível: navegação por teclado, contraste AA, `aria-live` no stream do chat. | Verificação manual + auditoria automatizada básica. |

---

## 7. Modelo de domínio

Todos os modelos são Pydantic v2 e servem de contrato entre backend, agente e frontend.

### 7.1 `TripBrief` — o que o agente coleta

```python
class TripBrief(BaseModel):
    origin: str | None                    # cidade ou aeroporto de partida
    destination: str                      # cidade / região / país
    start_date: date | None
    end_date: date | None
    reference_month: str | None           # alternativa a datas exatas
    duration_days: int | None
    flexible_dates: bool = False
    adults: int = 1
    children_ages: list[int] = []
    total_budget: Decimal | None
    budget_currency: str = "BRL"          # ISO 4217
    display_currency: str = "BRL"
    budget_tolerance: float = 0.10        # RF-26
    trip_type: Literal["sightseeing","romantic","family","adventure","cultural","relaxation"]
    interests: list[str] = []
    dietary_restrictions: list[str] = []
    mobility_restrictions: str | None
    other_restrictions: list[str] = []
    pace: Literal["light","moderate","intense"] = "moderate"
    nationality: str | None               # para requisitos de entrada (RF-28)
    inferred_fields: list[str] = []       # RF-05
```

### 7.2 `TripPlan` — a saída

```python
class TripPlan(BaseModel):
    brief: TripBrief
    summary: str
    flight_options: list[FlightOption]            # >= 2 (RF-24)
    accommodation_options: list[AccommodationOption]  # >= 3
    itinerary: list[ItineraryDay]
    meals: list[MealSuggestion]
    budget: Budget
    exchange_rate: ExchangeRate | None
    checklist: Checklist
    sources: list[Source]                 # RF-32
    warnings: list[str]                   # degradações, estouros, lacunas
    generated_at: datetime

class ItineraryDay(BaseModel):
    day: int
    date: date | None
    region: str                           # RF-21
    morning: list[Activity]
    afternoon: list[Activity]
    evening: list[Activity]
    transfers: list[Transfer]             # tempo estimado entre blocos
    estimated_day_cost: Decimal

class Budget(BaseModel):
    flights: Decimal
    accommodation: Decimal
    food: Decimal
    activities: Decimal
    local_transport: Decimal
    contingency: Decimal                  # >= 10% (RF-25)
    total: Decimal
    stated_cap: Decimal | None
    difference: Decimal | None            # positivo = estouro
    within_cap: bool
    alerts: list[str]                     # RF-26
```

### 7.3 `Source` — a espinha dorsal da transparência

```python
class Source(BaseModel):
    type: Literal["real", "estimate", "mock"]
    provider: str                         # "booking", "tripadvisor", "web", "exchange-api", "fixture"
    url: str | None
    retrieved_at: datetime
    confidence: Literal["high", "medium", "low"]
    note: str | None
```

**Regra invariante:** todo campo monetário exibido ao usuário referencia uma
`Source`. Um plano sem `Source` em algum custo é inválido e deve falhar na
validação, não ser renderizado.

---

## 8. Contratos de API

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/api/session` | Cria sessão efêmera. Retorna `session_id` e TTL. |
| `POST` | `/api/chat` | Envia mensagem do usuário. Responde via **SSE**: eventos `token`, `tool_call`, `brief_update`, `plan_ready`, `error`, `done`. |
| `GET` | `/api/session/{id}/brief` | Estado atual do `TripBrief` (para o painel lateral). |
| `GET` | `/api/session/{id}/plan` | `TripPlan` atual em JSON. |
| `GET` | `/api/session/{id}/export?format=md\|pdf` | Download do documento. |
| `GET` | `/api/health` | Status do serviço e dos provedores (`real`/`unavailable`/`mock`). |

**Erros:** formato uniforme `{ "error": { "code": str, "message": str, "recoverable": bool } }`.
Mensagens de erro voltadas ao usuário são em pt-BR e acionáveis.

---

## 9. Camada de LLM

- Cliente **OpenAI-compatible**, com `base_url` e `api_key` por variável de
  ambiente — permite apontar para gateways de baixo custo (opencode, OpenRouter)
  sem mudar código.
- **Cadeia de modelos** definida por `LLM_MODEL_CHAIN` (lista ordenada). O
  primeiro é o padrão; os seguintes são fallback automático (RNF-07). Modelos
  gratuitos/baratos são candidatos naturais ao topo da cadeia, desde que passem
  na suíte de aceite.
- **IDs de modelo são configuração, nunca constantes no código.** A
  disponibilidade de um modelo específico muda ao longo do tempo; o sistema deve
  validar a cadeia na inicialização e registrar quais modelos responderam.
- **Contrato mínimo exigido do modelo:** suporte a tool-calling e a saída
  estruturada. Um modelo que não suporte tool-calling não pode ocupar a cadeia
  principal.
- Interface `LLMClient` isolando o agente do provedor, com implementação `FakeLLM`
  determinística para os testes (RNF-03).

### 9.1 Ferramentas expostas ao agente

| Ferramenta | Entrada | Saída |
|---|---|---|
| `update_brief` | campos parciais do `TripBrief` | briefing consolidado |
| `search_accommodation` | cidade, check-in, check-out, hóspedes, faixa de preço | lista de `AccommodationOption` + `Source` |
| `search_attractions` | cidade, interesses, perfil dos viajantes | lista de `Activity` + `Source` |
| `search_restaurants` | cidade, restrições, faixa de preço | lista de `MealSuggestion` + `Source` |
| `estimate_flights` | origem, destino, datas, passageiros | faixa de preço + `Source` (`estimate`) |
| `get_exchange_rate` | moeda origem, moeda destino | taxa + timestamp + `Source` |
| `practical_info` | destino, nacionalidade, período | clima, documentação, tomada, moeda |
| `calculate_budget` | itens de custo | `Budget` validado com alertas |

Toda ferramenta **deve** retornar `Source` junto com o dado. Uma ferramenta que
não consiga produzir dado real retorna resultado vazio com motivo — nunca dado
sintético não rotulado (RNF-02).

---

## 10. Camada de provedores

```python
class AccommodationProvider(Protocol):
    async def search(self, criteria: AccommodationCriteria) -> SearchResult: ...
```

- Implementações: `BookingProvider` (MCP), `TripadvisorProvider` (MCP),
  `WebFlightEstimator`, `ExchangeRateProvider`, e um `MockProvider` por interface
  alimentado por fixtures JSON versionadas.
- **Seleção em runtime:** credencial presente e provedor saudável → real;
  caso contrário → mock, com `Source.type="mock"` e aviso propagado ao
  `TripPlan.warnings`.
- **Circuit breaker por provedor:** após 3 falhas consecutivas, o provedor é
  marcado indisponível por 5 minutos e o sistema usa o fallback direto, sem
  pagar o custo de timeout a cada chamada.
- As fixtures de mock devem cobrir os três cenários de aceite (§11) com dados
  realistas, para que a suíte rode offline.

---

## 11. Critérios de aceite

O MVP está pronto quando os três cenários passam como testes automatizados
ponta a ponta (provedores mockados) **e** foram validados manualmente uma vez
com provedores reais.

### CEN-1 — Família internacional
São Paulo → Lisboa, 7 dias, 2 adultos + 1 criança (6 anos), teto R$ 25.000, sem glúten.

- [ ] Agente coleta o briefing completo em ≤ 6 turnos.
- [ ] Itinerário de 7 dias, no máximo 2 atividades principais/dia (RF-22).
- [ ] Restaurantes: 100% compatíveis com "sem glúten", com justificativa (RF-14).
- [ ] Orçamento em BRL com câmbio EUR→BRL, taxa e timestamp visíveis (RF-13).
- [ ] Checklist menciona documentação de entrada e recomenda verificação oficial (RF-28).
- [ ] ≥ 2 opções de voo e ≥ 3 de hospedagem, com recomendação justificada (RF-24).
- [ ] PDF e Markdown gerados com seção de fontes (RF-30/31/32).

### CEN-2 — Casal, fim de semana romântico
3 dias, foco gastronômico, orçamento médio.

- [ ] Itinerário de 3 dias com ritmo folgado e jantares como âncora.
- [ ] Dia de chegada e partida respeitam horários de voo e check-in/out (RF-23).
- [ ] Atividades do mesmo dia geograficamente agrupadas (RF-21).
- [ ] Nenhuma sugestão sem `Source` (RNF-01).

### CEN-3 — Nacional econômico
5 dias no Brasil, orçamento apertado.

- [ ] Seção de câmbio ausente ou marcada como não aplicável.
- [ ] Se o total estourar o teto, alerta explícito com valor excedido e as 3
      categorias mais caras, mais sugestões de corte (RF-26).
- [ ] Contingência de ≥ 10% presente mesmo com orçamento apertado (RF-25).

### Aceite transversal

- [ ] Sem nenhuma credencial configurada, o app roda ponta a ponta em modo mock,
      com aviso visível (RF-16).
- [ ] Com um provedor injetando timeout, o plano é gerado com aviso de
      degradação (RNF-06).
- [ ] Com o modelo primário falhando, a resposta vem do fallback (RNF-07).
- [ ] `pytest` passa offline, sem credenciais (RNF-03).

---

## 12. Estrutura do repositório

```
backend/
  app/
    api/              # rotas FastAPI, SSE
    agent/            # loop de tool-calling, prompts, ferramentas
    providers/        # protocolos + implementações reais e mock
    models/           # Pydantic: TripBrief, TripPlan, Source...
    export/           # Markdown e PDF
    session/          # store em memória com TTL
    llm/              # LLMClient, cadeia de fallback, FakeLLM
  tests/
    fixtures/         # dados dos 3 cenários
    e2e/              # um teste por cenário de aceite
frontend/
  src/
    components/       # chat, painel de briefing, visualização do plano
    api/              # cliente SSE
.env.example
```

### 12.1 Comandos esperados

| Comando | Efeito |
|---|---|
| `make dev` | sobe backend e frontend em modo desenvolvimento |
| `make test` | roda a suíte offline com fixtures |
| `make lint` | `ruff` + `tsc --noEmit` |
| `make e2e` | roda os três cenários de aceite |

### 12.2 Configuração (`.env.example`)

```
LLM_BASE_URL=            # gateway OpenAI-compatible
LLM_API_KEY=
LLM_MODEL_CHAIN=         # lista ordenada: primário,fallback1,fallback2
BOOKING_API_KEY=         # opcional — ausente ⇒ modo mock
TRIPADVISOR_API_KEY=     # opcional — ausente ⇒ modo mock
EXCHANGE_API_URL=
SESSION_TTL_MINUTES=60
MAX_TOOL_CALLS_PER_SESSION=25
MAX_TOKENS_PER_SESSION=
CACHE_TTL_MINUTES=15
```

---

## 13. Riscos e premissas

| Risco | Impacto | Mitigação |
|---|---|---|
| Preço de voo sem API confiável | Estimativas imprecisas frustram o usuário | Sempre exibir faixa, nunca valor único; rótulo `estimate` e confiança `low`/`medium` (RF-12) |
| Modelo barato/gratuito com tool-calling fraco | Agente entra em loop ou ignora ferramentas | Contrato mínimo em §9; cadeia de fallback; teto de chamadas (RNF-08) |
| Modelo gratuito descontinuado ou com rate limit | Serviço para | IDs como configuração + fallback automático (RNF-07) |
| Provedor MCP indisponível no runtime do backend | Sem dados reais | Fallback mock rotulado; `/api/health` expõe o estado (RF-16) |
| Alucinação de preços ou atrações inexistentes | Perda de confiança | RNF-02 + validação de que todo custo tem `Source` |
| Sessão em memória perdida | Usuário perde o plano | Aviso na UI + incentivo à exportação precoce |

**Premissas:** o usuário tem acesso à internet; os conectores Booking.com e
Tripadvisor estão acessíveis ao backend via MCP; a API de câmbio escolhida é
gratuita e não exige credencial paga.

---

## 14. Definition of Done

Uma entrega só está pronta quando:

1. Todos os requisitos `M` implementados e com teste correspondente.
2. Os três cenários de aceite (§11) passam automatizados.
3. `make test` e `make lint` verdes, offline e sem credenciais.
4. O app roda ponta a ponta em modo mock puro.
5. `.env.example` atualizado e nenhum segredo versionado.
6. Cobertura de backend ≥ 70%.
