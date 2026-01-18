"""
Database Adapter Layer for ReasonSQL.

This module provides a unified interface for database operations,
allowing the system to work with different database backends
(SQLite for local development, Postgres for production).

Design Principles:
- Agents NEVER access databases directly
- All database operations go through adapters
- Adapters handle connection pooling, error translation, schema introspection
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class DatabaseType(str, Enum):
    """Supported database types."""
    SQLITE = "sqlite"
    POSTGRES = "postgres"


@dataclass
class ConnectionConfig:
    """Database connection configuration."""
    db_type: DatabaseType
    # SQLite
    file_path: Optional[str] = None
    # Postgres
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    connection_string: Optional[str] = None


class DatabaseError(Exception):
    """Base exception for database operations."""
    pass


class ConnectionError(DatabaseError):
    """Failed to connect to database."""
    pass


class QueryExecutionError(DatabaseError):
    """Query execution failed."""
    pass


class DatabaseAdapter(ABC):
    """
    Abstract base class for database adapters.
    
    All database operations in the system MUST go through this interface.
    Agents and orchestrators should never use sqlite3/psycopg2 directly.
    """
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self._connected = False
    
    @abstractmethod
    def connect(self) -> None:
        """Establish database connection."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close database connection."""
        pass
    
    @abstractmethod
    def execute(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        Execute a SQL query and return results.
        
        Args:
            sql: SQL query string
            params: Optional query parameters (for parameterized queries)
        
        Returns:
            List of dictionaries, one per row, with column names as keys
        """
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """
        Get database schema information.
        
        Returns:
            Dictionary with:
            - tables: List of table info (name, columns, row_count)
            - relationships: List of foreign key relationships
        """
        pass
    
    @abstractmethod
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """
        Get detailed info for a specific table.
        
        Returns:
            Dictionary with columns, primary keys, foreign keys, sample data
        """
        pass
    
    @abstractmethod
    def get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get sample rows from a table.
        
        Args:
            table_name: Name of the table
            limit: Maximum number of rows to return
        
        Returns:
            List of sample rows as dictionaries
        """
        pass
    
    @property
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._connected
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
