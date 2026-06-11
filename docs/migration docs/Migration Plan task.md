# ReasonSQL 2.0 — Execution Tracker

## Decisions
- vLLM: Optional (commented-out in docker-compose)
- LangSmith: Optional (env-var opt-in, added to .env.example)
- Database: PostgreSQL only (SQLite removed)

## Tasks

### 1. Git & Setup
- [x] Verify on branch `2.0`
- [ ] Create task tracker (this file)

### 2. Dependencies & Config
- [ ] Rewrite `requirements.txt`
- [ ] Update `.env.example` with new vars
- [ ] Rewrite `configs/settings.py` (remove crewai, add LangSmith/vLLM/SQLAlchemy config)

### 3. Database Layer — SQLAlchemy
- [ ] Rewrite `backend/db_connection.py` with SQLAlchemy engine + session
- [ ] Remove SQLite support paths

### 4. RAG Pipeline — FAISS + Hybrid + Cross-Encoder
- [ ] Delete `backend/utils/vector_search.py`
- [ ] Create `backend/retrieval/__init__.py`
- [ ] Create `backend/retrieval/schema_indexer.py` (FAISS via LangChain)
- [ ] Create `backend/retrieval/hybrid_retriever.py` (BM25 + FAISS + CrossEncoder)

### 5. LLM Layer — LangChain
- [ ] Create `backend/llm/__init__.py`
- [ ] Create `backend/llm/providers.py` (ChatLiteLLM fallback chain + vLLM/Qwen)
- [ ] Create `backend/llm/prompts.py` (ChatPromptTemplate for each agent)

### 6. Orchestrator — LangGraph StateGraph
- [ ] Delete old orchestrator files (crew, enhanced, deterministic, quota)
- [ ] Create `backend/graph/__init__.py`
- [ ] Create `backend/graph/state.py` (TypedDict PipelineState)
- [ ] Create `backend/graph/nodes.py` (7 node functions)
- [ ] Create `backend/graph/pipeline.py` (StateGraph compile + routing)
- [ ] Update `backend/orchestrator/__init__.py` to re-export from graph

### 7. API Layer Adaptation
- [ ] Update `backend/api/deps.py` (get_orchestrator → LangGraph pipeline)
- [ ] Update `backend/api/routers/query.py` (.ainvoke + map to FinalResponse)
- [ ] Update `backend/api/main.py` (version bump, lifespan updates)

### 8. Docker — Multi-Container
- [ ] Rewrite `Dockerfile` (FastAPI, not Streamlit; install libpq-dev)
- [ ] Rewrite `docker-compose.yml` (postgres + backend + vllm-optional)
- [ ] Create `data/init.sql` (Chinook PostgreSQL seed script symlink)

### 9. Cleanup & Documentation
- [ ] Update `README.md` (new tech stack, architecture, quick start)
- [ ] Update `backend/utils/__init__.py` if needed
- [ ] Verify all imports resolve
