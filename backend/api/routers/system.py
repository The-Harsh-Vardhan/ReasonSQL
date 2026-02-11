"""
System router — health check and debug endpoints.

Endpoints:
- GET /health    — Health check (always available)
- GET /debug-db  — Live DB debug (gated behind ENABLE_DEBUG_ENDPOINTS)
"""

import os
import time
from urllib.parse import urlparse, unquote

from fastapi import APIRouter, HTTPException, status

from backend.db_connection import test_connection
from configs import LLM_PROVIDER

from ..schemas import HealthResponse
from ..deps import database_registry, logger, ENABLE_DEBUG_ENDPOINTS


router = APIRouter(tags=["System"])


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API health and configuration status."""
    # Get live database info
    db_info = test_connection()
    db_connected = db_info.get("connected", False)
    db_type = db_info.get("db_type", "unknown")
    table_count = db_info.get("table_count", 0)
    tables = db_info.get("tables", [])

    # Build db_name based on type
    if db_type == "postgresql":
        db_name = "Supabase PostgreSQL"
    else:
        db_name = db_info.get("connection_info", "SQLite (local)")

    return HealthResponse(
        status="healthy",
        version="1.0.0",
        llm_provider=LLM_PROVIDER,
        database_connected=db_connected,
        db_type=db_type,
        db_name=db_name,
        dataset_name=db_info.get("dataset_name"),
        table_count=table_count,
        tables=tables,
    )


@router.get("/debug-db")
async def debug_db():
    """
    Live database connection test (not cached).

    This endpoint is gated behind the ENABLE_DEBUG_ENDPOINTS environment
    variable. Returns 404 when disabled (default in production).
    """
    if not ENABLE_DEBUG_ENDPOINTS:
        logger.debug("Debug endpoint hit but ENABLE_DEBUG_ENDPOINTS is false")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debug endpoints are disabled",
        )

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return {"error": "DATABASE_URL not set"}

    parsed = urlparse(database_url)
    masked_pw = (parsed.password or "")[:3] + "***" if parsed.password else "NONE"
    info = {
        "user": parsed.username,
        "host": parsed.hostname,
        "port": parsed.port,
        "password_preview": masked_pw,
        "password_length": len(parsed.password) if parsed.password else 0,
        "dbname": parsed.path.lstrip("/"),
        "is_pooler": "pooler.supabase.com" in (parsed.hostname or ""),
        "url_has_sslmode": "sslmode" in database_url,
    }

    # Try connection
    try:
        import psycopg2

        info["psycopg2_version"] = psycopg2.__version__
        info["libpq_version"] = psycopg2.__libpq_version__

        t0 = time.time()
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 6543,
            user=parsed.username,
            password=unquote(parsed.password) if parsed.password else None,
            dbname=parsed.path.lstrip("/") or "postgres",
            sslmode="require",
            connect_timeout=10,
        )
        elapsed = round(time.time() - t0, 2)
        cur = conn.cursor()
        cur.execute("SELECT current_database(), current_user, version()")
        row = cur.fetchone()
        conn.close()
        info["connected"] = True
        info["elapsed_s"] = elapsed
        info["db_name"] = row[0]
        info["db_user"] = row[1]
        info["db_version"] = row[2][:60]
    except Exception as e:
        info["connected"] = False
        info["error"] = str(e)

    return info
