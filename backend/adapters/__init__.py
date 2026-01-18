"""
Adapters module for ReasonSQL.

Contains:
1. Naive SQL generator (for comparison demos)
2. Database adapters (SQLite, Postgres)
"""

# Naive comparison (demonstration only)
from .naive_sql_generator import (
    run_naive_query,
    generate_naive_sql,
    execute_naive_sql,
    get_raw_schema,
    is_sql_safe,
    NaiveResult,
    NaiveStatus,
    format_naive_result_for_display,
    NAIVE_DISCLAIMER,
    NAIVE_COMPARISON_LABEL
)

# Database adapters
from .database_adapter import (
    DatabaseAdapter,
    DatabaseType,
    ConnectionConfig,
    DatabaseError,
    ConnectionError,
    QueryExecutionError
)
from .sqlite_adapter import SQLiteAdapter, create_sqlite_adapter
from .postgres_adapter import PostgresAdapter, create_postgres_adapter
from .factory import create_adapter, register_adapter, get_adapter, list_adapters

__all__ = [
    # Naive comparison
    "run_naive_query",
    "generate_naive_sql",
    "execute_naive_sql",
    "get_raw_schema",
    "is_sql_safe",
    "NaiveResult",
    "NaiveStatus",
    "format_naive_result_for_display",
    "NAIVE_DISCLAIMER",
    "NAIVE_COMPARISON_LABEL",
    # Database adapters
    "DatabaseAdapter",
    "DatabaseType",
    "ConnectionConfig",
    "DatabaseError",
    "ConnectionError",
    "QueryExecutionError",
    "SQLiteAdapter",
    "PostgresAdapter",
    "create_sqlite_adapter",
    "create_postgres_adapter",
    "create_adapter",
    "register_adapter",
    "get_adapter",
    "list_adapters",
]
