# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Travel Planner: an AI travel-planning agent. The user chats in natural language (pt-BR), a
single tool-calling agent (no multi-agent orchestration) collects trip parameters, searches
accommodation/attractions/flights/exchange rates, and produces a day-by-day itinerary with
budget, exportable as PDF and Markdown. No bookings/payments are ever made, and there is no
persistence beyond an in-memory session with TTL (no accounts, no database).

The full spec — functional/non-functional requirements, domain model, API contracts, acceptance
scenarios — lives in `REQUIREMENTS.md`. Treat it as the source of truth when requirements and
code disagree. `PROCESS.md` documents the build/review/self-improve loop this project was built
under (drives a `product_review` subagent — see `.claude/agents/product_review.md` — and an
accumulating lessons log). `SELF_IMPROVE.md` holds that lessons log; read it before touching
areas it flags (SSE parsing, `Source`/currency invariants, provider→agent layering).

## Commands

```
make install    # uv sync (backend) + npm install (frontend)
make dev        # backend :8000 + frontend :5173, both with reload
make test       # pytest --cov=app (backend) + npm run test (frontend, vitest)
make lint       # ruff check (backend) + oxlint + tsc --noEmit (frontend)
make e2e        # pytest tests/e2e -v — the three acceptance scenarios
```

Single test, backend: `cd backend && uv run pytest tests/unit/test_budget.py -v` (or `-k name`).
Single test, frontend: `cd frontend && npm run test -- BriefPanel`.
Backend deps: `uv add <pkg>` / `uv sync`, never `pip install`. Frontend: `npm install`, never
`npx`/`ts-node` directly for scripts — use the `npm run` scripts in `package.json`.

Backend tests run fully offline with a `FakeLLM` and mock providers fed by JSON fixtures
(`tests/fixtures/`) — no network, no credentials required (RNF-03).

**Windows gotcha:** `pytest` collection fails on `tests/api/test_routes.py`,
`tests/e2e/test_cen1_familia.py`, and `tests/unit/test_export.py` with
`OSError: cannot load library 'libgobject-2.0-0'` — these import the PDF export path
(`app/export/pdf.py`, WeasyPrint), which needs native GTK/Pango/cairo that Windows doesn't ship
and that reliably fighting via MSYS2 isn't worth it. Run backend tests/lint from Linux instead:
- **WSL (preferred for day-to-day)** — the Ubuntu distro already has `libgobject-2.0.so.0` and
  Python 3.12 present; it only needs `uv` installed once
  (`curl -LsSf https://astral.sh/uv/install.sh | sh`). Then run the same `uv run pytest`/`make
  test` commands from `wsl -d Ubuntu -e bash -lc "cd /mnt/d/travel-planner/backend && ..."`, or
  a shell opened directly in WSL.
- **Docker** — `backend/Dockerfile` installs the exact GTK/Pango/cairo packages WeasyPrint needs
  (see its `apt-get install` block) and is what actually ships to Render, so it's the
  higher-fidelity option when you want test results to match production rather than just unblock
  local iteration. `docker-compose.yml` runs the backend container with reload; add a one-off
  `docker compose run --rm backend uv run pytest` for tests rather than relying on the dev
  compose service.

Frontend tests/lint (`npm run test`, `oxlint`, `tsc`) have no such dependency and run fine
natively on Windows.

## Architecture

### Backend flow (`backend/app/`)

```
POST /api/chat (SSE)  →  process_message() [agent/loop.py]
                             │  tool-calling loop against LLMClient, max 8 iterations/turn
                             │  emits: token, tool_call, brief_update, plan_ready, error, done
                             ▼
                        TOOL_HANDLERS [agent/tools.py]  →  ProviderRegistry [providers/registry.py]
                             │                                  │
                             │                          real provider if credentialed + circuit
                             │                          closed, else mock — every fallback path
                             │                          appends a human-readable warning
                             ▼
                        session.brief.ready_to_plan()?
                             │ yes, and brief changed since last plan
                             ▼
                        generate_plan() [agent/planner.py] → TripPlan → plan_ready event
```

- **`agent/loop.py`** — the SSE-facing orchestrator. Owns per-session budgets: tool-call cap,
  token cap (`estimate_tokens`, ~4 chars/token heuristic, no real tokenizer), and the "never more
  than 2 questions per turn" check (`count_questions`, RF-03, logged not enforced). Structured
  JSON logs go to the `travel_planner.metrics` logger.
- **`agent/tools.py`** — tool schemas exposed to the LLM plus their handlers, all taking an
  `AgentContext` (session + registry + settings). Every tool that returns cost data must attach a
  `Source`.
- **`agent/planner.py` / `agent/budget.py` / `agent/itinerary.py`** — assemble `TripPlan` once the
  brief is complete: budget math (RF-25/26), day-by-day itinerary with geographic/pace
  constraints (RF-21/22/23).
- **`providers/registry.py`** — the real/mock selection point (RF-16, §10 of REQUIREMENTS.md).
  Real provider used only if an API key is configured *and* its `CircuitBreaker` is closed (opens
  after 3 failures in a 300s window); otherwise falls back to the matching `Mock*Provider` and
  appends a warning string to the caller-supplied `warnings` list — that list flows into
  `TripPlan.warnings` and must reach the UI, not just a log line. Flights have no "real" mode by
  design — they're always `estimate` (RF-12).
- **`llm/`** — `LLMClient` Protocol (`llm/base.py`) isolates the agent from the model provider.
  `openai_client.py` is the OpenAI-compatible implementation with the model-fallback chain
  (`LLM_MODEL_CHAIN`, comma-separated, first = primary); `fake.py` is the deterministic client
  used by every test. IDs of models are config (`Settings.model_chain_list`), never hardcoded.
- **`models/`** — Pydantic v2 contracts shared across backend, agent, and (via JSON) frontend:
  `TripBrief` (what's collected), `TripPlan`/`ItineraryDay`/`Budget` (the output), `Source` (see
  below). These are the API's actual contract — read them before touching `agent/` or `api/`.
- **`session/store.py`** — in-memory session state with TTL, no database (§2.3 of
  REQUIREMENTS.md: no persistence ⇒ no shareable link, by design).
- **`export/`** — `markdown.py` and `pdf.py` (WeasyPrint via HTML) both render from the same
  `TripPlan`, and both must include the "Fontes e confiabilidade" section (RF-32) and the
  estimates/no-booking disclaimer (RF-33).

### The `Source` invariant

Every monetary field shown to the user must carry a `Source` (type: `real`/`estimate`/`mock`,
provider, url, `retrieved_at`, confidence). This is treated as a hard invariant, not a
nice-to-have: a `TripPlan` missing a `Source` on any cost item should fail validation rather than
render. When adding a new cost-bearing field, attach its `Source` at the point the value is
created — see `SELF_IMPROVE.md`'s note on a validator that checked an already-non-optional
Pydantic field and could never fire, and its note on `Activity` originally lacking a currency
field that `FlightOption`/`AccommodationOption` already had.

### Frontend (`frontend/src/`)

React 19 + TypeScript + Vite, plain CSS (no framework). `api/client.ts` is the SSE client
consuming `/api/chat`'s event stream; `components/` are the chat window, the live `TripBrief`
side panel, the plan view, `SourceBadge` (the `real`/`estimate`/`mock` visual distinction from
RNF-01), and export buttons. Linting is `oxlint`, not ESLint; type-checking is a separate
`tsc -b --noEmit` step from `build`.

### Layering rule

`providers/` must not import from `agent/` — utilities needed by both (e.g. currency/geography
helpers) belong in an app-level neutral module, not inside whichever layer happened to need it
first. This was a real inversion caught late in a prior build pass (see `SELF_IMPROVE.md`).

## Working in this repo

- All user-facing text (UI copy, error messages, exported documents, the `product_review` agent's
  reports) is pt-BR. Code, identifiers, and comments are English as usual.
- Streaming/SSE changes are not proven correct by `curl -N` or automated tests alone — both
  tolerate framing that a real browser's `fetch()`/`ReadableStream` won't. Validate SSE changes
  against an actual browser (Playwright or manual) before considering them done.
- `.claude/agents/product_review.md` defines a read-only subagent that audits the build against
  `REQUIREMENTS.md`'s Must-requirements, the three acceptance scenarios (§11), and the Definition
  of Done (§14), evidence-first (`file:line` or command output, never inference from a promising
  filename). Invoke it when asked to "review the product" or check acceptance criteria — it never
  edits files.
