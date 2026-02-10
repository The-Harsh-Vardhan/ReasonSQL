"""
ReasonSQL FastAPI Application.

This module provides the REST API layer for the ReasonSQL NL→SQL system.
All business logic is delegated to the orchestrator; no SQL or LLM logic here.

Endpoints:
- POST /query - Execute natural language query
- POST /databases - Register a database connection
- GET /databases/{id}/schema - Get schema for a database
- GET /health - Health check
"""

import os
import sqlite3
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    QueryRequest, QueryResponse, 
    DatabaseRegisterRequest, DatabaseInfo, DatabaseListResponse,
    SchemaResponse, TableSchema,
    HealthResponse,
    ExecutionStatusAPI, AgentActionAPI, ReasoningTraceAPI,
    DatabaseType
)

# Import orchestrator (backend logic)
from backend.orchestrator import BatchOptimizedOrchestrator
from backend.models import ExecutionStatus
from backend.db_connection import get_db_type, test_connection
from configs import DATABASE_PATH, LLM_PROVIDER, DATABASE_URL


# ============================================================
# DATABASE REGISTRY (In-Memory for MVP)
# ============================================================

_database_registry: Dict[str, Dict[str, Any]] = {}

# Chinook database download URL
CHINOOK_DB_URL = "https://github.com/lerocha/chinook-database/raw/master/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite"


def _ensure_database_exists() -> bool:
    """Download the Chinook database if it doesn't exist (for SQLite only)."""
    # Skip download if using PostgreSQL
    if get_db_type() == "postgresql":
        print("[API] Using PostgreSQL database, skipping SQLite download")
        return True
    
    import urllib.request
    from pathlib import Path
    
    db_path = Path(DATABASE_PATH)
    
    # Create data directory if needed
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    if db_path.exists():
        print(f"[API] Database already exists at {db_path}")
        return True
    
    print(f"[API] Database not found. Downloading Chinook database...")
    try:
        urllib.request.urlretrieve(CHINOOK_DB_URL, db_path)
        print(f"[API] Database downloaded successfully ({db_path.stat().st_size} bytes)")
        return True
    except Exception as e:
        print(f"[API] ERROR: Failed to download database: {e}")
        return False


def _init_default_database():
    """Register default database on startup (PostgreSQL or SQLite)."""
    db_type = get_db_type()
    
    if db_type == "postgresql":
        # PostgreSQL (Supabase) mode
        print("[API] Initializing PostgreSQL database (Supabase)...")
        conn_status = test_connection()
        
        _database_registry["default"] = {
            "id": "default",
            "type": DatabaseType.POSTGRES,
            "connection_string": DATABASE_URL[:50] + "..." if DATABASE_URL else None,  # Masked
            "connected": conn_status.get("connected", False),
            "table_count": conn_status.get("table_count", 0)
        }
        
        if conn_status.get("connected"):
            print(f"[API] ✓ PostgreSQL connected with {conn_status.get('table_count', 0)} tables")
        else:
            print(f"[API] ✗ PostgreSQL connection failed: {conn_status.get('error', 'Unknown error')}")
    else:
        # SQLite mode
        db_exists = _ensure_database_exists()
        
        _database_registry["default"] = {
            "id": "default",
            "type": DatabaseType.SQLITE,
            "file_path": DATABASE_PATH,
            "connected": db_exists and os.path.exists(DATABASE_PATH)
        }


# ============================================================
# APP LIFECYCLE
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    _init_default_database()
    db_status = "connected" if _database_registry.get("default", {}).get("connected") else "NOT connected"
    print(f"[API] ReasonSQL API started. Default DB: {DATABASE_PATH} ({db_status})")
    yield
    # Shutdown
    print("[API] ReasonSQL API shutting down.")


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="ReasonSQL API",
    description="Multi-Agent NL→SQL System API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for frontend - configurable via environment
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _convert_execution_status(status: ExecutionStatus) -> ExecutionStatusAPI:
    """Convert backend ExecutionStatus to API enum."""
    mapping = {
        ExecutionStatus.SUCCESS: ExecutionStatusAPI.SUCCESS,
        ExecutionStatus.ERROR: ExecutionStatusAPI.ERROR,
        ExecutionStatus.BLOCKED: ExecutionStatusAPI.BLOCKED,
        ExecutionStatus.EMPTY: ExecutionStatusAPI.EMPTY,
    }
    return mapping.get(status, ExecutionStatusAPI.ERROR)


def _convert_reasoning_trace(trace) -> ReasoningTraceAPI:
    """Convert backend ReasoningTrace to API model."""
    actions = []
    for action in trace.actions:
        actions.append(AgentActionAPI(
            agent_name=action.agent_name,
            summary=action.output_summary,  # Backend uses output_summary
            detail=action.reasoning,        # Backend uses reasoning for details
            timestamp_ms=None               # Not captured in backend model
        ))
    
    return ReasoningTraceAPI(
        actions=actions,
        final_status=_convert_execution_status(trace.final_status),
        total_time_ms=trace.total_time_ms,
        correction_attempts=trace.correction_attempts
    )


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check API health and configuration status."""
    default_db = _database_registry.get("default", {})
    
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
        table_count=table_count,
        tables=tables,
    )


@app.get("/debug-db", tags=["System"])
async def debug_db():
    """Live database connection test (not cached)."""
    import time
    from urllib.parse import urlparse
    
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
        "dbname": parsed.path.lstrip('/'),
        "is_pooler": "pooler.supabase.com" in (parsed.hostname or ""),
        "url_has_sslmode": "sslmode" in database_url,
    }
    
    # Try connection
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        from urllib.parse import unquote
        
        info["psycopg2_version"] = psycopg2.__version__
        info["libpq_version"] = psycopg2.__libpq_version__
        
        t0 = time.time()
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 6543,
            user=parsed.username,
            password=unquote(parsed.password) if parsed.password else None,
            dbname=parsed.path.lstrip('/') or 'postgres',
            sslmode='require',
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


@app.post("/query", response_model=QueryResponse, tags=["Query"])
async def execute_query(request: QueryRequest):
    """
    Execute a natural language query against the database.
    
    The query is processed by the 12-agent pipeline:
    1. IntentAnalyzer → 2. ClarificationAgent → 3. SchemaExplorer → ...
    """
    # Validate database exists
    db_info = _database_registry.get(request.database_id)
    if not db_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database '{request.database_id}' not registered"
        )
    
    # If registry says disconnected, do a live re-check (startup may have failed)
    if not db_info.get("connected"):
        live_status = test_connection()
        if live_status.get("connected"):
            # Update registry so future requests skip re-check
            db_info["connected"] = True
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Database '{request.database_id}' is not connected"
            )
    
    try:
        # Create orchestrator and run query
        orchestrator = BatchOptimizedOrchestrator(verbose=False)
        response = orchestrator.process_query(request.query)
        
        # Convert to API response
        return QueryResponse(
            success=response.reasoning_trace.final_status == ExecutionStatus.SUCCESS,
            answer=response.answer,
            sql_used=response.sql_used,
            data_preview=response.data_preview,
            row_count=response.row_count,
            is_meta_query=response.is_meta_query,
            reasoning_trace=_convert_reasoning_trace(response.reasoning_trace),
            warnings=response.warnings
        )
    
    except Exception as e:
        # Return error response instead of raising
        return QueryResponse(
            success=False,
            answer=f"Query failed: {str(e)}",
            error=str(e),
            reasoning_trace=ReasoningTraceAPI(
                final_status=ExecutionStatusAPI.ERROR
            )
        )


@app.post("/databases", response_model=DatabaseInfo, tags=["Databases"])
async def register_database(request: DatabaseRegisterRequest):
    """
    Register a new database connection.
    
    For SQLite: Provide file_path
    For Postgres: Provide connection_string
    """
    # Validate request
    if request.type == DatabaseType.SQLITE and not request.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_path required for SQLite databases"
        )
    
    if request.type == DatabaseType.POSTGRES and not request.connection_string:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="connection_string required for Postgres databases"
        )
    
    # Check connection
    connected = False
    if request.type == DatabaseType.SQLITE:
        connected = os.path.exists(request.file_path)
    elif request.type == DatabaseType.POSTGRES:
        # TODO: Implement Postgres connection check
        connected = False  # Placeholder
    
    # Register
    _database_registry[request.id] = {
        "id": request.id,
        "type": request.type,
        "file_path": request.file_path,
        "connection_string": request.connection_string,
        "connected": connected
    }
    
    return DatabaseInfo(
        id=request.id,
        type=request.type,
        connected=connected
    )


@app.get("/databases", response_model=DatabaseListResponse, tags=["Databases"])
async def list_databases():
    """List all registered databases."""
    databases = [
        DatabaseInfo(
            id=db["id"],
            type=db["type"],
            connected=db.get("connected", False)
        )
        for db in _database_registry.values()
    ]
    return DatabaseListResponse(databases=databases)


@app.get("/databases/{database_id}/schema", response_model=SchemaResponse, tags=["Databases"])
async def get_database_schema(database_id: str):
    """
    Get schema information for a registered database.
    
    Returns all tables with their columns.
    """
    db_info = _database_registry.get(database_id)
    if not db_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database '{database_id}' not registered"
        )
    
    if db_info["type"] != DatabaseType.SQLITE:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Schema introspection only supported for SQLite currently"
        )
    
    file_path = db_info.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database file not found: {file_path}"
        )
    
    try:
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        table_names = [row[0] for row in cursor.fetchall()]
        
        tables = []
        for table_name in table_names:
            # Get columns
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [
                {"name": row[1], "type": row[2]}
                for row in cursor.fetchall()
            ]
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            
            tables.append(TableSchema(
                name=table_name,
                columns=columns,
                row_count=row_count
            ))
        
        conn.close()
        
        return SchemaResponse(
            database_id=database_id,
            tables=tables
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read schema: {str(e)}"
        )


# ============================================================
# RUN DIRECTLY (for development)
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
