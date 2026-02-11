# 🗺️ ReasonSQL Roadmap

This document outlines improvements to take ReasonSQL from a "Demo" to a "Product".

## 1. 📊 Data Visualization (Frontend) ✅
**Goal**: Turn raw SQL results into insightful charts.
- [x] Install **Recharts** in `frontend-next`.
- [x] Add AI chart type selection (Line, Bar, Pie) based on data columns.
- [x] Render charts in results view.

## 2. ⚡ Performance & Scale (Backend) ✅
**Goal**: Handle concurrent users and large datasets.
- [x] **Async Database Driver**: Migrated to `asyncpg` for non-blocking I/O.
- [x] **Redis Caching**: Cache LLM responses (with in-memory fallback).
- [x] **Connection Pooling**: Async pool management in `db_connection.py`.

## 3. 🤖 AI Capabilities ✅
**Goal**: Smarter, more context-aware agents.
- [x] **Multi-turn Chat**: Conversation history with pronoun resolution.
- [x] **Vector Search (RAG)**: `sentence-transformers` embeddings for schema selection (15+ tables).
- [ ] **Data Explainer**: Agent that summarizes SQL results in natural language. (Future)

## 4. 🛠️ DevOps & Quality ✅
**Goal**: Automated reliability.
- [x] **CI/CD Pipeline**: GitHub Actions workflow (`.github/workflows/ci.yml`).
- [ ] **Integration Tests**: Test DB container in CI. (Future)
- [ ] **Pre-commit Hooks**: Linting enforcement. (Future)

## 5. 🔌 Connectivity (Partial) ✅
- [x] **Upload CSV**: `POST /upload` endpoint to ingest CSV files on-the-fly.
- [ ] **New Dialects**: MySQL, SQL Server, Snowflake support. (Future)
