# ReasonSQL 2.0 — Walkthrough

## Summary

Successfully upgraded ReasonSQL from a custom orchestrator + CrewAI system to a production-grade AI/ML architecture on branch `2.0`. Committed as `acae81a` (29 files changed, 3674 insertions, 5221 deletions).

---

## What Was Built

### 1. LangGraph StateGraph Pipeline
**File:** [backend/graph/pipeline.py](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/backend/graph/pipeline.py)

Replaced the 1440-line `BatchOptimizedOrchestrator` with a compiled LangGraph `StateGraph`. 7 nodes with conditional routing:

```
schema_retrieval → reasoning → sql_generation → safety_validation
    → sql_execution → [self_correction] → response_synthesis → END
```

**Routing logic:**
- After reasoning: `DATA_QUERY → sql_generation`, `META_QUERY/AMBIGUOUS → response_synthesis`
- After safety: `approved → sql_execution`, `rejected → self_correction` (max 2 retries)
- After execution: `success → response_synthesis`, `error → self_correction`

### 2. Hybrid RAG + Cross-Encoder

| Component | File |
|-----------|------|
| FAISS index builder | [backend/retrieval/schema_indexer.py](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/backend/retrieval/schema_indexer.py) |
| BM25 + FAISS + CrossEncoder | [backend/retrieval/hybrid_retriever.py](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/backend/retrieval/hybrid_retriever.py) |

Pipeline: `BM25(k) + FAISS(k)` → `Reciprocal Rank Fusion` → `CrossEncoder rerank` → `top-N tables`

### 3. LangChain LLM Layer

| Component | File |
|-----------|------|
| Provider factory | [backend/llm/providers.py](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/backend/llm/providers.py) |
| ChatPromptTemplates | [backend/llm/prompts.py](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/backend/llm/prompts.py) |

Fallback chain via LangChain's `.with_fallbacks()`:
```
Gemini (ChatLiteLLM) → Groq 8B (ChatLiteLLM) → Qwen (ChatOpenAI @ vLLM)
```

### 4. SQLAlchemy Database Layer
**File:** [backend/db_connection.py](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/backend/db_connection.py)

- Sync engine (psycopg2) + async engine (asyncpg)
- `QueuePool` connection pooling
- Schema introspection via `sqlalchemy.inspect` (no raw SQL)
- PostgreSQL only — SQLite entirely removed

### 5. Docker Compose
**File:** [docker-compose.yml](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/docker-compose.yml)

- `pgvector/pgvector:pg16` — PostgreSQL with pgvector, Chinook auto-seeded
- `backend` — Multi-stage FastAPI image
- `vllm` — Commented-out optional service for Qwen on GPU

### 6. LangSmith Observability
Auto-enabled when `LANGCHAIN_TRACING_V2=true` — no code changes needed. LangSmith hooks in at the LangChain SDK level.

---

## Resume Keyword Mapping

| Keyword | Where Genuinely Used |
|---------|---------------------|
| **LangChain** | `ChatLiteLLM`, `ChatOpenAI`, `ChatPromptTemplate`, `HuggingFaceEmbeddings`, `.with_fallbacks()` |
| **LangGraph** | `StateGraph`, 7 nodes, conditional edges, `PipelineState` TypedDict |
| **LangSmith** | Auto-tracing via `LANGCHAIN_TRACING_V2=true` env var |
| **FAISS** | `FAISS.from_documents()`, `similarity_search_with_score()`, persist/load |
| **Hybrid Retrieval** | BM25 + FAISS + Reciprocal Rank Fusion in `HybridSchemaRetriever` |
| **Cross-Encoder Reranking** | `CrossEncoder("ms-marco-MiniLM-L-6-v2").predict()` |
| **Vector Search** | FAISS ANN index for schema table retrieval |
| **RAG** | Schema context injected into every LLM prompt via retrieval |
| **SQLAlchemy** | `create_engine`, `create_async_engine`, `inspect`, `SessionLocal` |
| **Docker** | Multi-stage `Dockerfile`, multi-service `docker-compose.yml` |
| **PostgreSQL** | `pgvector/pgvector:pg16` image, `asyncpg` driver, pgvector extension |
| **Qwen** | `Qwen/Qwen2.5-Coder-32B-Instruct` via `ChatOpenAI` → vLLM endpoint |
| **vLLM** | OpenAI-compatible server for Qwen (optional Docker service) |

---

## How to Verify

```bash
# 1. Start services
docker-compose up -d

# 2. Check health
curl http://localhost:8000/health

# 3. Run a query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How many customers are there?", "database_id": "default"}'

# 4. Enable LangSmith to see traces
# Set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY in .env
# Visit https://smith.langchain.com
```

---

## What's NOT Changed (main branch safe)

- `main` branch is completely untouched — all changes are on `2.0`
- Frontend (`frontend-next/`) is unchanged — API response format preserved
- `data/Chinook_PostgreSql.sql` — used as-is for Docker seeding
- Test files in `tests/` — need update for new architecture (future work)
