"""
Query router — handles natural language query execution.

Endpoints:
- POST /query — Execute NL query against the database via LangGraph pipeline
"""

import asyncio
import time
from fastapi import APIRouter, HTTPException, status

from backend.db_connection import test_connection
from configs import MAX_RETRIES

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

def _build_reasoning_trace_api(pipeline_state: dict) -> ReasoningTraceAPI:
    """
    Convert LangGraph PipelineState reasoning_trace list into ReasoningTraceAPI.

    The trace is a list of dicts: [{agent, summary, detail}, ...]
    """
    raw_trace = pipeline_state.get("reasoning_trace", [])

    actions = [
        AgentActionAPI(
            agent_name=entry.get("agent", "Unknown"),
            summary=entry.get("summary", ""),
            detail=entry.get("detail", ""),
            timestamp_ms=None,
        )
        for entry in raw_trace
    ]

    # Determine status
    if pipeline_state.get("pipeline_error"):
        final_status = ExecutionStatusAPI.ERROR
    elif pipeline_state.get("execution_error"):
        final_status = ExecutionStatusAPI.ERROR
    elif pipeline_state.get("intent") == "AMBIGUOUS":
        final_status = ExecutionStatusAPI.BLOCKED
    elif pipeline_state.get("row_count", 0) == 0 and pipeline_state.get("intent") == "DATA_QUERY":
        final_status = ExecutionStatusAPI.EMPTY
    else:
        final_status = ExecutionStatusAPI.SUCCESS

    return ReasoningTraceAPI(
        actions=actions,
        final_status=final_status,
        total_time_ms=pipeline_state.get("execution_time_ms"),
        correction_attempts=pipeline_state.get("retry_count", 0),
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/query", response_model=QueryResponse)
async def execute_query(request: QueryRequest):
    """
    Execute a natural language query against the database.

    The query is processed by the LangGraph multi-agent pipeline:
    1. SchemaRetrieval (FAISS + BM25 + CrossEncoder)
    2. Reasoning (Intent + Clarification + Planning)
    3. SQLGeneration → SafetyValidation → SQLExecution
    4. [SelfCorrection if needed]
    5. ResponseSynthesis

    Supports multi-turn conversation via `history` field.
    """
    # Validate database exists
    db_info = database_registry.get(request.database_id)
    if not db_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database '{request.database_id}' not registered",
        )

    # Live connection re-check if registry says disconnected
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
        pipeline = get_orchestrator()

        # Initial state for LangGraph pipeline
        initial_state = {
            "user_query": request.query,
            "history": request.history or [],
            "messages": [],
            "retry_count": 0,
            "max_retries": MAX_RETRIES,
            "reasoning_trace": [],
        }

        start_time = time.time()

        # Invoke LangGraph pipeline (async)
        final_state = await asyncio.wait_for(
            pipeline.ainvoke(initial_state),
            timeout=QUERY_TIMEOUT_SECONDS,
        )

        total_time_ms = (time.time() - start_time) * 1000

        # Build response
        answer = final_state.get("final_answer", "No answer generated.")
        sql_used = (
            final_state.get("corrected_sql")
            or final_state.get("generated_sql")
            or "N/A"
        )
        results = final_state.get("execution_result") or []
        row_count = final_state.get("row_count", 0)
        is_meta = final_state.get("intent") == "META_QUERY"
        has_error = bool(final_state.get("pipeline_error") or final_state.get("execution_error"))

        reasoning_trace = _build_reasoning_trace_api(final_state)
        reasoning_trace.total_time_ms = total_time_ms

        return QueryResponse(
            success=not has_error,
            answer=answer,
            sql_used=sql_used if sql_used != "N/A" else None,
            data_preview=results[:10] if results else None,
            row_count=row_count,
            is_meta_query=is_meta,
            reasoning_trace=reasoning_trace,
            warnings=list(filter(None, [
                final_state.get("pipeline_error"),
                final_state.get("execution_error"),
            ])),
        )

    except asyncio.TimeoutError:
        logger.error("Query timed out after %ds: %s", QUERY_TIMEOUT_SECONDS, request.query[:100])
        return QueryResponse(
            success=False,
            answer=f"Query timed out after {QUERY_TIMEOUT_SECONDS} seconds. Try a simpler question.",
            error="timeout",
            reasoning_trace=ReasoningTraceAPI(final_status=ExecutionStatusAPI.ERROR),
        )

    except Exception as e:
        logger.exception("Query failed: %s", request.query[:100])
        return QueryResponse(
            success=False,
            answer="An internal error occurred while processing your query. Please try again.",
            error="internal_error",
            reasoning_trace=ReasoningTraceAPI(final_status=ExecutionStatusAPI.ERROR),
        )
