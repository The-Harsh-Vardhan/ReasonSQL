# ReasonSQL 2.0 — Resume-Grade Architecture Upgrade

Upgrade the ReasonSQL backend from a custom orchestrator-based NL→SQL pipeline to a **LangChain + LangGraph** powered system with **FAISS vector search**, **hybrid retrieval**, **cross-encoder reranking**, **SQLAlchemy ORM**, **PostgreSQL** via Docker, **Qwen via vLLM**, and **LangSmith** observability. All changes on branch `2.0`, keeping `main` intact.

---

## User Review Required

> [!IMPORTANT]
> **Scope:** This plan restructures the entire backend pipeline. The frontend (Next.js) needs only a minor API-response adaptation and remains mostly untouched.

> [!WARNING]
> **Breaking Changes:**
> - The `crewai` dependency is fully removed (replaced by LangChain/LangGraph)
> - The custom `MultiProviderLLM` / `LLMClient` classes are replaced by LangChain's `ChatLiteLLM` / `ChatOpenAI` wrappers
> - The `BatchOptimizedOrchestrator` is replaced by a LangGraph `StateGraph`
> - The hand-rolled `SchemaVectorStore` (cosine similarity over numpy) is replaced by **FAISS** with hybrid retrieval
> - Docker Compose now runs **PostgreSQL + pgvector** as a first-class service alongside the backend

> [!IMPORTANT]
> **Resume Keyword Coverage:** The following technologies will be genuinely used (not just imported):
>
> | Keyword | Where Used |
> |---------|-----------|
> | **LangChain** | All LLM calls, prompt templates, output parsers, tool definitions |
> | **LangGraph** | Multi-agent pipeline as a compiled `StateGraph` with conditional edges |
> | **LangSmith** | Tracing/observability for every LLM call (env-var opt-in) |
> | **FAISS** | Vector index for schema embeddings (replaces hand-rolled cosine) |
> | **Hybrid Retrieval** | BM25 (keyword) + FAISS (semantic) fusion for schema selection |
> | **Cross-Encoder Reranking** | `cross-encoder/ms-marco-MiniLM-L-6-v2` reranks retrieval results |
> | **Vector Search** | FAISS `.similarity_search_with_score()` in the RAG pipeline |
> | **RAG** | Retrieval-Augmented Generation for schema context injection |
> | **SQLAlchemy** | All database connections via `create_engine` / `sessionmaker` |
> | **Docker** | Multi-container Compose: `backend`, `postgres`, `vllm` (optional) |
> | **PostgreSQL** | Local Dockerized Postgres replaces Supabase for dev; pgvector extension |
> | **Qwen** | `Qwen/Qwen2.5-Coder-32B-Instruct` as a vLLM-served model |
> | **vLLM** | OpenAI-compatible inference server for self-hosted Qwen |
> | **Prompt Engineering** | Structured multi-role prompts with LangChain `ChatPromptTemplate` |
> | **Agentic AI** | LangGraph nodes act as autonomous agents with tool access |
> | **Multi-Agent Systems** | 7 graph nodes (agents) with conditional routing |
> | **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` via `HuggingFaceEmbeddings` |
> | **Semantic Search** | FAISS + BM25 hybrid for schema table retrieval |
> | **Pydantic** | All state/response models remain Pydantic v2 |
> | **FastAPI** | API layer unchanged, just wires to new orchestrator |
> | **Async Python** | `asyncio`, `async/await` throughout the pipeline |

---

## Open Questions

> [!IMPORTANT]
> 1. **vLLM container**: The plan includes a `vllm` service in `docker-compose.yml` but it requires a **GPU machine** (or >32GB RAM for CPU). Should we:
>    - (a) Include it as an **optional** commented-out service (recommended — you can uncomment when you have a GPU)
>    - (b) Always include it (will fail on CPU-only machines)
>
> 2. **LangSmith**: Requires a free account at [smith.langchain.com](https://smith.langchain.com). The plan makes it **opt-in** via `LANGSMITH_API_KEY` env var. Is that okay, or do you want it always-on?
>
> 3. **PostgreSQL data**: The Docker Postgres will be seeded with the Chinook dataset via an init script. Should we also keep SQLite support for non-Docker local dev, or go Postgres-only?

---

## Proposed Changes

### 1. Dependency & Configuration Layer

#### [MODIFY] [requirements.txt](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/requirements.txt)

Complete rewrite. Remove `crewai`, `groq`, `streamlit`, `sentence-transformers` (standalone). Add:

```
# Core Framework
langchain>=0.3.0
langchain-community>=0.3.0
langchain-core>=0.3.0
langgraph>=0.2.0
langsmith>=0.2.0

# LLM Providers
litellm>=1.0.0
langchain-openai>=0.2.0          # For vLLM OpenAI-compat endpoint

# Embeddings & Vector Search
langchain-huggingface>=0.1.0     # HuggingFaceEmbeddings
faiss-cpu>=1.8.0                 # FAISS vector index
rank-bm25>=0.2.2                 # BM25 keyword retrieval (hybrid)
sentence-transformers>=3.0.0     # Embedding model backend

# Cross-Encoder Reranking
langchain-community>=0.3.0       # CrossEncoderReranker
# (cross-encoder model loaded via sentence-transformers)

# Database
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
asyncpg>=0.29.0
pgvector>=0.3.0                  # pgvector SQLAlchemy integration

# API
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
httpx>=0.26.0
python-multipart>=0.0.6

# Data
pydantic>=2.0.0
pandas>=2.0.0
openpyxl>=3.1.0
tabulate>=0.9.0

# Utilities
python-dotenv>=1.0.0
rich>=13.0.0
redis[hiredis]>=5.0.0
```

---

#### [MODIFY] [.env.example](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/.env.example)

Add new env vars for LangSmith, vLLM, PostgreSQL Docker:

```env
# LangSmith (optional — enables tracing)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__your_key_here
LANGCHAIN_PROJECT=ReasonSQL-2.0

# vLLM (optional — self-hosted Qwen)
VLLM_BASE_URL=http://localhost:8001/v1
VLLM_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct

# PostgreSQL (Docker)
DATABASE_URL=postgresql://reasonsql:reasonsql@localhost:5432/reasonsql
```

---

#### [MODIFY] [configs/settings.py](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/configs/settings.py)

- Remove `crewai` import and `get_llm()` function
- Add LangSmith configuration (auto-detected from env vars)
- Add vLLM endpoint configuration
- Add SQLAlchemy engine factory (`get_sqlalchemy_engine()`)
- Keep agent prompts but restructure them as LangChain `ChatPromptTemplate` references

---

### 2. Database Layer — SQLAlchemy

#### [MODIFY] [backend/db_connection.py](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/backend/db_connection.py)

Complete rewrite to use **SQLAlchemy**:

```python
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    poolclass=QueuePool,
    echo=False
)
SessionLocal = sessionmaker(bind=engine)
```

Key changes:
- `get_connection()` → `get_session()` returning SQLAlchemy `Session`
- `execute_query()` → uses `session.execute(text(sql))`
- `get_tables()` → uses `inspect(engine).get_table_names()`
- `get_table_columns()` → uses `inspect(engine).get_columns(table)`
- Schema introspection via `sqlalchemy.inspect` instead of raw PRAGMA/information_schema
- Async support via `create_async_engine` + `asyncpg`
- Connection pooling via SQLAlchemy's built-in `QueuePool`

---

### 3. RAG Pipeline — FAISS + Hybrid Retrieval + Cross-Encoder

#### [DELETE] [backend/utils/vector_search.py](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/backend/utils/vector_search.py)

Replaced by the new retrieval module.

#### [NEW] `backend/retrieval/__init__.py`

Module init.

#### [NEW] `backend/retrieval/schema_indexer.py`

Builds and persists a **FAISS index** of schema embeddings:

```python
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

class SchemaIndexer:
    """Indexes database schema into FAISS for semantic retrieval."""
    
    def __init__(self, embedding_model="all-MiniLM-L6-v2"):
        self.embeddings = HuggingFaceEmbeddings(model_name=embedding_model)
        self.vectorstore: Optional[FAISS] = None
    
    def index_schema(self, tables: Dict[str, str]) -> FAISS:
        """Create FAISS index from table schemas."""
        docs = [
            Document(page_content=schema_text, metadata={"table": name})
            for name, schema_text in tables.items()
        ]
        self.vectorstore = FAISS.from_documents(docs, self.embeddings)
        return self.vectorstore
```

#### [NEW] `backend/retrieval/hybrid_retriever.py`

Implements **Hybrid Retrieval** (BM25 + FAISS) with **Cross-Encoder Reranking**:

```python
from rank_bm25 import BM25Okapi
from langchain_community.vectorstores import FAISS
from sentence_transformers import CrossEncoder

class HybridSchemaRetriever:
    """
    Hybrid Retrieval: BM25 (keyword) + FAISS (semantic) → Cross-Encoder Reranking.
    
    Pipeline:
    1. BM25 retrieves top-K candidates by keyword match
    2. FAISS retrieves top-K candidates by semantic similarity
    3. Reciprocal Rank Fusion (RRF) merges both result sets
    4. Cross-Encoder reranks top-N fused results for precision
    """
    
    def __init__(self, vectorstore: FAISS, documents: List[Document]):
        self.vectorstore = vectorstore
        self.bm25 = BM25Okapi([doc.page_content.split() for doc in documents])
        self.documents = documents
        self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    
    def retrieve(self, query: str, k: int = 10, rerank_top_n: int = 5) -> List[str]:
        """Hybrid retrieve + rerank, returns table names."""
        # 1. BM25 keyword retrieval
        bm25_scores = self.bm25.get_scores(query.split())
        bm25_ranked = sorted(enumerate(bm25_scores), key=lambda x: x[1], reverse=True)[:k]
        
        # 2. FAISS semantic retrieval
        faiss_results = self.vectorstore.similarity_search_with_score(query, k=k)
        
        # 3. Reciprocal Rank Fusion
        fused = self._reciprocal_rank_fusion(bm25_ranked, faiss_results)
        
        # 4. Cross-Encoder reranking
        reranked = self._cross_encoder_rerank(query, fused[:rerank_top_n])
        
        return [doc.metadata["table"] for doc in reranked]
```

---

### 4. LLM Layer — LangChain

#### [DELETE] [backend/orchestrator/llm_client.py](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/backend/orchestrator/llm_client.py)

The entire 768-line custom LLM client is replaced by LangChain wrappers.

#### [NEW] `backend/llm/providers.py`

LangChain-based LLM provider factory:

```python
from langchain_community.chat_models import ChatLiteLLM
from langchain_openai import ChatOpenAI

def get_primary_llm() -> BaseChatModel:
    """Gemini via LiteLLM."""
    return ChatLiteLLM(model="gemini/gemini-2.0-flash", temperature=0.1)

def get_fallback_llm() -> BaseChatModel:
    """Groq via LiteLLM.""" 
    return ChatLiteLLM(model="groq/llama-3.1-8b-instant", temperature=0.1)

def get_vllm_llm() -> BaseChatModel:
    """Qwen via vLLM (self-hosted OpenAI-compatible endpoint)."""
    return ChatOpenAI(
        base_url=VLLM_BASE_URL,
        model=VLLM_MODEL,  # Qwen/Qwen2.5-Coder-32B-Instruct
        temperature=0.1,
        max_tokens=512
    )

def get_llm_with_fallback() -> RunnableWithFallbacks:
    """LangChain fallback chain: Gemini → Groq → vLLM/Qwen."""
    return get_primary_llm().with_fallbacks([
        get_fallback_llm(),
        get_vllm_llm()
    ])
```

#### [NEW] `backend/llm/prompts.py`

LangChain `ChatPromptTemplate` definitions for each agent role. Migrates the string prompts from `configs/settings.py` to structured templates with input variables.

---

### 5. Orchestrator — LangGraph StateGraph

#### [DELETE] [backend/orchestrator/batch_optimized_orchestrator.py](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/backend/orchestrator/batch_optimized_orchestrator.py)

The 1440-line monolith is replaced by a LangGraph graph.

#### [NEW] `backend/graph/__init__.py`

Module init.

#### [NEW] `backend/graph/state.py`

LangGraph-compatible state definition using `TypedDict`:

```python
from typing import TypedDict, Annotated, List, Optional
from langgraph.graph.message import add_messages

class PipelineState(TypedDict):
    """LangGraph state for the NL→SQL pipeline."""
    user_query: str
    messages: Annotated[list, add_messages]
    
    # Schema & Retrieval
    schema_context: str
    retrieved_tables: List[str]
    retrieval_method: str  # "hybrid_rag" | "full_schema"
    
    # Intent & Planning
    intent: str  # DATA_QUERY | META_QUERY | AMBIGUOUS
    intent_confidence: float
    resolved_query: str
    query_plan: str
    assumptions: List[str]
    
    # SQL Generation & Execution
    generated_sql: str
    safety_approved: bool
    safety_violations: List[str]
    execution_result: Optional[List]
    execution_error: str
    
    # Control Flow
    retry_count: int
    max_retries: int
    
    # Response
    final_answer: str
    reasoning_trace: List[dict]
```

#### [NEW] `backend/graph/nodes.py`

Each LangGraph node is a function (agent):

```python
async def schema_retrieval_node(state: PipelineState) -> PipelineState:
    """RAG node: Hybrid retrieval + cross-encoder reranking for schema."""
    ...

async def reasoning_node(state: PipelineState) -> PipelineState:
    """LLM node: Intent analysis + clarification + planning."""
    ...

async def sql_generation_node(state: PipelineState) -> PipelineState:
    """LLM node: Generate SQL from plan + schema context."""
    ...

def safety_validation_node(state: PipelineState) -> PipelineState:
    """Deterministic node: Rule-based SQL safety checks."""
    ...

async def sql_execution_node(state: PipelineState) -> PipelineState:
    """Deterministic node: Execute SQL via SQLAlchemy."""
    ...

async def self_correction_node(state: PipelineState) -> PipelineState:
    """LLM node: Fix SQL errors (conditional)."""
    ...

async def response_synthesis_node(state: PipelineState) -> PipelineState:
    """LLM node: Generate human-readable answer."""
    ...
```

#### [NEW] `backend/graph/pipeline.py`

The compiled LangGraph pipeline:

```python
from langgraph.graph import StateGraph, END

def build_pipeline() -> StateGraph:
    """Build the LangGraph NL→SQL pipeline."""
    graph = StateGraph(PipelineState)
    
    # Add nodes (agents)
    graph.add_node("schema_retrieval", schema_retrieval_node)
    graph.add_node("reasoning", reasoning_node)
    graph.add_node("sql_generation", sql_generation_node)
    graph.add_node("safety_validation", safety_validation_node)
    graph.add_node("sql_execution", sql_execution_node)
    graph.add_node("self_correction", self_correction_node)
    graph.add_node("response_synthesis", response_synthesis_node)
    
    # Define edges
    graph.set_entry_point("schema_retrieval")
    graph.add_edge("schema_retrieval", "reasoning")
    graph.add_conditional_edges("reasoning", route_after_reasoning)
    graph.add_edge("sql_generation", "safety_validation")
    graph.add_conditional_edges("safety_validation", route_after_safety)
    graph.add_conditional_edges("sql_execution", route_after_execution)
    graph.add_edge("self_correction", "safety_validation")
    graph.add_edge("response_synthesis", END)
    
    return graph.compile()
```

Conditional routing functions:
- `route_after_reasoning`: → `response_synthesis` if META_QUERY, → `sql_generation` if DATA_QUERY
- `route_after_safety`: → `sql_execution` if approved, → `self_correction` if violations
- `route_after_execution`: → `response_synthesis` if success, → `self_correction` if error (max retries)

---

### 6. API Layer Adaptation

#### [MODIFY] [backend/api/deps.py](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/backend/api/deps.py)

Update `get_orchestrator()` to return the compiled LangGraph pipeline instead of `BatchOptimizedOrchestrator`.

#### [MODIFY] [backend/api/routers/query.py](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/backend/api/routers/query.py)

Update the `/query` endpoint to invoke the LangGraph pipeline via `.ainvoke()` and map the `PipelineState` output to the existing `FinalResponse` schema.

---

### 7. Docker — Multi-Container Setup

#### [MODIFY] [Dockerfile](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/Dockerfile)

Update to:
- Use `python:3.11-slim` (keep)
- Install `libpq-dev` for `psycopg2` compilation
- Run `uvicorn backend.api.main:app` instead of Streamlit
- Multi-stage build for smaller image

#### [MODIFY] [docker-compose.yml](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/docker-compose.yml)

Full rewrite with 3 services:

```yaml
services:
  # PostgreSQL with pgvector
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: reasonsql
      POSTGRES_USER: reasonsql
      POSTGRES_PASSWORD: reasonsql
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./data/init.sql:/docker-entrypoint-initdb.d/01-chinook.sql

  # FastAPI Backend
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://reasonsql:reasonsql@postgres:5432/reasonsql
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - LANGCHAIN_TRACING_V2=${LANGCHAIN_TRACING_V2:-false}
      - LANGCHAIN_API_KEY=${LANGCHAIN_API_KEY:-}
    depends_on:
      postgres:
        condition: service_healthy

  # vLLM (optional — requires GPU)
  # Uncomment to self-host Qwen
  # vllm:
  #   image: vllm/vllm-openai:latest
  #   command: --model Qwen/Qwen2.5-Coder-32B-Instruct --max-model-len 4096
  #   ports:
  #     - "8001:8000"
  #   deploy:
  #     resources:
  #       reservations:
  #         devices:
  #           - capabilities: [gpu]

volumes:
  pgdata:
```

#### [NEW] `data/init.sql`

PostgreSQL version of Chinook schema + data for Docker auto-seeding (already exists as `data/Chinook_PostgreSql.sql`, just needs to be referenced).

---

### 8. Cleanup & Migration

#### [DELETE] `backend/orchestrator/crew_orchestrator.py` — CrewAI-based orchestrator (dead code)
#### [DELETE] `backend/orchestrator/enhanced_orchestrator.py` — Old orchestrator variant
#### [DELETE] `backend/orchestrator/deterministic_orchestrator.py` — Old orchestrator variant
#### [DELETE] `backend/orchestrator/quota_optimized_orchestrator.py` — Old orchestrator variant
#### [MODIFY] `backend/orchestrator/__init__.py` — Re-export from new `backend.graph` module

#### [MODIFY] [README.md](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/README.md)

Update Tech Stack table, architecture diagram, and Quick Start to reflect:
- LangChain + LangGraph pipeline
- FAISS + Hybrid Retrieval + Cross-Encoder
- Docker Compose with PostgreSQL
- vLLM / Qwen integration
- LangSmith observability

---

## Architecture Diagram (v2.0)

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Next.js Frontend                              │
│                  POST /query → FastAPI Backend                      │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│                   FastAPI + LangGraph Pipeline                      │
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │   Schema     │───▶│  Reasoning   │───▶│   SQL Generation     │  │
│  │  Retrieval   │    │  (LangChain) │    │   (LangChain)        │  │
│  │  (FAISS+BM25 │    └──────────────┘    └──────────┬───────────┘  │
│  │  +CrossEnc.) │                                    │              │
│  └──────────────┘                         ┌──────────▼───────────┐  │
│                                           │  Safety Validation   │  │
│  ┌──────────────┐    ┌──────────────┐     │  (Deterministic)     │  │
│  │  Response    │◀───│     SQL      │◀────└──────────────────────┘  │
│  │  Synthesis   │    │  Execution   │                               │
│  │  (LangChain) │    │ (SQLAlchemy) │     ┌──────────────────────┐  │
│  └──────────────┘    └──────────────┘  ◀──│  Self-Correction     │  │
│                                           │  (LangChain, cond.)  │  │
│                                           └──────────────────────┘  │
│                                                                     │
│  LLM Fallback Chain: Gemini → Groq → Qwen (vLLM)                  │
│  Observability: LangSmith Tracing                                   │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│              Docker Compose Infrastructure                          │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  PostgreSQL  │  │   FastAPI    │  │  vLLM (Qwen, optional)  │  │
│  │  + pgvector  │  │   Backend    │  │  GPU-accelerated         │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Verification Plan

### Automated Tests
```bash
# 1. Docker stack spins up
docker-compose up -d
docker-compose ps  # All services healthy

# 2. Backend health check
curl http://localhost:8000/health

# 3. Query execution (smoke test)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How many customers are there?"}'

# 4. Unit tests
python -m pytest tests/ -v
```

### Manual Verification
- Verify LangSmith dashboard shows traces for LLM calls
- Verify FAISS retrieval selects correct tables
- Verify cross-encoder reranking improves table selection over pure FAISS
- Verify the LangGraph pipeline visualization in LangSmith
- Verify Docker Compose starts all services cleanly
- Verify the frontend still works with the new backend
