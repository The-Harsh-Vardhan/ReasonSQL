"""
Pydantic schemas for ReasonSQL API.

These models define the request/response structure for all API endpoints.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


# ============================================================
# ENUMS
# ============================================================

class DatabaseType(str, Enum):
    """Supported database types."""
    SQLITE = "sqlite"
    POSTGRES = "postgres"


class ExecutionStatusAPI(str, Enum):
    """Query execution status (mirrors backend ExecutionStatus)."""
    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"
    EMPTY = "empty"


# ============================================================
# REQUEST MODELS
# ============================================================

class QueryRequest(BaseModel):
    """Request body for POST /query."""
    query: str = Field(..., description="Natural language query", min_length=1)
    database_id: Optional[str] = Field(
        default="default", 
        description="Database identifier (default uses configured SQLite)"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {"query": "How many customers are there?"},
                {"query": "Show me top 5 artists by tracks", "database_id": "chinook"}
            ]
        }
    }


class DatabaseRegisterRequest(BaseModel):
    """Request body for POST /databases."""
    id: str = Field(..., description="Unique database identifier")
    type: DatabaseType = Field(..., description="Database type")
    connection_string: Optional[str] = Field(
        None, 
        description="Connection string (for Postgres)"
    )
    file_path: Optional[str] = Field(
        None, 
        description="File path (for SQLite)"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {"id": "chinook", "type": "sqlite", "file_path": "./data/chinook.db"},
                {"id": "production", "type": "postgres", "connection_string": "postgresql://user:pass@host/db"}
            ]
        }
    }


# ============================================================
# RESPONSE MODELS
# ============================================================

class AgentActionAPI(BaseModel):
    """Single agent action in reasoning trace."""
    agent_name: str
    summary: str
    detail: Optional[str] = None
    timestamp_ms: Optional[float] = None


class ReasoningTraceAPI(BaseModel):
    """Reasoning trace showing agent pipeline execution."""
    actions: List[AgentActionAPI] = []
    final_status: ExecutionStatusAPI = ExecutionStatusAPI.SUCCESS
    total_time_ms: Optional[float] = None
    correction_attempts: int = 0


class QueryResponse(BaseModel):
    """Response body for POST /query."""
    success: bool = Field(..., description="Whether the query succeeded")
    answer: str = Field(..., description="Human-readable answer")
    sql_used: Optional[str] = Field(None, description="SQL query executed")
    data_preview: Optional[List[Dict[str, Any]]] = Field(
        None, 
        description="First N rows of results"
    )
    row_count: int = Field(0, description="Total rows returned")
    is_meta_query: bool = Field(False, description="Was this a schema introspection query?")
    reasoning_trace: ReasoningTraceAPI = Field(
        default_factory=ReasoningTraceAPI,
        description="Full agent execution trace"
    )
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = Field(None, description="Error message if failed")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "answer": "There are 59 customers in the database.",
                    "sql_used": "SELECT COUNT(*) FROM Customer",
                    "row_count": 1,
                    "is_meta_query": False
                }
            ]
        }
    }


class DatabaseInfo(BaseModel):
    """Database registration info."""
    id: str
    type: DatabaseType
    connected: bool = False


class DatabaseListResponse(BaseModel):
    """Response for GET /databases."""
    databases: List[DatabaseInfo]


class TableSchema(BaseModel):
    """Schema for a single table."""
    name: str
    columns: List[Dict[str, str]]
    row_count: Optional[int] = None


class SchemaResponse(BaseModel):
    """Response for GET /databases/{id}/schema."""
    database_id: str
    tables: List[TableSchema]


class HealthResponse(BaseModel):
    """Response for GET /health."""
    status: str = "healthy"
    version: str = "1.0.0"
    llm_provider: Optional[str] = None
    database_connected: bool = False
    db_type: Optional[str] = None
    db_name: Optional[str] = None
    dataset_name: Optional[str] = None
    table_count: int = 0
    tables: List[str] = []
