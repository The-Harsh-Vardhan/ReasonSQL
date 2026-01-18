# ReasonSQL - Multi-Agent NL→SQL System

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CrewAI](https://img.shields.io/badge/Framework-CrewAI-green.svg)](https://github.com/joaomdmoura/crewai)
[![LLM: Gemini/Groq](https://img.shields.io/badge/LLM-Gemini%20%7C%20Groq-purple.svg)](https://ai.google.dev/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Deployed-FF4B4B.svg)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF.svg)](https://github.com/features/actions)

> **Why simple "prompt → SQL" fails, and how 12 specialized agents fix it.**

---

## ⚡ TL;DR (30-Second Summary)

| ❌ NAIVE APPROACH | ✅ OUR APPROACH |
|-------------------|-----------------|
| Schema + Question → LLM → SQL | 12 Specialized Agents in Pipeline |
| Hallucinates table names | Explores schema BEFORE generating |
| Assumes meaning of recent, best | Asks clarifying questions |
| Returns errors, not answers | Self-corrects on failures |
| No safety (SELECT * on 1M rows) | Safety-validated, enforces LIMIT |
| Black box | Full reasoning trace visible |

**Result:** ~50% accuracy → 85%+ on complex queries

---

## 🚀 Quick Start

### 💻 Local Setup (Modern Stack)

```bash
# 1. Backend Setup
pip install -r requirements.txt
cp .env.example .env  # Add GEMINI_API_KEY or GROQ_API_KEY

# 2. Start FastAPI Backend
python -m uvicorn backend.api.main:app --port 8000

# 3. Start Next.js Frontend (in new terminal)
cd frontend-next
npm install && npm run dev
# Visit http://localhost:3000
```

### 🎯 Legacy Streamlit UI (Optional)

```bash
cd frontend/streamlit_legacy
python -m streamlit run streamlit_app.py
# Visit http://localhost:8501
```

### 🐳 Docker Setup (Coming Soon)

```bash
docker-compose up
# Visit http://localhost:3000
```

---

## 📁 Project Structure

```
ReasonSQL/
├── backend/                # Core Logic
│   ├── api/                # FastAPI endpoints
│   ├── agents/             # 12 agent definitions
│   ├── orchestrator/       # Orchestration logic
│   ├── adapters/           # Database adapters (SQLite, Postgres)
│   ├── tools/              # Database tools
│   └── models/             # Pydantic models
├── frontend-next/          # Next.js Frontend (PRIMARY)
│   └── app/page.tsx        # Main query interface
├── frontend/               # Legacy
│   └── streamlit_legacy/   # Deprecated Streamlit UI
├── data/
│   └── chinook.db          # Sample database
├── configs/                # Configuration
└── scripts/                # Setup & Utilities
```

---

## 📖 Documentation

- **[Agent Pipeline](AGENT_PIPELINE.md)** - Complete visualization of 12-agent workflow
- **[Deployment Guide](DEPLOYMENT.md)** - Deploy to Streamlit Cloud, Docker, or local
- [Batch Orchestrator Design](docs/BATCH_ORCHESTRATOR_DESIGN.md) - Technical architecture
- [Quota Optimization](docs/QUOTA_OPTIMIZATION.md) - Rate limit handling
- [JSON Parsing Fix](docs/JSON_PARSING_FIX.md) - LLM response parsing
- [Gemini Key Rotation](key_rotation_summary.py) - Multi-key management
- [Contributing Guide](CONTRIBUTING.md) - How to contribute

---

## 🚀 Deployment

This project is ready to deploy on:

- **Streamlit Cloud** - Free hosting for public repos ([Guide](DEPLOYMENT.md#streamlit-cloud-deployment))
- **Docker** - Containerized deployment ([Guide](DEPLOYMENT.md#docker-deployment))
- **Local** - Run on your machine ([Guide](DEPLOYMENT.md#local-deployment))

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

---

## 📜 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

**Built with ReasonSQL** | 12 Agents • 4 LLM Calls • Full Transparency
