"""
Query router — handles natural language query execution.

Endpoints:
- POST /query        — Execute NL query against the database via LangGraph pipeline
- POST /query/stream — Stream query execution as Server-Sent Events (see stream.py)
"""

import asyncio
import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from backend.db_connection import test_connection
from backend.cache import get_cached, set_cached
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
# HELPERS (shared with stream.py)
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

    # Determine status — check self-correction recovery: if row_count > 0, the query succeeded
    # even if execution_error has a stale value from before self-correction succeeded.
    row_count = pipeline_state.get("row_count", 0)
    intent = pipeline_state.get("intent", "DATA_QUERY")
    exec_error = pipeline_state.get("execution_error", "")
    recovered = row_count > 0 or intent in ("META_QUERY", "AMBIGUOUS")

    if pipeline_state.get("pipeline_error"):
        final_status = ExecutionStatusAPI.ERROR
    elif bool(exec_error) and not recovered:
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


def _build_query_response_from_state(
    final_state: dict,
    total_time_ms: float = 0,
    cache_hit: bool = False,
    run_id: Optional[str] = None,
) -> QueryResponse:
    """
    Build a QueryResponse from a completed LangGraph PipelineState.

    Shared between the regular /query endpoint and the /query/stream endpoint.
    """
    answer = final_state.get("final_answer", "No answer generated.")
    sql_used = (
        final_state.get("corrected_sql")
        or final_state.get("generated_sql")
        or "N/A"
    )
    results = final_state.get("execution_result") or []
    row_count = final_state.get("row_count", 0)
    is_meta = final_state.get("intent") == "META_QUERY"

    # Determine success — trust row_count over stale execution_error
    pipeline_failed = bool(final_state.get("pipeline_error"))
    exec_error = final_state.get("execution_error", "")
    recovered = row_count > 0 or is_meta or final_state.get("intent") == "AMBIGUOUS"
    has_error = pipeline_failed or (bool(exec_error) and not recovered)

    reasoning_trace = _build_reasoning_trace_api(final_state)
    if total_time_ms:
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
            final_state.get("execution_error") if not recovered else None,
        ])),
        cache_hit=cache_hit,
        run_id=run_id,
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

    Supports:
    - Multi-turn conversation via `history` field
    - Session persistence via `thread_id` (LangGraph checkpointing)
    - Result caching (Redis/in-memory, 5-minute TTL)
    - LangSmith run_id in response for feedback annotation
    """
    db_id = request.database_id or "default"

    # Validate database exists
    db_info = database_registry.get(db_id)
    if not db_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database '{db_id}' not registered",
        )

    # Live connection re-check if registry says disconnected
    if not db_info.get("connected"):
        live_status = test_connection()
        if live_status.get("connected"):
            db_info["connected"] = True
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Database '{db_id}' is not connected",
            )

    # ── Cache check ──────────────────────────────────────────────────────────
    cached = await get_cached(request.query, db_id)
    if cached:
        # Deserialize and return cached QueryResponse
        try:
            return QueryResponse(**{**cached, "cache_hit": True})
        except Exception:
            pass  # If deserialization fails, re-run the query

    try:
        pipeline = get_orchestrator()

        # Session thread ID for LangGraph checkpointing
        thread_id = request.thread_id or str(uuid.uuid4())

        # Initial state for LangGraph pipeline
        initial_state = {
            "user_query": request.query,
            "history": request.history or [],
            "messages": [],
            "retry_count": 0,
            "max_retries": MAX_RETRIES,
            "reasoning_trace": [],
        }

        config = {"configurable": {"thread_id": thread_id}}

        start_time = time.time()

        # Invoke LangGraph pipeline (async) with thread config
        final_state = await asyncio.wait_for(
            pipeline.ainvoke(initial_state, config=config),
            timeout=QUERY_TIMEOUT_SECONDS,
        )

        total_time_ms = (time.time() - start_time) * 1000

        # Extract LangSmith run_id if available
        run_id: Optional[str] = None
        try:
            from langsmith import get_current_run_tree
            run_tree = get_current_run_tree()
            if run_tree:
                run_id = str(run_tree.id)
        except Exception:
            pass

        response = _build_query_response_from_state(
            final_state,
            total_time_ms=total_time_ms,
            cache_hit=False,
            run_id=run_id,
        )

        # ── Cache successful results ─────────────────────────────────────────
        if response.success and response.row_count >= 0:
            await set_cached(request.query, db_id, response.model_dump())

        return response

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
