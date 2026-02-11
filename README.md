# ReasonSQL - Multi-Agent NL→SQL System

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com)
[![LLM: Gemini](https://img.shields.io/badge/LLM-Gemini-purple.svg)](https://ai.google.dev/)
[![Live Demo](https://img.shields.io/badge/Live-reason--sql.vercel.app-06b6d4.svg)](https://reason-sql.vercel.app)
[![Render](https://img.shields.io/badge/API-Render-46E3B7.svg)](https://render.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Why simple "prompt → SQL" fails, and how 12 specialized agents fix it.**

🔗 **[Live Demo →](https://reason-sql.vercel.app)**

---

## ⚡ TL;DR

| ❌ Naive Approach | ✅ ReasonSQL |
|-------------------|-------------|
| Schema + Question → LLM → SQL | 12 Specialized Agents in Pipeline |
| Hallucinates table names | Explores schema BEFORE generating |
| Assumes meaning of "recent", "best" | Asks clarifying questions |
| Returns errors, not answers | Self-corrects on failures |
| No safety (SELECT * on 1M rows) | Safety-validated, enforces LIMIT |
| Black box | Full reasoning trace visible |

**Result:** ~50% accuracy → **85%+ on complex queries**

---

## ✨ Features

### Core Intelligence
- **12 Specialized AI Agents** — Intent analysis, schema exploration, SQL generation, safety validation, self-correction, response synthesis
- **Batch-Optimized Pipeline** — Only 4-6 LLM calls per query (vs. 12+ with naive approaches)
- **Self-Correction** — Automatically retries and fixes errors
- **Safety Validation** — Blocks DROP/DELETE/UPDATE, enforces SELECT-only with LIMIT

### Frontend (Next.js)
- **SQL Syntax Highlighting** — Color-coded keywords, strings, numbers, functions
- **Copy Buttons** — One-click copy for answers and generated SQL
- **CSV Export** — Download query results as CSV
- **Shareable Links** — Share queries via URL (`?q=your+query`)
- **Keyboard Shortcuts** — `Ctrl+Enter` to submit queries
- **Saved Queries / Bookmarks** — Star queries for quick re-use
- **Query Suggestions** — Preset query pills for quick exploration
- **Live Execution Timer** — Real-time countdown while processing
- **Toast Notifications** — Slide-in feedback for all actions
- **Schema Explorer** — Browse database tables and columns in the sidebar
- **System Status** — Live connection indicators for API and database
- **Agent Pipeline Visualization** — See which agents ran in sequence
- **Architecture Section** — Expandable "How it works" with agent descriptions
- **Responsive Design** — Collapsible sidebar with hamburger menu on mobile
- **Analytics Dashboard** — Query stats, success rate chart, top queries (`/dashboard`)
- **PWA Support** — Installable on mobile/desktop
- **OpenGraph Social Preview** — Branded card when sharing on LinkedIn/Twitter

### Backend (FastAPI)
- **PostgreSQL + SQLite** — Supabase PostgreSQL in production, SQLite for local dev
- **RESTful API** — `/query`, `/health`, `/databases/{id}/schema` endpoints
- **Live Health Check** — Real-time database connection monitoring
- **Quota Management** — Gemini API key rotation and rate limiting

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    Next.js Frontend                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │  Query    │ │  Schema  │ │ Dashboard│ │  System  │      │
│  │  Input    │ │ Explorer │ │ /dashboard│ │  Status  │      │
│  └────┬─────┘ └──────────┘ └──────────┘ └──────────┘      │
│       │                                                     │
└───────┼─────────────────────────────────────────────────────┘
        │  POST /query
        ▼
┌────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                          │
│                                                            │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌────────────┐  │
│  │ Intent  │→ │ Schema  │→ │   SQL    │→ │  Safety    │  │
│  │Analyzer │  │Explorer │  │Generator │  │ Validator  │  │
│  └─────────┘  └─────────┘  └──────────┘  └─────┬──────┘  │
│                                                  │         │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌─────▼──────┐  │
│  │Response │← │  Self   │← │  Query   │← │    FK      │  │
│  │ Synth   │  │Corrector│  │ Executor │  │ Validator  │  │
│  └─────────┘  └─────────┘  └──────────┘  └────────────┘  │
│                                                            │
└─────────────────────────┬──────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  PostgreSQL (Supabase) │
              │  or SQLite (local)     │
              └───────────────────────┘
```

---

## 🚀 Quick Start

### Local Development

```bash
# 1. Clone & install backend
git clone https://github.com/The-Harsh-Vardhan/ReasonSQL.git
cd ReasonSQL
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Add your GEMINI_API_KEY to .env

# 3. Start backend
python -m uvicorn backend.api.main:app --port 8000

# 4. Start frontend (new terminal)
cd frontend-next
npm install && npm run dev
# Visit http://localhost:3000
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | ✅ | Google Gemini API key |
| `DATABASE_URL` | For PostgreSQL | Supabase connection string |
| `DATABASE_PATH` | For SQLite | Path to `.db` file (default: `data/chinook.db`) |
| `NEXT_PUBLIC_API_URL` | For deploy | Backend API URL |

---

## 📁 Project Structure

```bash
ReasonSQL/
├── backend/                    # Core modular API (FastAPI)
│   ├── api/                    # Routers, deps, schemas
│   ├── agents/                 # 12 specialized agent definitions
│   ├── orchestrator/           # Multi-agent logic
│   └── adapters/               # DB Adapters (SQLite/Postgres)
├── frontend-next/              # Next.js 16 Dashboard
├── tests/                      # API and Integration tests
├── data/                       # Sample datasets (Chinook)
├── configs/                    # Environment & provider configs
├── docs/                       # Hosting & usage guides
└── Extras/                     # Legacy code and documentation
```

---

## 📖 How to Use

1. **Ask a Question**: Type any natural language question about the database (e.g., *"Who are the top 10 customers by spend?"*).
2. **Observe the Reasoning**: Click the **"Reasoning"** tab to see how the 12 agents analyzed your intent, explored the schema, and validated the SQL.
3. **Review Results**: View the generated SQL and the live data preview in the **"Result"** tab.
4. **Export & Share**: Download results as CSV or share the specific query URL with your team.

---

## 🚀 Deployment

| Platform | Component | Free Tier | Status |
|----------|-----------|-----------|--------|
| **[Vercel](https://vercel.com)** | Next.js Frontend | ✅ Free | [Live →](https://reason-sql.vercel.app) |
| **[Render](https://render.com)** | FastAPI Backend | ✅ 750 hrs/mo | [Active](https://reasonsql-api-rl3g.onrender.com/health) |
| **Supabase** | PostgreSQL DB | ✅ 500MB | Connected |

See [HOSTING.md](docs/HOSTING.md) for detailed instructions.

---

## 📖 Documentation

- [Hosting Guide](docs/HOSTING.md) — Step-by-step Supabase, Render, Vercel setup
- [Agent Pipeline](Extras/AGENT_PIPELINE.md) — Complete 12-agent workflow (Legacy)
- [Contributing Guide](CONTRIBUTING.md) — How to contribute

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 16, React, Tailwind CSS |
| **Backend** | Python, FastAPI, Pydantic |
| **LLM** | Google Gemini (with key rotation) |
| **Database** | PostgreSQL (Supabase) / SQLite |
| **Hosting** | Vercel (frontend) + Render (backend) |
| **Analytics** | Vercel Analytics |

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

<p align="center">
  <strong>Built with ReasonSQL</strong><br>
  12 Agents • 4 LLM Calls • Full Transparency<br><br>
  <a href="https://reason-sql.vercel.app">Live Demo</a> •
  <a href="https://github.com/The-Harsh-Vardhan/ReasonSQL">Source Code</a>
</p>
