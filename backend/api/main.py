"""
ReasonSQL FastAPI Application.

This module provides the REST API layer for the ReasonSQL NL→SQL system.
All business logic is delegated to the orchestrator; no SQL or LLM logic here.

Endpoints (via routers):
- POST /query                     — Execute natural language query
- POST /databases                 — Register a database connection
- GET  /databases                 — List registered databases
- GET  /databases/{id}/schema     — Get schema for a database
- GET  /health                    — Health check
- GET  /debug-db                  — Debug database connection (gated)
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db_connection import get_db_type, test_connection
from configs import DATABASE_PATH, DATABASE_URL

from .deps import database_registry, logger, get_orchestrator
from .schemas import DatabaseType
from .routers import query, databases, system


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

CHINOOK_DB_URL = "https://github.com/lerocha/chinook-database/raw/master/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite"


def _ensure_database_exists() -> bool:
    """Download the Chinook database if it doesn't exist (for SQLite only)."""
    if get_db_type() == "postgresql":
        logger.info("Using PostgreSQL database, skipping SQLite download")
        return True

    import urllib.request
    from pathlib import Path

    db_path = Path(DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        logger.info("Database already exists at %s", db_path)
        return True

    logger.info("Database not found. Downloading Chinook database...")
    try:
        urllib.request.urlretrieve(CHINOOK_DB_URL, db_path)
        logger.info("Database downloaded successfully (%d bytes)", db_path.stat().st_size)
        return True
    except Exception as e:
        logger.error("Failed to download database: %s", e)
        return False


def _init_default_database():
    """Register default database on startup (PostgreSQL or SQLite)."""
    db_type = get_db_type()

    if db_type == "postgresql":
        logger.info("Initializing PostgreSQL database (Supabase)...")
        conn_status = test_connection()

        database_registry["default"] = {
            "id": "default",
            "type": DatabaseType.POSTGRES,
            "connection_string": DATABASE_URL[:50] + "..." if DATABASE_URL else None,
            "connected": conn_status.get("connected", False),
            "table_count": conn_status.get("table_count", 0),
        }

        if conn_status.get("connected"):
            logger.info(
                "PostgreSQL connected with %d tables",
                conn_status.get("table_count", 0),
            )
        else:
            logger.error(
                "PostgreSQL connection failed: %s",
                conn_status.get("error", "Unknown error"),
            )
    else:
        db_exists = _ensure_database_exists()
        database_registry["default"] = {
            "id": "default",
            "type": DatabaseType.SQLITE,
            "file_path": DATABASE_PATH,
            "connected": db_exists and os.path.exists(DATABASE_PATH),
        }


# =============================================================================
# APP LIFECYCLE
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    _init_default_database()
    db_status = "connected" if database_registry.get("default", {}).get("connected") else "NOT connected"
    logger.info("ReasonSQL API started. Default DB: %s (%s)", DATABASE_PATH, db_status)

    # Pre-warm the singleton orchestrator
    get_orchestrator()

    yield

    # Shutdown
    logger.info("ReasonSQL API shutting down.")


# =============================================================================
# FASTAPI APP
# =============================================================================

app = FastAPI(
    title="ReasonSQL API",
    description="Multi-Agent NL→SQL System API",
    version="1.0.0",
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
app.include_router(databases.router)


# =============================================================================
# RUN DIRECTLY (for development)
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
