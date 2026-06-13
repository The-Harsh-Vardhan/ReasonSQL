# ReasonSQL 2.0 — What's New & What You Can Build

## 1.0 vs 2.0 at a Glance

| Dimension | 1.0 | 2.0 |
|-----------|-----|-----|
| **Orchestration** | Custom monolithic classes (4 competing files) | LangGraph `StateGraph` (single declarative graph) |
| **LLM Layer** | Custom `MultiProviderLLM` wrapper | LangChain LCEL + `.with_fallbacks()` |
| **Schema Retrieval** | Full schema dump to every prompt | Hybrid BM25 + FAISS + CrossEncoder RAG |
| **Database** | SQLite (file-based) | PostgreSQL via SQLAlchemy async/sync |
| **Observability** | `print()` / `logging` | LangSmith — full graph traces, token counts, latency |
| **API style** | Sync FastAPI | Async FastAPI (`asyncio.wait_for`) |
| **Multi-turn** | ❌ None | ✅ Conversation history (last 5 turns) |
| **Self-correction** | Hardcoded retry loop | LangGraph conditional edge routing (pluggable) |
| **State typing** | `dict` or ad-hoc attrs | `TypedDict PipelineState` (fully typed) |
| **File upload** | ❌ None | ✅ CSV, Excel, SQLite (auto-ingested) |
| **Testing** | Manual only | `tests/test_migration.py` (structured test suite) |

---

## What 2.0 Gave You (Concrete Advantages)

### 1 — Declarative, Auditable Pipeline
```
1.0: 4 competing orchestrator files, hardcoded if/else routing
2.0: One `StateGraph` in pipeline.py — every node, edge, and conditional route is visible
```
You can open `backend/graph/pipeline.py` and read the entire execution flow like a diagram. Adding a new agent is just `graph.add_node("my_agent", my_fn)` + one new edge. In 1.0, you'd have to modify a 1,000-line orchestrator class.

### 2 — Hybrid Schema Retrieval (Scales to Large DBs)
```
1.0: SELECT * schema → paste into prompt (token cost grows O(n tables))
2.0: BM25 keyword + FAISS vector + CrossEncoder reranking → top-5 tables only
```
For the 12-table Chinook DB the difference is small. But connect a 200-table enterprise DB and 1.0 would blow the context window; 2.0 picks the right 5-10 tables automatically.

### 3 — LangChain LCEL + Automatic Fallbacks
```
1.0: Custom exception-catching try/except switching between providers
2.0: primary.with_fallbacks([groq_llm, qwen_vllm])
```
LangChain's `with_fallbacks()` is transparent to your prompts — if Gemini returns a 429, Groq kicks in automatically with zero code changes. You can add Anthropic Claude as a fourth fallback with one line.

### 4 — LangSmith Observability (set `LANGCHAIN_TRACING_V2=true`)
- Every node in the graph appears as a separate span in LangSmith UI
- Full prompt + response for each LLM call
- Token usage, latency, cost per call
- Retry chains are visually linked to the original query

### 5 — Async-First Architecture
```
1.0: Sync execute_query() → blocked the event loop during DB I/O
2.0: AsyncSession + asyncpg → true async throughout FastAPI
```
This means concurrent queries don't block each other. If 10 users query simultaneously, 1.0 would serialize them; 2.0 handles them in parallel.

### 6 — Typed PipelineState
Every piece of data flowing through the pipeline is declared in `state.py`. You get autocomplete, runtime validation, and a self-documenting data contract. No more "what keys does this dict have?" debugging.

---

## Feature Roadmap — What You Can Build Now

These are **directly unlocked** by the 2.0 tech stack and would be very hard/impossible in 1.0.

### 🟢 Easy (1–2 days each)

#### A. Streaming Responses via Server-Sent Events
LangChain LCEL supports `.astream()` natively. Instead of waiting 7s for a response, you can stream each agent's progress to the frontend in real-time.
```python
# backend/api/routers/query.py
from fastapi.responses import StreamingResponse

@router.post("/query/stream")
async def stream_query(request: QueryRequest):
    async def generator():
        async for chunk in pipeline.astream(initial_state):
            yield f"data: {json.dumps(chunk)}\n\n"
    return StreamingResponse(generator(), media_type="text/event-stream")
```
Frontend already shows `ProcessingDiagram` — hook it up to SSE and the diagram becomes a **live step-by-step animation**.

#### B. Per-Query LangSmith Feedback Buttons
LangSmith has a feedback API. You can add 👍/👎 buttons to each result that annotate the LangSmith trace:
```python
from langsmith import Client
ls_client = Client()
ls_client.create_feedback(run_id=run_id, key="user_feedback", score=1)
```
You immediately get a dataset of good/bad SQL generations for fine-tuning.

#### C. Query Result Caching (Redis)
The `REDIS_URL` is already in your `.env`. Add a cache decorator to `execute_query`:
```python
# If identical SQL was run in last 5 min, return cached result (sub-10ms)
```
Free tier Render instances benefit enormously from this — avoid re-querying Supabase for identical questions.

---

### 🟡 Medium (3–5 days each)

#### D. Multi-Database Support
The `database_registry` dict in `deps.py` already stores multiple DB connections. The upload router creates new tables in-session. Next step: let users **register their own PostgreSQL/MySQL/SQLite connections** by URL and query them directly.

```python
POST /databases   { "url": "postgresql://...", "name": "my_db" }
POST /query       { "query": "...", "database_id": "my_db" }
```

#### E. LangGraph Checkpointing → Session Persistence
LangGraph supports `MemorySaver` and `SqliteSaver` checkpointers. This turns your stateless pipeline into a **persistent conversation session** where you can resume exactly where you left off, even after a restart:
```python
from langgraph.checkpoint.sqlite import SqliteSaver
memory = SqliteSaver.from_conn_string("checkpoints.db")
compiled = graph.compile(checkpointer=memory)
# Now queries within the same thread_id share state across calls
```

#### F. Structured Output with `.with_structured_output()`
Replace JSON-parsing-from-LLM-string with Pydantic models:
```python
class SQLOutput(BaseModel):
    sql: str
    confidence: float
    explanation: str

sql_llm = llm.with_structured_output(SQLOutput)
```
This eliminates the `json.loads()` / regex fallback entirely — you get type-safe Pydantic objects directly from the LLM.

#### G. Agent Evaluation Suite (LangSmith Datasets)
LangSmith lets you create evaluation datasets from your query history and run automated accuracy tests:
```python
# Push golden test cases to LangSmith
ls_client.create_dataset("chinook_eval")
# Run your pipeline against them, score SQL accuracy
ls_client.evaluate(pipeline, data="chinook_eval", evaluators=[sql_correctness])
```

---

### 🔴 Advanced (1–2 weeks each)

#### H. LangGraph Human-in-the-Loop for Ambiguous Queries
Instead of answering ambiguous queries with "please clarify", you can **pause the graph** and wait for user input:
```python
# In pipeline.py — add interrupt_before=["sql_generation"]
compiled = graph.compile(checkpointer=memory, interrupt_before=["sql_generation"])

# Resume with user's clarification
final_state = compiled.invoke(
    Command(resume={"user_clarification": "last 30 days"}),
    config={"thread_id": session_id}
)
```
The frontend already has the conversation context banner — wire it to actual graph resume calls.

#### I. Schema-Aware Fine-Tuning Loop
1. Collect good query→SQL pairs via LangSmith feedback
2. Push to Hugging Face dataset
3. Fine-tune a small model (Qwen 7B) on your specific DB schema
4. Serve via vLLM (already in `docker-compose.yml`) as the primary provider
5. Result: ~zero API cost, much faster, schema-specific accuracy

#### J. Autonomous Data Analyst Agent
Build a new LangGraph node (`analysis_agent`) that:
- Runs multiple SQL queries autonomously (sub-queries it decomposes)
- Identifies trends, anomalies, correlations in results
- Produces a multi-paragraph narrative report
- Renders a full chart dashboard via the existing `ResultsChart` component

This is now possible because the `StateGraph` lets you add a new loop: `response_synthesis → analysis_agent → response_synthesis` with a conditional edge.

---

## Summary

The biggest unlock of 2.0 is **composability**. Every piece (LLM, retrieval, routing, state, observability) is now a standard LangChain/LangGraph primitive. That means:

- **Swap LLMs** by changing one env var
- **Add agents** by adding one node + one edge
- **Debug** via LangSmith instead of log-grepping
- **Scale** to any database size via RAG retrieval
- **Persist** conversations via LangGraph checkpointing

The 1.0 monolithic orchestrators would have required complete rewrites for any of the above.
