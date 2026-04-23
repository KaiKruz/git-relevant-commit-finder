# 🔍 Git Relevant Commit Finder

> Intelligently surface the git commits that actually matter — by querying your repository history with natural language.

---

## Overview

**Git Relevant Commit Finder** is a full-stack tool that lets developers search a git repository's commit history using semantic / natural-language queries rather than raw `git log` filters.

Given a repo (local path or GitHub URL) and a question like _"when did we migrate from REST to GraphQL?"_ or _"which commits touched the authentication module in Q1?"_, the system:

1. Indexes commit metadata + diffs via embeddings.
2. Runs a semantic search against the index.
3. Returns a ranked list of the most relevant commits with explanations.

---

## Features

| Feature | Status |
|---|---|
| Ingest local git repo | ✅ planned |
| Ingest remote GitHub repo (clone) | ✅ planned |
| Semantic search over commits | ✅ planned |
| Filter by author / date / branch | ✅ planned |
| Diff-level relevance highlights | ✅ planned |
| REST API (FastAPI) | ✅ planned |
| Web UI (React + Vite) | ✅ planned |
| CLI mode | ✅ planned |

---

## Architecture

```
┌─────────────────────────────────────────────┐
│                  Frontend                    │
│         React + Vite  (port 5173)           │
└────────────────────┬────────────────────────┘
                     │  REST / JSON
┌────────────────────▼────────────────────────┐
│                  Backend                     │
│          FastAPI  (port 8000)               │
│  ┌─────────────┐   ┌──────────────────────┐ │
│  │  Ingestor   │   │   Search Engine      │ │
│  │  (gitpython)│   │   (embeddings +      │ │
│  │             │   │    vector store)     │ │
│  └─────────────┘   └──────────────────────┘ │
└────────────────────┬────────────────────────┘
                     │
         ┌───────────▼────────────┐
         │   Vector Store         │
         │   (ChromaDB / local)   │
         └────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Git

### Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Project Structure

```
git-relevant-commit-finder/
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── main.py           # App entry point & router registration
│   │   ├── api/              # Route handlers
│   │   │   ├── repos.py      # /repos endpoints
│   │   │   └── search.py     # /search endpoints
│   │   ├── core/             # Config, settings, logging
│   │   │   └── config.py
│   │   ├── services/         # Business logic
│   │   │   ├── ingestor.py   # Git repo ingestion
│   │   │   ├── embedder.py   # Embedding generation
│   │   │   └── searcher.py   # Semantic search
│   │   ├── models/           # Pydantic schemas
│   │   │   └── schemas.py
│   │   └── db/               # Vector store client
│   │       └── vector_store.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/                 # React + Vite application
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── api/              # API client layer
│   │   │   └── client.js
│   │   ├── components/       # Reusable UI components
│   │   ├── pages/            # Page-level components
│   │   └── hooks/            # Custom React hooks
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── docs/
│   └── api-contract.md       # Frozen API contract
├── AGENTS.md                 # AI agent roles & workflow
└── README.md
```

---

## API Contract

See [`docs/api-contract.md`](docs/api-contract.md) for the frozen REST API specification.

---

## License

MIT
