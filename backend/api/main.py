"""
ReasonSQL 2.0 — FastAPI Application.

Architecture:
- LangChain + LangGraph multi-agent NL→SQL pipeline
- FAISS + BM25 + Cross-Encoder hybrid schema retrieval
- SQLAlchemy + PostgreSQL (pgvector) database layer
- LangSmith observability (opt-in)
- Redis/in-memory result caching
- Session persistence via LangGraph MemorySaver

Endpoints (via routers):
- POST /query                     — Execute natural language query
- POST /query/stream              — Execute via SSE streaming
- POST /feedback                  — Submit LangSmith feedback (👍/👎)
- POST /databases                 — Register a database connection
- GET  /databases                 — List registered databases
- GET  /databases/{id}/schema     — Get schema for a database
- GET  /health                    — Health check
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db_connection import test_connection, close_async_pool
from configs import DATABASE_URL

from .deps import database_registry, logger, get_orchestrator
from .schemas import DatabaseType
from .routers import query, databases, system, upload, stream, feedback


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

def _init_default_database():
    """Register the PostgreSQL database on startup."""
    logger.info("Connecting to PostgreSQL: %s...", DATABASE_URL[:40] + "..." if DATABASE_URL else "(not set)")
    conn_status = test_connection()

    database_registry["default"] = {
        "id": "default",
        "type": DatabaseType.POSTGRES,
        "connection_string": DATABASE_URL[:50] + "..." if DATABASE_URL else None,
        "connected": conn_status.get("connected", False),
        "table_count": conn_status.get("table_count", 0),
        "dataset_name": conn_status.get("dataset_name"),
    }

    if conn_status.get("connected"):
        logger.info(
            "✅ PostgreSQL connected: %d tables (dataset: %s)",
            conn_status.get("table_count", 0),
            conn_status.get("dataset_name", "unknown"),
        )
    else:
        logger.error(
            "❌ PostgreSQL connection FAILED: %s",
            conn_status.get("error", "Unknown error"),
        )


# =============================================================================
# APP LIFECYCLE
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: DB connection + LangGraph pipeline pre-warm
    _init_default_database()
    db_status = "connected" if database_registry.get("default", {}).get("connected") else "NOT connected"
    logger.info("ReasonSQL 2.0 API started. PostgreSQL: %s", db_status)

    # Pre-warm LangGraph pipeline (compiles graph, no model loading)
    get_orchestrator()

    yield

    # Shutdown: close async connection pool
    logger.info("ReasonSQL 2.0 API shutting down.")
    await close_async_pool()


# =============================================================================
# FASTAPI APP
# =============================================================================

app = FastAPI(
    title="ReasonSQL API",
    description=(
        "Multi-Agent NL→SQL System — LangChain + LangGraph + FAISS + SQLAlchemy\n"
        "LLM Providers: Gemini → Groq → Qwen (vLLM)\n"
        "Retrieval: Hybrid BM25 + FAISS + Cross-Encoder Reranking\n"
        "Features: SSE Streaming · Redis Cache · Session Persistence · LangSmith Feedback\n"
        "Observability: LangSmith (opt-in)"
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — configurable via environment
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

if allowed_origins == ["*"]:
    logger.warning(
        "CORS is set to allow ALL origins (*). "
        "Set ALLOWED_ORIGINS env var to restrict in production."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# INCLUDE ROUTERS
# =============================================================================

app.include_router(system.router)
app.include_router(query.router)
app.include_router(stream.router)
app.include_router(feedback.router)
app.include_router(databases.router)
app.include_router(upload.router)


# =============================================================================
# RUN DIRECTLY (for development)
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
