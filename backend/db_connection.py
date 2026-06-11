"""
Database Connection Module — ReasonSQL 2.0

Uses SQLAlchemy for all database operations (PostgreSQL only).

Architecture:
- Synchronous: SQLAlchemy `create_engine` + `sessionmaker` (psycopg2 driver)
- Asynchronous: SQLAlchemy `create_async_engine` + `AsyncSession` (asyncpg driver)
- Connection pooling: SQLAlchemy QueuePool (configurable via env)
- Schema introspection: `sqlalchemy.inspect` (no raw PRAGMA / information_schema)

Usage:
    from backend.db_connection import execute_query, get_tables, get_session

    # Simple query
    results = execute_query("SELECT COUNT(*) as count FROM \"Customer\"")

    # Session-based (for transactions)
    with get_session() as session:
        result = session.execute(text("SELECT 1"))
"""

import os
import logging
from typing import List, Dict, Any, Optional, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text, inspect as sa_inspect, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from configs import DATABASE_URL, DB_POOL_SIZE, DB_MAX_OVERFLOW

logger = logging.getLogger("reasonsql.db")


# =============================================================================
# ENGINE CREATION
# =============================================================================

def _build_sync_url(url: str) -> str:
    """Convert any postgres:// or postgresql+asyncpg:// URL to psycopg2 sync URL."""
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    url = url.replace("postgres://", "postgresql://")
    return url


def _build_async_url(url: str) -> str:
    """Convert URL to asyncpg-compatible URL."""
    url = url.replace("postgresql://", "postgresql+asyncpg://")
    url = url.replace("postgres://", "postgresql+asyncpg://")
    # Ensure it's not doubled
    url = url.replace("postgresql+asyncpg+asyncpg://", "postgresql+asyncpg://")
    return url


# Synchronous engine (used for schema introspection + sync helpers)
_sync_engine = create_engine(
    _build_sync_url(DATABASE_URL),
    poolclass=QueuePool,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_pre_ping=True,          # Verify connections before use
    pool_recycle=3600,           # Recycle connections every hour
    echo=False,
)

# Session factory (synchronous)
SessionLocal = sessionmaker(bind=_sync_engine, autocommit=False, autoflush=False)

# Asynchronous engine (used in the async FastAPI pipeline)
_async_engine = create_async_engine(
    _build_async_url(DATABASE_URL),
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=_async_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# =============================================================================
# SESSION CONTEXT MANAGERS
# =============================================================================

@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Synchronous session context manager.

    Usage:
        with get_session() as session:
            result = session.execute(text("SELECT 1")).fetchall()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def get_async_session() -> AsyncSession:
    """
    Async session dependency for FastAPI route injection.

    Usage (FastAPI):
        async def route(session: AsyncSession = Depends(get_async_session)):
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session


# =============================================================================
# QUERY EXECUTION
# =============================================================================

def execute_query(sql: str, params: Optional[dict] = None) -> List[Dict[str, Any]]:
    """
    Execute a read-only SQL query and return results as list of dicts.

    Args:
        sql: SQL query string (use :param_name for parameters)
        params: Optional dict of query parameters

    Returns:
        List of row dicts with column names as keys
    """
    with get_session() as session:
        result = session.execute(text(sql), params or {})
        if result.returns_rows:
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in result.fetchall()]
        return []


async def execute_query_async(sql: str, params: Optional[dict] = None) -> List[Dict[str, Any]]:
    """
    Execute a SQL query asynchronously via asyncpg.

    Args:
        sql: SQL query string (use :param_name for named parameters)
        params: Optional dict of query parameters

    Returns:
        List of row dicts with column names as keys
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(sql), params or {})
        if result.returns_rows:
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in result.fetchall()]
        return []


async def execute_write_async(sql: str, params: Optional[dict] = None) -> None:
    """
    Execute a write SQL statement asynchronously (CREATE TABLE for CSV uploads etc.).

    Args:
        sql: SQL statement
        params: Optional parameters dict
    """
    async with AsyncSessionLocal() as session:
        await session.execute(text(sql), params or {})
        await session.commit()


# =============================================================================
# SCHEMA INTROSPECTION (via SQLAlchemy Inspector)
# =============================================================================

def get_tables() -> List[str]:
    """
    Get all table names in the public schema using SQLAlchemy inspector.

    Returns:
        Sorted list of table names
    """
    inspector = sa_inspect(_sync_engine)
    return sorted(inspector.get_table_names(schema="public"))


def get_table_columns(table_name: str) -> List[Dict[str, Any]]:
    """
    Get column metadata for a table using SQLAlchemy inspector.

    Args:
        table_name: Table name (without schema prefix)

    Returns:
        List of column dicts: {name, type, nullable, primary_key}
    """
    inspector = sa_inspect(_sync_engine)
    columns = inspector.get_columns(table_name, schema="public")
    pk_constraint = inspector.get_pk_constraint(table_name, schema="public")
    pk_columns = set(pk_constraint.get("constrained_columns", []))

    return [
        {
            "name": col["name"],
            "type": str(col["type"]),
            "nullable": col.get("nullable", True),
            "primary_key": col["name"] in pk_columns,
        }
        for col in columns
    ]


def get_foreign_keys(table_name: str) -> List[Dict[str, Any]]:
    """
    Get foreign key relationships for a table.

    Returns:
        List of FK dicts: {constrained_columns, referred_table, referred_columns}
    """
    inspector = sa_inspect(_sync_engine)
    fks = inspector.get_foreign_keys(table_name, schema="public")
    return [
        {
            "constrained_columns": fk["constrained_columns"],
            "referred_table": fk["referred_table"],
            "referred_columns": fk["referred_columns"],
        }
        for fk in fks
    ]


def get_full_schema() -> Dict[str, Dict[str, Any]]:
    """
    Get complete schema: tables, columns, and foreign keys.

    Returns:
        Dict mapping table_name → {columns: [...], foreign_keys: [...]}
    """
    tables = get_tables()
    schema = {}
    for table in tables:
        schema[table] = {
            "columns": get_table_columns(table),
            "foreign_keys": get_foreign_keys(table),
        }
    return schema


def get_schema_as_text() -> Dict[str, str]:
    """
    Get schema as human-readable text strings for embedding/LLM context.

    Returns:
        Dict mapping table_name → formatted schema string
    """
    schema = get_full_schema()
    result = {}
    for table, info in schema.items():
        col_strs = []
        for col in info["columns"]:
            pk_marker = " PRIMARY KEY" if col["primary_key"] else ""
            null_marker = "" if col["nullable"] else " NOT NULL"
            col_strs.append(f'"{col["name"]}" {col["type"]}{pk_marker}{null_marker}')

        fk_strs = []
        for fk in info["foreign_keys"]:
            fk_strs.append(
                f'FK: "{fk["constrained_columns"][0]}" → '
                f'"{fk["referred_table"]}"("{fk["referred_columns"][0]}")'
            )

        parts = [f'Table "{table}":'] + col_strs + fk_strs
        result[table] = " | ".join(parts)

    return result


def get_row_count(table_name: str) -> int:
    """Get approximate row count for a table."""
    # Sanitize table name to prevent SQL injection
    if not all(c.isalnum() or c in ("_", "-") for c in table_name):
        raise ValueError(f"Invalid table name: {table_name!r}")
    results = execute_query(f'SELECT COUNT(*) as count FROM "{table_name}"')
    return results[0]["count"] if results else 0


# =============================================================================
# CONNECTION TESTING
# =============================================================================

def test_connection() -> Dict[str, Any]:
    """
    Test database connection and return status info.

    Returns:
        Dict with connected status, db_type, table_count, tables
    """
    try:
        tables = get_tables()

        # Detect well-known dataset
        dataset_name = None
        chinook_tables = {
            "Album", "Artist", "Customer", "Employee", "Genre",
            "Invoice", "InvoiceLine", "MediaType", "Playlist", "PlaylistTrack", "Track"
        }
        chinook_lower = {t.lower() for t in chinook_tables}
        actual_lower = {t.lower() for t in tables}
        if len(actual_lower & chinook_lower) >= 5:
            dataset_name = "Chinook"

        return {
            "connected": True,
            "db_type": "postgresql",
            "dataset_name": dataset_name,
            "table_count": len(tables),
            "tables": tables[:5],
        }
    except Exception as e:
        logger.error("Database connection test failed: %s", e)
        return {
            "connected": False,
            "db_type": "postgresql",
            "error": str(e),
        }


# =============================================================================
# CLEANUP
# =============================================================================

async def close_async_pool():
    """Dispose async connection pool (called on app shutdown)."""
    await _async_engine.dispose()
    logger.info("Async database connection pool closed.")


def close_sync_pool():
    """Dispose sync connection pool."""
    _sync_engine.dispose()
    logger.info("Sync database connection pool closed.")


# =============================================================================
# BACKWARDS COMPATIBILITY (used by API routers before migration)
# =============================================================================

def get_db_type() -> str:
    """Always returns 'postgresql' in v2.0."""
    return "postgresql"


def get_connection_context():
    """Backwards-compat alias for get_session()."""
    return get_session()
