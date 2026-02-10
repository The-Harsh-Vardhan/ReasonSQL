"""
PostgreSQL Database Adapter.

Implements DatabaseAdapter interface for PostgreSQL databases.
Used for cloud/production deployments.

NOTE: This is a basic implementation. Production usage may require:
- Connection pooling (asyncpg, psycopg2.pool)
- SSL configuration
- More robust error handling
"""

from typing import List, Dict, Any, Optional

from .database_adapter import (
    DatabaseAdapter, 
    ConnectionConfig, 
    DatabaseType,
    DatabaseError,
    ConnectionError,
    QueryExecutionError
)


class PostgresAdapter(DatabaseAdapter):
    """
    PostgreSQL implementation of DatabaseAdapter.
    
    Features:
    - Full PostgreSQL support via psycopg2
    - Schema introspection via information_schema
    - Parameterized queries for security
    
    Requirements:
    - psycopg2-binary (pip install psycopg2-binary)
    """
    
    def __init__(self, connection_string: str = None, **kwargs):
        """
        Initialize Postgres adapter.
        
        Args:
            connection_string: Full connection string (postgresql://user:pass@host/db)
            **kwargs: Or individual params (host, port, database, user, password)
        """
        config = ConnectionConfig(
            db_type=DatabaseType.POSTGRES,
            connection_string=connection_string,
            host=kwargs.get("host"),
            port=kwargs.get("port", 5432),
            database=kwargs.get("database"),
            user=kwargs.get("user"),
            password=kwargs.get("password")
        )
        super().__init__(config)
        self._connection = None
    
    def connect(self) -> None:
        """Establish connection to PostgreSQL database."""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except ImportError:
            raise ConnectionError(
                "psycopg2 not installed. Run: pip install psycopg2-binary"
            )
        
        try:
            if self.config.connection_string:
                self._connection = psycopg2.connect(
                    self.config.connection_string,
                    cursor_factory=RealDictCursor
                )
            else:
                self._connection = psycopg2.connect(
                    host=self.config.host,
                    port=self.config.port,
                    database=self.config.database,
                    user=self.config.user,
                    password=self.config.password,
                    cursor_factory=RealDictCursor
                )
            self._connected = True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to PostgreSQL: {e}")
    
    def disconnect(self) -> None:
        """Close PostgreSQL connection."""
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
            
            # Check if query returns results
            if cursor.description:
                return [dict(row) for row in cursor.fetchall()]
            else:
                self._connection.commit()
                return []
        
        except Exception as e:
            self._connection.rollback()
            raise QueryExecutionError(f"PostgreSQL query failed: {e}")
    
    def get_schema(self) -> Dict[str, Any]:
        """Get complete database schema using information_schema."""
        if not self._connection:
            self.connect()
        
        # Get all tables in public schema
        tables_sql = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        table_rows = self.execute(tables_sql)
        table_names = [row["table_name"] for row in table_rows]
        
        tables = []
        for table_name in table_names:
            table_info = self.get_table_info(table_name)
            tables.append(table_info)
        
        # Get foreign key relationships
        fk_sql = """
            SELECT
                tc.table_name as from_table,
                kcu.column_name as from_column,
                ccu.table_name as to_table,
                ccu.column_name as to_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
        """
        relationships = self.execute(fk_sql)
        
        return {
            "tables": tables,
            "relationships": relationships,
            "table_count": len(tables)
        }
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get detailed information about a table."""
        if not self._connection:
            self.connect()
        
        # Get columns
        columns_sql = """
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = %s
            ORDER BY ordinal_position
        """
        columns_raw = self.execute(columns_sql, (table_name,))
        columns = [
            {
                "name": col["column_name"],
                "type": col["data_type"],
                "nullable": col["is_nullable"] == "YES",
                "default": col["column_default"]
            }
            for col in columns_raw
        ]
        
        # Get primary keys
        pk_sql = """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
            AND tc.table_schema = 'public'
            AND tc.table_name = %s
        """
        pk_rows = self.execute(pk_sql, (table_name,))
        primary_keys = [row["column_name"] for row in pk_rows]
        
        # Get row count (approximate for large tables)
        count_sql = f"SELECT COUNT(*) as count FROM {table_name}"
        count_rows = self.execute(count_sql)
        row_count = count_rows[0]["count"] if count_rows else 0
        
        return {
            "name": table_name,
            "columns": columns,
            "primary_keys": primary_keys,
            "row_count": row_count
        }
    
    def get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get sample rows from a table."""
        sql = f"SELECT * FROM {table_name} LIMIT {limit}"
        return self.execute(sql)


# Convenience function
def create_postgres_adapter(connection_string: str) -> PostgresAdapter:
    """Create and connect a Postgres adapter."""
    adapter = PostgresAdapter(connection_string=connection_string)
    adapter.connect()
    return adapter
