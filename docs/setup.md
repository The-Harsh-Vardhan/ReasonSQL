---
title: Setup
---

# Setup

## Docker (PostgreSQL + FastAPI backend)

```bash
git clone https://github.com/The-Harsh-Vardhan/ReasonSQL.git
cd ReasonSQL
cp .env.example .env        # add GEMINI_API_KEY (required), optionally LANGCHAIN_API_KEY
docker-compose up -d
curl http://localhost:8000/health

cd frontend-next
npm install && npm run dev  # http://localhost:3000
```

## Local dev without Docker

```bash
python -m pip install -r requirements.txt   # inside a virtual environment
docker-compose up -d postgres               # or any PostgreSQL
# DATABASE_URL=postgresql://reasonsql:reasonsql@localhost:5432/reasonsql  (in .env)
uvicorn backend.api.main:app --port 8000 --reload
```

## CLI

Install the runtime dependencies first, then the package:

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
```

| Command | What it does |
|---------|--------------|
| `reasonsql ask "question"` | Runs one question through the same LangGraph path as `POST /query` and prints the answer, SQL, status, row count, retries and time. |
| `reasonsql ask --file queries.txt --json` | One question per line; `--json` prints the full API-shaped response. Exits non-zero if any question fails. |
| `reasonsql serve [--host 127.0.0.1] [--port 8000] [--reload]` | Starts the FastAPI backend. |
| `reasonsql eval [options]` | Runs `scripts/evaluate.py` against a running API (`--api-url`, default `http://localhost:8000`). Options: `--categories`, `--no-langsmith`, `--timeout`, `--baseline` (also run each case as a single prompt on the same LLM and DB), `--report PATH` (Markdown report). |

`python -m backend.main "question"` still works and is treated as `ask`.

## LangSmith tracing

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=<your key>
LANGCHAIN_PROJECT=ReasonSQL-2.0
```

## Optional: self-hosted Qwen via vLLM

Requires an NVIDIA GPU. Uncomment the `vllm` service in `docker-compose.yml`, then set in `.env`:

```env
ENABLE_VLLM_FALLBACK=true
VLLM_BASE_URL=http://vllm:8000/v1
VLLM_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct
```
