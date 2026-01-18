"""
API Client for ReasonSQL Frontend.

This module provides a clean interface for the frontend to communicate
with the FastAPI backend. Streamlit should ONLY use this module for
backend communication.

Usage:
    from frontend.api_client import ReasonSQLClient
    
    client = ReasonSQLClient()
    response = client.query("How many customers are there?")
"""

import httpx
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum


# ============================================================
# CONFIGURATION
# ============================================================

API_BASE_URL = "http://localhost:8000"


# ============================================================
# DATA MODELS (Mirrors backend API schemas)
# ============================================================

class ExecutionStatusAPI(str, Enum):
    """Query execution status."""
    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"
    EMPTY = "empty"


@dataclass
class AgentActionAPI:
    """Single agent action in reasoning trace."""
    agent_name: str
    summary: str
    detail: Optional[str] = None
    timestamp_ms: Optional[float] = None


@dataclass
class ReasoningTraceAPI:
    """Reasoning trace showing agent pipeline execution."""
    actions: List[AgentActionAPI]
    final_status: ExecutionStatusAPI
    total_time_ms: Optional[float] = None
    correction_attempts: int = 0


@dataclass
class QueryResponse:
    """Response from POST /query endpoint."""
    success: bool
    answer: str
    sql_used: Optional[str] = None
    data_preview: Optional[List[Dict[str, Any]]] = None
    row_count: int = 0
    is_meta_query: bool = False
    reasoning_trace: Optional[ReasoningTraceAPI] = None
    warnings: List[str] = None
    error: Optional[str] = None


@dataclass
class DatabaseInfo:
    """Database registration info."""
    id: str
    type: str
    connected: bool = False


@dataclass 
class TableSchema:
    """Schema for a single table."""
    name: str
    columns: List[Dict[str, str]]
    row_count: Optional[int] = None


# ============================================================
# API CLIENT
# ============================================================

class ReasonSQLClient:
    """
    HTTP client for ReasonSQL FastAPI backend.
    
    Provides typed methods for all API endpoints.
    Handles connection errors gracefully.
    """
    
    def __init__(self, base_url: str = API_BASE_URL, timeout: float = 120.0):
        """
        Initialize API client.
        
        Args:
            base_url: FastAPI server URL (default: http://localhost:8000)
            timeout: Request timeout in seconds (default: 120s for LLM queries)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health status."""
        try:
            response = self._client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def query(self, query_text: str, database_id: str = "default") -> QueryResponse:
        """
        Execute a natural language query.
        
        Args:
            query_text: Natural language query
            database_id: Database to query against
        
        Returns:
            QueryResponse with answer, SQL, reasoning trace
        """
        try:
            response = self._client.post(
                f"{self.base_url}/query",
                json={"query": query_text, "database_id": database_id}
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse reasoning trace
            trace_data = data.get("reasoning_trace", {})
            actions = [
                AgentActionAPI(
                    agent_name=a.get("agent_name", ""),
                    summary=a.get("summary", ""),
                    detail=a.get("detail"),
                    timestamp_ms=a.get("timestamp_ms")
                )
                for a in trace_data.get("actions", [])
            ]
            
            reasoning_trace = ReasoningTraceAPI(
                actions=actions,
                final_status=ExecutionStatusAPI(trace_data.get("final_status", "error")),
                total_time_ms=trace_data.get("total_time_ms"),
                correction_attempts=trace_data.get("correction_attempts", 0)
            )
            
            return QueryResponse(
                success=data.get("success", False),
                answer=data.get("answer", ""),
                sql_used=data.get("sql_used"),
                data_preview=data.get("data_preview"),
                row_count=data.get("row_count", 0),
                is_meta_query=data.get("is_meta_query", False),
                reasoning_trace=reasoning_trace,
                warnings=data.get("warnings", []),
                error=data.get("error")
            )
        
        except httpx.TimeoutException:
            return QueryResponse(
                success=False,
                answer="Query timed out. The LLM may be slow or rate limited.",
                error="Request timed out"
            )
        except httpx.ConnectError:
            return QueryResponse(
                success=False,
                answer="Cannot connect to API server. Is FastAPI running on port 8000?",
                error="Connection failed"
            )
        except Exception as e:
            return QueryResponse(
                success=False,
                answer=f"API error: {str(e)}",
                error=str(e)
            )
    
    def list_databases(self) -> List[DatabaseInfo]:
        """List all registered databases."""
        try:
            response = self._client.get(f"{self.base_url}/databases")
            response.raise_for_status()
            data = response.json()
            return [
                DatabaseInfo(
                    id=db.get("id", ""),
                    type=db.get("type", ""),
                    connected=db.get("connected", False)
                )
                for db in data.get("databases", [])
            ]
        except Exception as e:
            return []
    
    def get_schema(self, database_id: str = "default") -> List[TableSchema]:
        """Get schema for a database."""
        try:
            response = self._client.get(f"{self.base_url}/databases/{database_id}/schema")
            response.raise_for_status()
            data = response.json()
            return [
                TableSchema(
                    name=table.get("name", ""),
                    columns=table.get("columns", []),
                    row_count=table.get("row_count")
                )
                for table in data.get("tables", [])
            ]
        except Exception as e:
            return []
    
    def is_connected(self) -> bool:
        """Check if API is reachable and database is connected."""
        health = self.health_check()
        return health.get("status") == "healthy" and health.get("database_connected", False)
    
    def close(self):
        """Close the HTTP client."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def create_client(base_url: str = API_BASE_URL) -> ReasonSQLClient:
    """Create a ReasonSQL API client."""
    return ReasonSQLClient(base_url=base_url)
