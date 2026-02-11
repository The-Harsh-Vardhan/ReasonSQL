"""
Database management router — register, list, and inspect databases.

Endpoints:
- POST   /databases              — Register a new database
- GET    /databases               — List all registered databases
- GET    /databases/{id}/schema   — Get schema for a database
"""

import os
from fastapi import APIRouter, HTTPException, status

from backend.db_connection import get_tables, get_table_columns, get_row_count

from ..schemas import (
    DatabaseRegisterRequest, DatabaseInfo, DatabaseListResponse,
    SchemaResponse, TableSchema,
    DatabaseType,
)
from ..deps import database_registry, logger


router = APIRouter(prefix="/databases", tags=["Databases"])


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("", response_model=DatabaseInfo)
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
            detail="file_path required for SQLite databases",
        )

    if request.type == DatabaseType.POSTGRES and not request.connection_string:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="connection_string required for Postgres databases",
        )

    # Check connection
    connected = False
    if request.type == DatabaseType.SQLITE:
        connected = os.path.exists(request.file_path)
        if connected:
            logger.info("SQLite database registered: %s", request.id)
        else:
            logger.warning("SQLite file not found for database '%s': %s", request.id, request.file_path)

    elif request.type == DatabaseType.POSTGRES:
        # Actually test the Postgres connection instead of placeholder
        try:
            import psycopg2
            conn = psycopg2.connect(request.connection_string, connect_timeout=10)
            cur = conn.cursor()
            cur.execute("SELECT 1")
            conn.close()
            connected = True
            logger.info("PostgreSQL database registered and connected: %s", request.id)
        except Exception as e:
            logger.warning("PostgreSQL connection failed for '%s': %s", request.id, str(e))
            connected = False

    # Register
    database_registry[request.id] = {
        "id": request.id,
        "type": request.type,
        "file_path": request.file_path,
        "connection_string": request.connection_string,
        "connected": connected,
    }

    return DatabaseInfo(
        id=request.id,
        type=request.type,
        connected=connected,
    )


@router.get("", response_model=DatabaseListResponse)
async def list_databases():
    """List all registered databases."""
    databases = [
        DatabaseInfo(
            id=db["id"],
            type=db["type"],
            connected=db.get("connected", False),
        )
        for db in database_registry.values()
    ]
    return DatabaseListResponse(databases=databases)


@router.get("/{database_id}/schema", response_model=SchemaResponse)
async def get_database_schema(database_id: str):
    """
    Get schema information for a registered database.

    Returns all tables with their columns. Supports both SQLite and PostgreSQL.
    """
    db_info = database_registry.get(database_id)
    if not db_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database '{database_id}' not registered",
        )

    try:
        table_names = get_tables()
        tables = []
        for table_name in table_names:
            columns = get_table_columns(table_name)
            col_list = [{"name": c["name"], "type": c.get("type", "unknown")} for c in columns]
            try:
                row_count = get_row_count(table_name)
            except Exception:
                row_count = None

            tables.append(TableSchema(
                name=table_name,
                columns=col_list,
                row_count=row_count,
            ))

        return SchemaResponse(
            database_id=database_id,
            tables=tables,
        )

    except Exception as e:
        logger.exception("Failed to read schema for database '%s'", database_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read schema: {str(e)}",
        )
