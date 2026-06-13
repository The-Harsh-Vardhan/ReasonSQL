"""
Dynamic Database Registry — ReasonSQL 2.0

Manages per-database SQLAlchemy engines for multi-database support.
The default Supabase database is pre-registered at startup.
User-registered databases get their own engine pool.

Why a separate registry module:
    - Avoids circular imports between db_connection and api.deps
    - Provides a clean API for engine lifecycle management
    - Supports both sync (psycopg2) and async (asyncpg) engines per DB
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

logger = logging.getLogger("reasonsql.db_registry")

# Global per-database engine map: db_id → SQLAlchemy Engine
_engines: Dict[str, Any] = {}


# =============================================================================
# REGISTRATION
# =============================================================================

def register_postgres(db_id: str, connection_string: str) -> bool:
    """
    Create and test a SQLAlchemy engine for a PostgreSQL database.

    Args:
        db_id: Unique identifier (e.g. "chinook", "northwind")
        connection_string: SQLAlchemy-compatible PostgreSQL URL

    Returns:
        True if connection test passed, False otherwise
    """
    # Ensure sqlalchemy+psycopg2 driver prefix
    url = connection_string
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if "postgresql+asyncpg://" in url:
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)

    try:
        engine = create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 10})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        _engines[db_id] = engine
        logger.info("Registered PostgreSQL database '%s'", db_id)
        return True
    except Exception as exc:
        logger.warning("Failed to register '%s': %s", db_id, exc)
        return False


def register_sqlite(db_id: str, file_path: str) -> bool:
    """
    Create a SQLAlchemy engine for a SQLite database.

    Args:
        db_id: Unique identifier
        file_path: Path to the .db file

    Returns:
        True if file exists and engine is created
    """
    import os
    if not os.path.exists(file_path):
        logger.warning("SQLite file not found for '%s': %s", db_id, file_path)
        return False

    try:
        url = f"sqlite:///{file_path}"
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        _engines[db_id] = engine
        logger.info("Registered SQLite database '%s': %s", db_id, file_path)
        return True
    except Exception as exc:
        logger.warning("SQLite registration failed for '%s': %s", db_id, exc)
        return False


# =============================================================================
# QUERY EXECUTION
# =============================================================================

def execute_on_db(db_id: str, sql: str) -> list:
    """
    Run a SELECT query on a registered database and return rows as dicts.

    This is used for user-registered databases (not the default Supabase one,
    which uses the async engine from db_connection.py).

    Args:
        db_id: Registered database identifier
        sql: SQL query to run

    Returns:
        List of dicts (one per row)

    Raises:
        KeyError: If db_id not registered
        Exception: On SQL execution error
    """
    engine = _engines.get(db_id)
    if engine is None:
        raise KeyError(f"Database '{db_id}' not registered in dynamic registry")

    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = list(result.keys())
        return [dict(zip(columns, row)) for row in result.fetchall()]


def get_schema_for_db(db_id: str) -> Dict[str, str]:
    """
    Get schema info (table names + columns) for a registered database.

    Returns:
        Dict mapping table_name → formatted schema string
    """
    engine = _engines.get(db_id)
    if engine is None:
        raise KeyError(f"Database '{db_id}' not registered")

    from sqlalchemy import inspect
    inspector = inspect(engine)
    schemas: Dict[str, str] = {}

    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        col_lines = [f'  "{c["name"]}" {c["type"]}' for c in columns]
        schemas[table_name] = f'Table "{table_name}":\n' + "\n".join(col_lines)

    return schemas


def get_engine(db_id: str) -> Optional[Any]:
    """Get the SQLAlchemy engine for a database, or None if not registered."""
    return _engines.get(db_id)


def list_registered() -> list:
    """Return list of registered database IDs."""
    return list(_engines.keys())


def unregister(db_id: str) -> bool:
    """Remove a database from the registry and dispose its engine."""
    engine = _engines.pop(db_id, None)
    if engine:
        try:
            engine.dispose()
        except Exception:
            pass
        return True
    return False
