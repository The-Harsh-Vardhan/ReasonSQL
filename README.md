# ReasonSQL 2.0 — Multi-Agent NL→SQL System

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![LangChain](https://img.shields.io/badge/LangChain-0.3+-1C3C3C.svg)](https://langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-FF6B6B.svg)](https://langchain-ai.github.io/langgraph/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![FAISS](https://img.shields.io/badge/FAISS-1.8+-blue.svg)](https://faiss.ai/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)
[![LangSmith](https://img.shields.io/badge/LangSmith-Tracing-orange.svg)](https://smith.langchain.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Why simple "prompt → SQL" fails, and how a LangGraph multi-agent pipeline with hybrid RAG fixes it.**

ReasonSQL turns a plain-English question into a validated, executed PostgreSQL query and an explained answer. A LangGraph `StateGraph` routes each question through hybrid schema retrieval, intent analysis and clarification, SQL generation, a deterministic safety validator, execution, and a self-correction loop. A FastAPI backend serves it to a Next.js dashboard.

🔗 **[Live Demo →](https://reason-sql.vercel.app)** · 📚 **[Docs site →](https://the-harsh-vardhan.github.io/ReasonSQL/)**

**Result:** ~50% accuracy → **85%+ on complex multi-join queries.** This is the project's previously reported figure; a reproducible baseline-vs-pipeline evaluation (`reasonsql eval --baseline`) is tracked in [#6](https://github.com/The-Harsh-Vardhan/ReasonSQL/issues/6).

---

## What it does

- **Retrieves only the relevant tables.** For schemas above 5 tables, BM25 keyword search and FAISS semantic search are fused with Reciprocal Rank Fusion and reranked by a cross-encoder (`ms-marco-MiniLM-L-6-v2`).
- **Analyzes and clarifies before writing SQL.** One reasoning step does intent analysis (`DATA_QUERY`, `META_QUERY`, `AMBIGUOUS`), clarification, decomposition and planning. Ambiguous questions ("best", "recent") get targeted questions back instead of a guess.
- **Validates SQL deterministically.** A rule-based safety node blocks `DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`, `CREATE`, `TRUNCATE` and `SELECT *`, and adds a `LIMIT` when one is missing. No LLM call.
- **Fixes its own errors.** Safety rejections and execution errors loop through a self-correction agent (up to 2 retries by default), and every corrected query is re-validated.
- **Is traceable.** The API returns a full reasoning trace, and LangSmith tracing is opt-in. LLM calls fall back Gemini → Groq → Qwen (vLLM, optional).

---

## Architecture

The diagram is traced from `backend/graph/pipeline.py` (`build_pipeline`). Edge labels are the return values of the routing functions; any node that sets `pipeline_error` routes straight to `END`.

```mermaid
flowchart TD
    START([START]) --> SR["schema_retrieval<br/>BM25 + FAISS + RRF + cross-encoder"]
    SR -->|ok| RS["reasoning<br/>intent, clarification, plan"]
    SR -->|pipeline_error| END_([END])
    RS -->|DATA_QUERY| SG["sql_generation"]
    RS -->|"META_QUERY / AMBIGUOUS"| SY["response_synthesis"]
    RS -->|pipeline_error| END_
    SG --> SV["safety_validation<br/>rule-based, no LLM"]
    SV -->|approved| EX["sql_execution<br/>SQLAlchemy async"]
    SV -->|"rejected, retries left"| SC["self_correction"]
    SV -->|"rejected, retries exhausted"| SY
    EX -->|success| SY
    EX -->|"error, retries left"| SC
    EX -->|"error, retries exhausted"| SY
    SC -->|"re-validate"| SV
    SC -->|pipeline_error| END_
    SY --> END_
```

The clarification agent is one of four logical agents batched into the `reasoning` node's single LLM call (intent analyzer, clarification agent, query decomposer, query planner). Node-by-node notes, the retrieval pipeline and the deployment topology are in [`docs/architecture.md`](docs/architecture.md). The v1 orchestrator design is kept for history in [`docs/AGENT_PIPELINE.md`](docs/AGENT_PIPELINE.md).

---

## ⚡ Naive vs ReasonSQL

| ❌ Naive Approach | ✅ ReasonSQL 2.0 |
|-------------------|----------------|
| Schema + Question → LLM → SQL | LangGraph StateGraph with 7 specialized nodes |
| Hallucinates table names | Hybrid RAG (BM25 + FAISS + CrossEncoder) finds relevant tables |
| Assumes meaning of "recent", "best" | ClarificationAgent asks targeted questions |
| Returns errors, not answers | Self-correction loop with up to 2 retries |
| No safety (SELECT * on 1M rows) | Rule-based safety validator enforces LIMIT + no SELECT * |
| Black box | LangSmith traces every LLM call, full reasoning trace in UI |

---

## 🚀 Quickstart

### Docker (PostgreSQL + FastAPI backend)

```bash
# 1. Clone
git clone https://github.com/The-Harsh-Vardhan/ReasonSQL.git
cd ReasonSQL

# 2. Configure
cp .env.example .env
# Add your GEMINI_API_KEY (required) and optionally LANGCHAIN_API_KEY

# 3. Launch (PostgreSQL + FastAPI backend)
docker-compose up -d

# 4. Verify
curl http://localhost:8000/health

# 5. Start frontend (new terminal)
cd frontend-next
npm install && npm run dev
# Visit http://localhost:3000
```

### CLI (`reasonsql`)

The package installs a `reasonsql` command with three subcommands (`backend/main.py`). Runtime dependencies live in `requirements.txt`, so install those first (inside a virtual environment).

```bash
pip install -r requirements.txt
pip install -e .

# Ask one question against the configured database (same LangGraph path as POST /query)
reasonsql ask "How many customers are there?"

# Several questions, one per line; --json prints the full API-shaped response
reasonsql ask --file queries.txt --json

# Start the FastAPI backend (defaults: 127.0.0.1:8000, reload off)
reasonsql serve --port 8000 --reload

# Run the golden-case evaluation against a running API; extra options pass through to scripts/evaluate.py
reasonsql eval --baseline --report docs/results/eval.md
```

`reasonsql ask` exits non-zero if any question fails. `python -m backend.main "question"` still works and is treated as `ask`. `reasonsql eval` needs the API running (`--api-url`, default `http://localhost:8000`); `--baseline` also runs each case as a single prompt on the same LLM and database for comparison. The golden cases are in `scripts/golden_cases.json`.

### Local Dev (without Docker)

```bash
# Install deps
pip install -r requirements.txt

# Ensure PostgreSQL is running (or use Docker for just postgres)
docker-compose up -d postgres

# Set DATABASE_URL in .env to localhost
# DATABASE_URL=postgresql://reasonsql:reasonsql@localhost:5432/reasonsql

# Start backend
uvicorn backend.api.main:app --port 8000 --reload
```

---

## ✨ What's New in v2.0

### LangChain + LangGraph Pipeline
- **LangGraph `StateGraph`** replaces the custom 1440-line orchestrator
- **7 specialized nodes** with conditional routing (intent-based, retry-based)
- **LangSmith tracing** — every LLM call, token count, and routing decision tracked
- **LangChain `ChatPromptTemplate`** for all prompts — composable, type-safe, traced

### Hybrid RAG + Cross-Encoder Reranking
- **FAISS vector index** (replaces hand-rolled cosine similarity)
- **BM25 keyword retrieval** combined with FAISS via Reciprocal Rank Fusion
- **Cross-Encoder reranking** (`ms-marco-MiniLM-L-6-v2`) for precision
- Only activates RAG for schemas with > 5 tables (configurable)

### SQLAlchemy + PostgreSQL
- Full **SQLAlchemy 2.0** ORM with async support (`asyncpg`)
- **Connection pooling** via `QueuePool` (configurable size)
- Schema introspection via `sqlalchemy.inspect` (no raw PRAGMA)
- **pgvector** extension support for future vector DB queries

### Docker + vLLM + Qwen
- **Multi-container Docker Compose**: `postgres` + `backend`
- **PostgreSQL 16 with pgvector** extension, Chinook dataset auto-seeded
- **vLLM** integration for self-hosted **Qwen2.5-Coder-32B** (optional, GPU)
- LLM fallback chain: **Gemini → Groq → Qwen (vLLM)**

---

## 🔬 Retrieval Pipeline (RAG)

```
User Query
    │
    ▼
┌────────────────────────────────────────────────────────┐
│ Hybrid Schema Retrieval                                │
│                                                        │
│  ┌──────────────┐    ┌────────────────────────────┐   │
│  │ BM25 Search  │    │ FAISS Semantic Search       │   │
│  │ (keyword)    │    │ (HuggingFace embeddings)    │   │
│  └──────┬───────┘    └────────────┬───────────────┘   │
│         │                        │                    │
│         └────────────┬───────────┘                    │
│                      ▼                                 │
│           Reciprocal Rank Fusion                       │
│                      │                                 │
│                      ▼                                 │
│         Cross-Encoder Reranking                        │
│       (ms-marco-MiniLM-L-6-v2)                         │
│                      │                                 │
│                      ▼                                 │
│         Top-N Most Relevant Tables                     │
└────────────────────────────────────────────────────────┘
    │
    ▼
Schema Context injected into LLM prompt
```

---

## 🔭 LangSmith Observability

Enable full tracing of every LLM call, graph node, and routing decision:

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__your_key_here
LANGCHAIN_PROJECT=ReasonSQL-2.0
```

Sign up free at [smith.langchain.com](https://smith.langchain.com). Once enabled, you'll see:
- Complete LangGraph execution graph visualization
- Per-node inputs/outputs and timing
- LLM call details (prompt, response, tokens, cost)
- Retry chains and routing decisions

---

## 🦾 Qwen + vLLM (Self-Hosted, Optional)

To run **Qwen2.5-Coder-32B-Instruct** locally via vLLM (requires NVIDIA GPU):

```bash
# 1. Uncomment vllm service in docker-compose.yml
# 2. Enable in .env:
ENABLE_VLLM_FALLBACK=true
VLLM_BASE_URL=http://vllm:8000/v1
VLLM_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct

# 3. Start all services
docker-compose up -d
```

The vLLM server exposes an OpenAI-compatible API endpoint. The pipeline uses it as a tertiary fallback when both Gemini and Groq are exhausted.

---

## 📁 Project Structure

```
ReasonSQL/
├── backend/
│   ├── main.py                 # 🆕 `reasonsql` CLI: ask / serve / eval
│   ├── api/                    # FastAPI routers, deps, schemas
│   ├── graph/                  # 🆕 LangGraph StateGraph pipeline
│   │   ├── state.py            #    TypedDict PipelineState
│   │   ├── nodes.py            #    7 node functions (agents)
│   │   └── pipeline.py         #    StateGraph compilation + routing
│   ├── llm/                    # 🆕 LangChain LLM providers
│   │   ├── providers.py        #    Gemini/Groq/Qwen with .with_fallbacks()
│   │   └── prompts.py          #    ChatPromptTemplate definitions
│   ├── retrieval/              # 🆕 Hybrid RAG pipeline
│   │   ├── schema_indexer.py   #    FAISS index via HuggingFaceEmbeddings
│   │   └── hybrid_retriever.py #    BM25 + FAISS + CrossEncoder reranking
│   ├── db_connection.py        # 🆕 SQLAlchemy engine + async sessions
│   ├── models/                 # Pydantic models (unchanged)
│   └── orchestrator/           # Compatibility shim → backend.graph
├── frontend-next/              # Next.js 16 Dashboard
├── scripts/
│   ├── evaluate.py             # Golden-case eval (--baseline, --report)
│   └── golden_cases.json       # 20 evaluation cases
├── tests/                      # pytest suite (API, adapters)
├── data/
│   └── Chinook_PostgreSql.sql  # Auto-seeded into Docker PostgreSQL
├── docs/                       # Pages site (Jekyll) + design notes, hosting, roadmap
├── configs/settings.py         # 🆕 PostgreSQL + LangSmith + FAISS config
├── pyproject.toml              # 🆕 installable package, `reasonsql` entry point
├── Dockerfile                  # 🆕 Multi-stage build for FastAPI
├── docker-compose.yml          # 🆕 postgres + backend + vllm (optional)
└── requirements.txt            # 🆕 LangChain ecosystem deps
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 16, React, Tailwind CSS |
| **Backend** | Python 3.11, FastAPI, Pydantic v2 |
| **Agentic Pipeline** | **LangGraph** `StateGraph` (7 nodes, conditional routing) |
| **LLM Framework** | **LangChain** (ChatPromptTemplate, LCEL, `.with_fallbacks()`) |
| **LLM Providers** | Gemini 2.0 Flash → Groq Llama-3.1-8B → **Qwen2.5-Coder-32B** (vLLM) |
| **Vector Search** | **FAISS** (ANN index via LangChain HuggingFaceEmbeddings) |
| **Hybrid Retrieval** | **BM25** (rank-bm25) + FAISS → Reciprocal Rank Fusion |
| **Reranking** | **Cross-Encoder** (`ms-marco-MiniLM-L-6-v2`) |
| **RAG** | Schema retrieval augments every SQL generation prompt |
| **Database** | **PostgreSQL 16** + pgvector, **SQLAlchemy 2.0** async |
| **LLM Serving** | **vLLM** (OpenAI-compatible Qwen inference server) |
| **Observability** | **LangSmith** (tracing, evaluation, debugging) |
| **Containerization** | **Docker** Compose multi-service setup |
| **Caching** | Redis (with in-memory fallback) |
| **CI/CD** | GitHub Actions |

---

## 📚 Docs

Docs site: **<https://the-harsh-vardhan.github.io/ReasonSQL/>** (source in [`docs/`](docs/)): [architecture](docs/architecture.md), [setup](docs/setup.md), [hosting guide](docs/HOSTING.md), [roadmap](docs/ROADMAP.md), [v1 pipeline design](docs/AGENT_PIPELINE.md).

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

<p align="center">
  <strong>ReasonSQL 2.0</strong><br>
  LangChain • LangGraph • FAISS • SQLAlchemy • PostgreSQL • vLLM • LangSmith<br><br>
  <a href="https://reason-sql.vercel.app">Live Demo</a> •
  <a href="https://github.com/The-Harsh-Vardhan/ReasonSQL">Source Code</a>
</p>
