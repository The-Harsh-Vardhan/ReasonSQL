"""
Query router — handles natural language query execution.

Endpoints:
- POST /query — Execute NL query against the database
"""

import asyncio
from fastapi import APIRouter, HTTPException, status

from backend.models import ExecutionStatus
from backend.db_connection import test_connection

from ..schemas import (
    QueryRequest, QueryResponse,
    ExecutionStatusAPI, AgentActionAPI, ReasoningTraceAPI,
)
from ..deps import (
    database_registry, get_orchestrator,
    logger, QUERY_TIMEOUT_SECONDS,
)


router = APIRouter(tags=["Query"])


# =============================================================================
# HELPERS
# =============================================================================

def _convert_execution_status(es: ExecutionStatus) -> ExecutionStatusAPI:
    """Convert backend ExecutionStatus to API enum."""
    mapping = {
        ExecutionStatus.SUCCESS: ExecutionStatusAPI.SUCCESS,
        ExecutionStatus.ERROR: ExecutionStatusAPI.ERROR,
        ExecutionStatus.BLOCKED: ExecutionStatusAPI.BLOCKED,
        ExecutionStatus.EMPTY: ExecutionStatusAPI.EMPTY,
    }
    return mapping.get(es, ExecutionStatusAPI.ERROR)


def _convert_reasoning_trace(trace) -> ReasoningTraceAPI:
    """Convert backend ReasoningTrace to API model."""
    actions = [
        AgentActionAPI(
            agent_name=action.agent_name,
            summary=action.output_summary,
            detail=action.reasoning,
            timestamp_ms=None,
        )
        for action in trace.actions
    ]
    return ReasoningTraceAPI(
        actions=actions,
        final_status=_convert_execution_status(trace.final_status),
        total_time_ms=trace.total_time_ms,
        correction_attempts=trace.correction_attempts,
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/query", response_model=QueryResponse)
async def execute_query(request: QueryRequest):
    """
    Execute a natural language query against the database.

    The query is processed by the multi-agent pipeline:
    1. IntentAnalyzer → 2. ClarificationAgent → 3. SchemaExplorer → ...

    Uses async thread offloading to avoid blocking the event loop
    and enforces a configurable timeout.
    """
    # Validate database exists
    db_info = database_registry.get(request.database_id)
    if not db_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database '{request.database_id}' not registered",
        )

    # If registry says disconnected, do a live re-check
    if not db_info.get("connected"):
        live_status = test_connection()
        if live_status.get("connected"):
            db_info["connected"] = True
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Database '{request.database_id}' is not connected",
            )

    try:
        orchestrator = get_orchestrator()

        # Run the synchronous orchestrator in a thread pool so we don't
        # block the async event loop, and wrap with a timeout.
        response = await asyncio.wait_for(
            asyncio.to_thread(orchestrator.process_query, request.query),
            timeout=QUERY_TIMEOUT_SECONDS,
        )

        return QueryResponse(
            success=response.reasoning_trace.final_status == ExecutionStatus.SUCCESS,
            answer=response.answer,
            sql_used=response.sql_used,
            data_preview=response.data_preview,
            row_count=response.row_count,
            is_meta_query=response.is_meta_query,
            reasoning_trace=_convert_reasoning_trace(response.reasoning_trace),
            warnings=response.warnings,
        )

    except asyncio.TimeoutError:
        logger.error("Query timed out after %ds: %s", QUERY_TIMEOUT_SECONDS, request.query[:100])
        return QueryResponse(
            success=False,
            answer=f"Query timed out after {QUERY_TIMEOUT_SECONDS} seconds. Try a simpler question.",
            error="timeout",
            reasoning_trace=ReasoningTraceAPI(
                final_status=ExecutionStatusAPI.ERROR
            ),
        )

    except Exception as e:
        # Log the full error internally, return sanitized message to client
        logger.exception("Query failed: %s", request.query[:100])
        return QueryResponse(
            success=False,
            answer="An internal error occurred while processing your query. Please try again.",
            error="internal_error",
            reasoning_trace=ReasoningTraceAPI(
                final_status=ExecutionStatusAPI.ERROR
            ),
        )
