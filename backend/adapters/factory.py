"""
Database Adapter Factory.

Creates the appropriate database adapter based on configuration.
Provides a single entry point for adapter creation.
"""

from typing import Optional

from .database_adapter import DatabaseAdapter, DatabaseType, ConnectionConfig
from .sqlite_adapter import SQLiteAdapter, create_sqlite_adapter
from .postgres_adapter import PostgresAdapter, create_postgres_adapter


def create_adapter(
    db_type: DatabaseType,
    file_path: Optional[str] = None,
    connection_string: Optional[str] = None,
    **kwargs
) -> DatabaseAdapter:
    """
    Create a database adapter of the specified type.
    
    Args:
        db_type: Type of database (sqlite or postgres)
        file_path: Path to SQLite file (required for sqlite)
        connection_string: Connection string (required for postgres)
        **kwargs: Additional connection params for postgres
    
    Returns:
        Connected DatabaseAdapter instance
    
    Raises:
        ValueError: If required params are missing
    
    Examples:
        # SQLite
        adapter = create_adapter(DatabaseType.SQLITE, file_path="./data/chinook.db")
        
        # Postgres
        adapter = create_adapter(
            DatabaseType.POSTGRES, 
            connection_string="postgresql://user:pass@host/db"
        )
    """
    if db_type == DatabaseType.SQLITE:
        if not file_path:
            raise ValueError("file_path is required for SQLite adapter")
        return create_sqlite_adapter(file_path)
    
    elif db_type == DatabaseType.POSTGRES:
        if not connection_string and not kwargs.get("host"):
            raise ValueError("connection_string or host is required for Postgres adapter")
        return create_postgres_adapter(connection_string) if connection_string else PostgresAdapter(**kwargs)
    
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


# Global adapter registry (for multi-database support)
_adapter_registry: dict[str, DatabaseAdapter] = {}


def register_adapter(name: str, adapter: DatabaseAdapter) -> None:
    """Register an adapter by name."""
    _adapter_registry[name] = adapter


def get_adapter(name: str) -> Optional[DatabaseAdapter]:
    """Get a registered adapter by name."""
    return _adapter_registry.get(name)


def list_adapters() -> list[str]:
    """List all registered adapter names."""
    return list(_adapter_registry.keys())
