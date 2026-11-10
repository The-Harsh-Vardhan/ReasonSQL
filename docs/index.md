---
title: ReasonSQL
---

# ReasonSQL 2.0

Multi-agent NL to SQL: a LangGraph `StateGraph` that retrieves the relevant tables with hybrid search (BM25 + FAISS + Reciprocal Rank Fusion + cross-encoder rerank), analyzes and clarifies the question, generates SQL, validates it deterministically, executes it on PostgreSQL, and self-corrects on errors. Served by FastAPI to a Next.js dashboard.

- Live demo: <https://reason-sql.vercel.app>
- Source: <https://github.com/The-Harsh-Vardhan/ReasonSQL>

## Pages

| Page | What is in it |
|------|---------------|
| [Architecture](architecture) | The LangGraph pipeline traced from the code, node-by-node notes, retrieval pipeline, deployment topology |
| [Setup](setup) | Docker, local dev, the `reasonsql` CLI (`ask`, `serve`, `eval`), observability and optional vLLM |
| [Hosting guide](HOSTING) | Supabase + Render + Vercel deployment |
| [Roadmap](ROADMAP) | Done and planned work |
| [v1 pipeline design](AGENT_PIPELINE) | The original 12-agent orchestrator design (superseded by the LangGraph pipeline) |

The reported accuracy figure (~50% to 85%+ on complex multi-join queries) predates the current evaluation harness. A reproducible baseline-vs-pipeline report is tracked in [issue 6](https://github.com/The-Harsh-Vardhan/ReasonSQL/issues/6).
