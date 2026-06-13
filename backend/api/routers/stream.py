"""
SSE Streaming router — ReasonSQL 2.0 Feature A

Provides a POST /query/stream endpoint that emits Server-Sent Events
as the LangGraph pipeline processes each node.

Event format:
    data: {"type": "node_complete", "node": "schema_retrieval", "summary": "...", "step": 1}\n\n
    data: {"type": "result", "data": {<full QueryResponse JSON>}}\n\n
    data: [DONE]\n\n

Why SSE over WebSockets:
    - Simpler: unidirectional (server → client)
    - Works through Vercel's proxy rewrites
    - Native EventSource API in browsers (no library needed)
    - Automatic reconnection built into the browser EventSource spec

Frontend consumption:
    const source = new EventSource("/api/query/stream?...")
    OR via fetch + ReadableStream for POST requests
"""

import asyncio
import json
import logging
import time
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from configs import MAX_RETRIES
from ..schemas import QueryRequest, ExecutionStatusAPI, AgentActionAPI, ReasoningTraceAPI, QueryResponse
from ..deps import database_registry, get_orchestrator, logger, QUERY_TIMEOUT_SECONDS

router = APIRouter(tags=["Streaming"])

_stream_logger = logging.getLogger("reasonsql.stream")


# =============================================================================
# NODE → HUMAN-READABLE LABEL MAP
# =============================================================================

NODE_LABELS = {
    "schema_retrieval": ("🔍", "Schema Retrieval", "Loading database schema via hybrid RAG"),
    "reasoning": ("🧠", "Reasoning & Planning", "Analyzing intent, resolving ambiguity, planning query"),
    "sql_generation": ("⚙️", "SQL Generation", "Generating PostgreSQL query"),
    "safety_validation": ("🛡️", "Safety Validation", "Checking for forbidden keywords, enforcing LIMIT"),
    "sql_execution": ("▶️", "SQL Execution", "Running query against the database"),
    "self_correction": ("🔄", "Self-Correction", "Fixing failed SQL query"),
    "response_synthesis": ("✨", "Response Synthesis", "Synthesizing human-readable answer"),
}


def _node_event(node_name: str, step: int, detail: str = "") -> str:
    """Format a node_complete SSE event."""
    icon, label, default_desc = NODE_LABELS.get(node_name, ("⚡", node_name, ""))
    payload = {
        "type": "node_complete",
        "node": node_name,
        "label": label,
        "icon": icon,
        "description": detail or default_desc,
        "step": step,
    }
    return f"data: {json.dumps(payload)}\n\n"


def _result_event(response: QueryResponse) -> str:
    """Format the final result SSE event."""
    payload = {
        "type": "result",
        "data": response.model_dump(),
    }
    return f"data: {json.dumps(payload, default=str)}\n\n"


def _error_event(message: str) -> str:
    """Format an error SSE event."""
    payload = {"type": "error", "message": message}
    return f"data: {json.dumps(payload)}\n\n"


# =============================================================================
# STREAMING ENDPOINT
# =============================================================================

@router.post("/query/stream")
async def stream_query(request: QueryRequest):
    """
    Stream a natural language query via Server-Sent Events.

    Emits one event per completed LangGraph node, then a final result event.
    The frontend can use this to show real-time agent progress.

    Response format: text/event-stream
    """
    # Validate database
    db_id = request.database_id or "default"
    db_info = database_registry.get(db_id)
    if not db_info:
        async def err_gen():
            yield _error_event(f"Database '{db_id}' not registered")
        return StreamingResponse(err_gen(), media_type="text/event-stream",
                                  headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    thread_id = request.thread_id or str(uuid.uuid4())

    async def event_generator() -> AsyncGenerator[str, None]:
        pipeline = get_orchestrator()

        initial_state = {
            "user_query": request.query,
            "history": request.history or [],
            "messages": [],
            "retry_count": 0,
            "max_retries": MAX_RETRIES,
            "reasoning_trace": [],
        }

        config = {"configurable": {"thread_id": thread_id}}

        step = 0
        final_state = {}
        run_id = None

        try:
            # astream yields partial state updates after each node completes
            async for chunk in pipeline.astream(initial_state, config=config):
                for node_name, node_state in chunk.items():
                    if node_name == "__end__":
                        continue

                    step += 1

                    # Extract the last trace entry for this node's summary
                    trace = node_state.get("reasoning_trace", [])
                    detail = trace[-1].get("summary", "") if trace else ""

                    yield _node_event(node_name, step, detail)

                    # Accumulate final state (last complete state wins)
                    final_state.update(node_state)

                    # Small delay to ensure events flush through proxies
                    await asyncio.sleep(0.01)

            # Build QueryResponse from accumulated final state
            from ..routers.query import _build_reasoning_trace_api, _build_query_response_from_state
            response = _build_query_response_from_state(final_state, run_id=run_id)

            yield _result_event(response)
            yield "data: [DONE]\n\n"

        except asyncio.TimeoutError:
            yield _error_event(f"Query timed out after {QUERY_TIMEOUT_SECONDS}s")
            yield "data: [DONE]\n\n"
        except Exception as exc:
            _stream_logger.exception("Streaming query failed: %s", request.query[:100])
            yield _error_event(f"Internal error: {str(exc)[:200]}")
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",    # Disable Nginx buffering
            "Connection": "keep-alive",
        },
    )
