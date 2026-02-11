"""
Centralized Database Connection Module.

Provides a unified interface for connecting to SQLite or PostgreSQL databases.
Auto-detects database type based on environment variables:
- DATABASE_URL (PostgreSQL/Supabase) - takes priority
- DATABASE_PATH (SQLite) - fallback for local development

Usage:
    from backend.db_connection import get_connection, execute_query, get_db_type
    
    # Execute a query (works with both SQLite and PostgreSQL)
    results = execute_query("SELECT * FROM users LIMIT 10")
    
    # Get raw connection if needed
    conn = get_connection()
"""

import os
import sqlite3
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from contextlib import contextmanager

# Lazy import psycopg2 (only when PostgreSQL is used)
psycopg2 = None


def _import_psycopg2():
    """Lazy import psycopg2 to avoid ImportError when not using PostgreSQL."""
    global psycopg2
    if psycopg2 is None:
        try:
            import psycopg2 as pg
            from psycopg2.extras import RealDictCursor
            psycopg2 = pg
        except ImportError:
            raise ImportError(
                "psycopg2 not installed. Run: pip install psycopg2-binary\n"
                "This is required for PostgreSQL/Supabase connections."
            )
    return psycopg2


# =============================================================================
# DATABASE TYPE DETECTION
# =============================================================================

def get_db_type() -> str:
    """
    Detect database type from environment variables.
    
    Returns:
        'postgresql' if DATABASE_URL is set, 'sqlite' otherwise
    """
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url and (database_url.startswith("postgres") or database_url.startswith("postgresql")):
        return "postgresql"
    return "sqlite"


def get_database_url() -> Optional[str]:
    """Get PostgreSQL connection URL if configured."""
    return os.getenv("DATABASE_URL", "").strip() or None


def get_database_path() -> str:
    """Get SQLite database path."""
    from configs import DATABASE_PATH
    return DATABASE_PATH


# =============================================================================
# CONNECTION MANAGEMENT
# =============================================================================

_pg_connection = None  # Reusable PostgreSQL connection


def get_connection() -> Union[sqlite3.Connection, Any]:
    """
    Get a database connection based on environment configuration.
    
    For SQLite: Returns a new connection each time (lightweight).
    For PostgreSQL: Returns a reusable connection (connection pooling recommended for production).
    
    Returns:
        Database connection object
    """
    db_type = get_db_type()
    
    if db_type == "postgresql":
        return _get_postgres_connection()
    else:
        return _get_sqlite_connection()


def _get_sqlite_connection() -> sqlite3.Connection:
    """Create SQLite connection with row factory."""
    db_path = get_database_path()
    
    if not Path(db_path).exists():
        raise FileNotFoundError(f"SQLite database not found: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _resolve_ipv4(hostname: str) -> str:
    """Resolve hostname to IPv4 address (Render can't reach some IPv6 addresses)."""
    import socket
    try:
        # Force AF_INET (IPv4) resolution
        results = socket.getaddrinfo(hostname, None, socket.AF_INET)
        if results:
            ipv4 = results[0][4][0]
            print(f"[DB] Resolved {hostname} → {ipv4} (IPv4)")
            return ipv4
    except socket.gaierror:
        pass
    return hostname  # Fallback to original


def _inject_ipv4_into_url(database_url: str) -> str:
    """Replace hostname with IPv4 address in DATABASE_URL to avoid IPv6 issues.
    
    ONLY applies to direct Supabase connections (db.*.supabase.co).
    Pooler connections (*.pooler.supabase.com) already resolve to IPv4
    and MUST keep the original hostname for TLS SNI routing.
    """
    from urllib.parse import urlparse, urlunparse
    try:
        parsed = urlparse(database_url)
        hostname = parsed.hostname
        
        # Skip pooler URLs — they need the hostname for SNI-based tenant routing
        if hostname and "pooler.supabase.com" in hostname:
            print(f"[DB] Pooler URL detected ({hostname}), keeping original hostname for SNI")
            return database_url
        
        if hostname and not hostname.replace('.', '').isdigit():
            ipv4 = _resolve_ipv4(hostname)
            if ipv4 != hostname:
                # Replace hostname with IP, preserve port
                new_netloc = parsed.netloc.replace(hostname, ipv4)
                new_url = urlunparse(parsed._replace(netloc=new_netloc))
                return new_url
    except Exception as e:
        print(f"[DB] IPv4 resolution failed, using original URL: {e}")
    return database_url


def _get_postgres_connection():
    """Get or create PostgreSQL connection."""
    global _pg_connection
    
    _import_psycopg2()
    from psycopg2.extras import RealDictCursor
    from urllib.parse import urlparse, unquote
    
    database_url = get_database_url()
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    # Check if existing connection is still valid (BEFORE logging)
    if _pg_connection is not None:
        try:
            _pg_connection.cursor().execute("SELECT 1")
            return _pg_connection
        except Exception:
            # Connection died, recreate
            try:
                _pg_connection.close()
            except Exception:
                pass
            _pg_connection = None
    
    # Only log when actually creating a NEW connection
    parsed = urlparse(database_url)
    masked_pw = (parsed.password or "")[:3] + "***" if parsed.password else "NONE"
    print(f"[DB] Connecting: user={parsed.username}, host={parsed.hostname}, port={parsed.port}, password={masked_pw}")
    
    # For pooler URLs, connect using individual parameters to preserve hostname for SNI
    # and avoid any URL encoding/shell expansion issues with passwords
    if parsed.hostname and "pooler.supabase.com" in parsed.hostname:
        print(f"[DB] Using pooler connection (SNI hostname: {parsed.hostname})")
        _pg_connection = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 6543,
            user=parsed.username,
            password=unquote(parsed.password) if parsed.password else None,
            dbname=parsed.path.lstrip('/') or 'postgres',
            sslmode='require',
            cursor_factory=RealDictCursor
        )
    else:
        # For direct connections, apply IPv4 resolution
        resolved_url = _inject_ipv4_into_url(database_url)
        _pg_connection = psycopg2.connect(
            resolved_url,
            cursor_factory=RealDictCursor
        )
    
    _pg_connection.autocommit = True  # For read-only operations
    return _pg_connection


@contextmanager
def get_connection_context():
    """
    Context manager for database connections.
    
    For SQLite: Opens and closes connection automatically.
    For PostgreSQL: Uses reusable connection, doesn't close on exit.
    
    Usage:
        with get_connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
    """
    db_type = get_db_type()
    
    if db_type == "sqlite":
        conn = _get_sqlite_connection()
        try:
            yield conn
        finally:
            conn.close()
    else:
        conn = _get_postgres_connection()
        yield conn
        # Don't close PostgreSQL connection (reusable)


# =============================================================================
# QUERY EXECUTION
# =============================================================================

def execute_query(sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    """
    Execute SQL query and return results as list of dictionaries.
    
    Works with both SQLite and PostgreSQL.
    
    Args:
        sql: SQL query to execute
        params: Optional query parameters (for parameterized queries)
    
    Returns:
        List of dictionaries where keys are column names
    """
    db_type = get_db_type()
    
    with get_connection_context() as conn:
        cursor = conn.cursor()
        
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        
        # Check if query returns results (SELECT vs INSERT/UPDATE)
        if cursor.description is None:
            return []
        
        if db_type == "sqlite":
            # SQLite Row factory
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        else:
            # PostgreSQL RealDictCursor already returns dicts
            return [dict(row) for row in cursor.fetchall()]


# =============================================================================
# SCHEMA INTROSPECTION
# =============================================================================

def get_tables() -> List[str]:
    """Get list of all table names in the database."""
    db_type = get_db_type()
    
    if db_type == "sqlite":
        sql = """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """
    else:
        sql = """
            SELECT table_name as name
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
    
    results = execute_query(sql)
    return [row["name"] for row in results]


def get_table_columns(table_name: str) -> List[Dict[str, Any]]:
    """Get column information for a table."""
    db_type = get_db_type()
    
    if db_type == "sqlite":
        # Use PRAGMA for SQLite
        with get_connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = []
            for row in cursor.fetchall():
                columns.append({
                    "name": row[1],
                    "type": row[2],
                    "nullable": not row[3],
                    "primary_key": bool(row[5])
                })
            return columns
    else:
        sql = """
            SELECT 
                column_name as name,
                data_type as type,
                is_nullable = 'YES' as nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
        """
        return execute_query(sql, (table_name,))


def get_row_count(table_name: str) -> int:
    """Get row count for a table."""
    # Basic SQL injection protection
    if not table_name.isalnum() and not all(c.isalnum() or c == '_' for c in table_name):
        raise ValueError(f"Invalid table name: {table_name}")
    
    results = execute_query(f"SELECT COUNT(*) as count FROM {table_name}")
    return results[0]["count"] if results else 0


# =============================================================================
# CONNECTION TESTING
# =============================================================================

def test_connection() -> Dict[str, Any]:
    """
    Test database connection and return status.
    
    Returns:
        Dictionary with connection status and info
    """
    db_type = get_db_type()
    
    try:
        if db_type == "postgresql":
            database_url = get_database_url()
            # Mask password in URL
            masked_url = database_url[:20] + "..." if database_url else None
        else:
            masked_url = get_database_path()
        
        # Test with simple query
        tables = get_tables()
        
        # Detect dataset
        dataset_name = None
        chinook_tables = {"Album", "Artist", "Customer", "Employee", "Genre", "Invoice", "InvoiceLine", "MediaType", "Playlist", "PlaylistTrack", "Track"}
        # Both PascalCase and snake_case matches
        chinook_tables_lower = {t.lower() for t in chinook_tables}
        actual_tables_lower = {t.lower() for t in tables}
        
        if len(actual_tables_lower.intersection(chinook_tables_lower)) >= 5:
            dataset_name = "Chinook"
        
        return {
            "connected": True,
            "db_type": db_type,
            "connection_info": masked_url,
            "dataset_name": dataset_name,
            "table_count": len(tables),
            "tables": tables[:5]  # First 5 tables
        }
    except Exception as e:
        return {
            "connected": False,
            "db_type": db_type,
            "error": str(e)
        }


# =============================================================================
# CLEANUP
# =============================================================================

def close_connections():
    """Close any open database connections."""
    global _pg_connection
    
    if _pg_connection is not None:
        try:
            _pg_connection.close()
        except Exception:
            pass
        _pg_connection = None

# =============================================================================
# ASYNC CONNECTION MANAGEMENT
# =============================================================================

import asyncio
from typing import Optional

# Global async pool
_async_pool = None

async def get_async_pool():
    """Get or create asyncpg connection pool."""
    global _async_pool
    
    if _async_pool:
        return _async_pool
    
    database_url = get_database_url()
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    try:
        import asyncpg
        # Resolve IPv4 if needed
        from urllib.parse import urlparse
        parsed = urlparse(database_url)
        
        # IPv4 resolution logic (reused from sync)
        final_url = database_url
        if parsed.hostname and "pooler.supabase.com" not in parsed.hostname:
             final_url = _inject_ipv4_into_url(database_url)

        print(f"[DB] Creating asyncpg pool...")
        _async_pool = await asyncpg.create_pool(
            final_url,
            min_size=1,
            max_size=10,
            command_timeout=60
        )
        return _async_pool
    except ImportError:
        raise ImportError("asyncpg not installed. Run: pip install asyncpg")
    except Exception as e:
        print(f"[DB] Async pool creation failed: {e}")
        raise

async def close_async_pool():
    """Close async connection pool."""
    global _async_pool
    if _async_pool:
        await _async_pool.close()
        _async_pool = None

async def execute_query_async(sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    """
    Execute SQL query asynchronously.
    
    - PostgreSQL: Uses asyncpg pool
    - SQLite: Runs sync execute_query in thread pool (fallback)
    """
    db_type = get_db_type()
    
    if db_type == "sqlite":
        # Fallback to sync execution in thread
        return await asyncio.to_thread(execute_query, sql, params)
    
    # PostgreSQL Async
    pool = await get_async_pool()
    async with pool.acquire() as conn:
        try:
            # asyncpg uses $1, $2 syntax, but our SQL might use %s (psycopg2 style)
            # Basic conversion: %s -> $n
            # This is tricky if queries are complex. 
            # Ideally, the generator should produce correct syntax.
            # But for now, let's assume we handle parameter styles or try to convert.
            
            # Simple conversion for standard parameterized queries
            if params:
                # Convert %s to $1, $2...
                # This is a naive regex replacement, but robust enough for most generated SQL
                import re
                param_count = 0
                def replace_param(match):
                    nonlocal param_count
                    param_count += 1
                    return f"${param_count}"
                
                async_sql = re.sub(r'%s', replace_param, sql)
                rows = await conn.fetch(async_sql, *params)
            else:
                rows = await conn.fetch(sql)
            
            return [dict(row) for row in rows]
        except Exception as e:
            # Log error and re-raise
            print(f"[DB] Async execution failed: {e}")
            raise
