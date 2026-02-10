"""
SQLite Database Adapter.

Implements DatabaseAdapter interface for SQLite databases.
Used for local development and offline demos.
"""

import sqlite3
from typing import List, Dict, Any, Optional
from pathlib import Path

from .database_adapter import (
    DatabaseAdapter, 
    ConnectionConfig, 
    DatabaseType,
    DatabaseError,
    ConnectionError,
    QueryExecutionError
)


class SQLiteAdapter(DatabaseAdapter):
    """
    SQLite implementation of DatabaseAdapter.
    
    Features:
    - File-based database (no server required)
    - Row factory for dict-like results
    - Full schema introspection
    - Foreign key detection
    """
    
    def __init__(self, file_path: str):
        """
        Initialize SQLite adapter.
        
        Args:
            file_path: Path to SQLite database file
        """
        config = ConnectionConfig(
            db_type=DatabaseType.SQLITE,
            file_path=file_path
        )
        super().__init__(config)
        self._connection: Optional[sqlite3.Connection] = None
    
    def connect(self) -> None:
        """Establish connection to SQLite database."""
        file_path = self.config.file_path
        
        if not file_path:
            raise ConnectionError("No file path specified for SQLite database")
        
        if not Path(file_path).exists():
            raise ConnectionError(f"Database file not found: {file_path}")
        
        try:
            self._connection = sqlite3.connect(file_path)
            self._connection.row_factory = sqlite3.Row
            self._connected = True
        except sqlite3.Error as e:
            raise ConnectionError(f"Failed to connect to SQLite: {e}")
    
    def disconnect(self) -> None:
        """Close SQLite connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
        self._connected = False
    
    def execute(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute SQL query and return results as list of dicts."""
        if not self._connection:
            self.connect()
        
        try:
            cursor = self._connection.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            # Get column names from description
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
            else:
                return []
        
        except sqlite3.Error as e:
            raise QueryExecutionError(f"SQLite query failed: {e}")
    
    def get_schema(self) -> Dict[str, Any]:
        """Get complete database schema."""
        if not self._connection:
            self.connect()
        
        cursor = self._connection.cursor()
        
        # Get all tables
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        table_names = [row[0] for row in cursor.fetchall()]
        
        tables = []
        for table_name in table_names:
            table_info = self.get_table_info(table_name)
            tables.append(table_info)
        
        # Get foreign key relationships
        relationships = []
        for table_name in table_names:
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            for fk in cursor.fetchall():
                relationships.append({
                    "from_table": table_name,
                    "from_column": fk[3],
                    "to_table": fk[2],
                    "to_column": fk[4]
                })
        
        return {
            "tables": tables,
            "relationships": relationships,
            "table_count": len(tables)
        }
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get detailed information about a table."""
        if not self._connection:
            self.connect()
        
        cursor = self._connection.cursor()
        
        # Get columns
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = []
        primary_keys = []
        for col in cursor.fetchall():
            col_info = {
                "name": col[1],
                "type": col[2],
                "nullable": not col[3],  # notnull is col[3]
                "default": col[4],
                "primary_key": bool(col[5])
            }
            columns.append(col_info)
            if col[5]:
                primary_keys.append(col[1])
        
        # Get foreign keys
        cursor.execute(f"PRAGMA foreign_key_list({table_name})")
        foreign_keys = []
        for fk in cursor.fetchall():
            foreign_keys.append({
                "column": fk[3],
                "references_table": fk[2],
                "references_column": fk[4]
            })
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cursor.fetchone()[0]
        
        return {
            "name": table_name,
            "columns": columns,
            "primary_keys": primary_keys,
            "foreign_keys": foreign_keys,
            "row_count": row_count
        }
    
    def get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get sample rows from a table."""
        sql = f"SELECT * FROM {table_name} LIMIT {limit}"
        return self.execute(sql)
    
    def get_column_values(self, table_name: str, column_name: str, limit: int = 100) -> List[Any]:
        """Get distinct values from a column (useful for exploration)."""
        sql = f"SELECT DISTINCT {column_name} FROM {table_name} LIMIT {limit}"
        results = self.execute(sql)
        return [row[column_name] for row in results]


# Convenience function
def create_sqlite_adapter(file_path: str) -> SQLiteAdapter:
    """Create and connect a SQLite adapter."""
    adapter = SQLiteAdapter(file_path)
    adapter.connect()
    return adapter
