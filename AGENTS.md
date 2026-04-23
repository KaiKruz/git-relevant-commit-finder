# AGENTS.md — Agent Roles & Workflow

This document describes how AI agents (Copilot, Antigravity, Claude, etc.) should reason about, navigate, and contribute to this codebase.

---

## Project Purpose

**Git Relevant Commit Finder** ingests a git repository's commit history, embeds the commits, and provides semantic search so developers can answer natural-language questions about their history.

---

## Repository Map (Agent Quick Reference)

```
backend/app/
  main.py            ← FastAPI app factory + router registration
  api/repos.py       ← POST /repos/ingest, GET /repos
  api/search.py      ← POST /search
  core/config.py     ← Pydantic Settings (reads .env)
  services/ingestor.py  ← Clone/open repo, extract commits + diffs
  services/embedder.py  ← Chunk text, call embedding model, upsert to store
  services/searcher.py  ← Query embedding, retrieve + rank results
  models/schemas.py  ← ALL shared Pydantic request/response models
  db/vector_store.py ← ChromaDB client singleton

frontend/src/
  api/client.js      ← Axios instance + typed API helpers
  pages/             ← Page-level React components
  components/        ← Shared UI components
  hooks/             ← Custom hooks (useSearch, useRepos)
```

---

## Agent Roles

### 🏗️ Architect Agent
- Owns `docs/api-contract.md`
- Any change to endpoint paths, request/response shapes, or status codes MUST be reflected there first
- Propagates schema changes to `models/schemas.py` and `api/client.js`

### ⚙️ Backend Agent
- Works inside `backend/`
- Entry point: `app/main.py`
- Business logic lives exclusively in `services/` — route handlers must stay thin
- Use `core/config.py` settings; never hardcode secrets or paths
- All request/response types MUST come from `models/schemas.py`
- Always add docstrings to public functions

### 🎨 Frontend Agent
- Works inside `frontend/`
- API calls go through `src/api/client.js` only — never use raw `fetch`/`axios` in components
- State: prefer React Query for server state; local `useState`/`useReducer` for UI state
- Keep pages thin; extract reusable logic into `hooks/`

### 🧪 QA Agent
- Write tests in `backend/tests/` (pytest) and `frontend/src/__tests__/` (vitest)
- Each service function should have at least one unit test
- API endpoints should have integration tests using `httpx.AsyncClient`

---

## Coding Conventions

### Python (Backend)
- Python 3.11+, type-annotated everywhere
- `ruff` for linting, `black` for formatting
- All async routes; use `async def` throughout
- Raise `HTTPException` with meaningful status codes and `detail` strings
- Environment variables via `core/config.py` (`pydantic-settings`)

### JavaScript (Frontend)
- ES2022+, JSX
- Functional components only; no class components
- Named exports only (no default exports except pages)
- CSS Modules for component-scoped styles

---

## API Contract Rules

> The contract in `docs/api-contract.md` is the **source of truth**.

1. No agent may change an endpoint's method, path, or response shape without updating the contract first.
2. Breaking changes require a version bump (`/v2/...`).
3. All new endpoints must be documented before implementation begins.

---

## Workflow

```
1. Read AGENTS.md          (this file)
2. Read docs/api-contract.md
3. Understand the task scope
4. Make changes in the correct layer (route → service → db)
5. Update schemas.py if models change
6. Update api/client.js if contract changes
7. Write or update tests
8. Verify with: uvicorn app.main:app --reload  +  npm run dev
```

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `VECTOR_STORE_PATH` | Local ChromaDB persistence path | `./chroma_db` |
| `EMBEDDING_MODEL` | Sentence-transformers model name | `all-MiniLM-L6-v2` |
| `OPENAI_API_KEY` | OpenAI key (optional, for GPT embeddings) | — |
| `MAX_DIFF_CHARS` | Max chars of diff to embed per commit | `4000` |
| `LOG_LEVEL` | Python log level | `INFO` |

---

## Do Not

- ❌ Add business logic inside route handlers
- ❌ Hardcode paths, keys, or model names — use `config.py`
- ❌ Import from `frontend/` inside `backend/` or vice-versa
- ❌ Change the frozen API contract without updating `docs/api-contract.md`
- ❌ Commit `.env` files
