"""
LangGraph Pipeline — ReasonSQL 2.0

Compiles the multi-agent NL→SQL pipeline as a LangGraph StateGraph.

Architecture:
    schema_retrieval → reasoning → [sql_generation | response_synthesis]
        → safety_validation → sql_execution
        → [self_correction → safety_validation → sql_execution]*
        → response_synthesis → END

Why LangGraph StateGraph:
    - Declarative graph definition with clear node/edge semantics
    - Conditional routing based on state (intent, errors, retry count)
    - Built-in state persistence and checkpointing
    - LangSmith integration: full graph execution traced automatically
    - Async-native: all nodes run with asyncio
    - Thread-safe compilation: compiled graph is reusable and stateless

LangSmith Integration:
    When LANGCHAIN_TRACING_V2=true, LangSmith automatically captures:
    - Full graph execution visualization
    - Per-node input/output states
    - LLM call details (prompt, response, tokens, latency)
    - Retry chains and conditional routing decisions
"""

import logging
from typing import Literal
from functools import lru_cache

from langgraph.graph import StateGraph, END

from configs import MAX_RETRIES
from .state import PipelineState
from .nodes import (
    schema_retrieval_node,
    reasoning_node,
    sql_generation_node,
    safety_validation_node,
    sql_execution_node,
    self_correction_node,
    response_synthesis_node,
)

logger = logging.getLogger("reasonsql.graph.pipeline")


# =============================================================================
# CONDITIONAL EDGE ROUTING FUNCTIONS
# =============================================================================

def route_after_pipeline_check(state: PipelineState) -> Literal["reasoning", "__end__"]:
    """Route: abort if schema retrieval failed."""
    if state.get("pipeline_error"):
        logger.warning("Pipeline aborted at schema retrieval: %s", state.get("pipeline_error"))
        return END
    return "reasoning"


def route_after_reasoning(
    state: PipelineState,
) -> Literal["sql_generation", "response_synthesis", "__end__"]:
    """
    Route after reasoning node based on intent:
    - DATA_QUERY → sql_generation
    - META_QUERY → response_synthesis (no SQL needed)
    - AMBIGUOUS → response_synthesis (clarification questions already set)
    - Pipeline error → END
    """
    if state.get("pipeline_error"):
        return END

    intent = state.get("intent", "DATA_QUERY")

    if intent in ("META_QUERY", "AMBIGUOUS"):
        logger.info("[Router] %s intent → response_synthesis", intent)
        return "response_synthesis"

    logger.info("[Router] DATA_QUERY intent → sql_generation")
    return "sql_generation"


def route_after_safety(
    state: PipelineState,
) -> Literal["sql_execution", "self_correction", "__end__"]:
    """
    Route after safety validation:
    - Approved → sql_execution
    - Rejected + retries remaining → self_correction
    - Rejected + max retries reached → response_synthesis (with error)
    """
    if state.get("pipeline_error"):
        return END

    if state.get("safety_approved"):
        return "sql_execution"

    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", MAX_RETRIES)

    if retry_count < max_retries:
        logger.info("[Router] Safety failed, retry %d/%d → self_correction", retry_count + 1, max_retries)
        return "self_correction"

    logger.warning("[Router] Safety failed after %d retries → response_synthesis", max_retries)
    return "response_synthesis"


def route_after_execution(
    state: PipelineState,
) -> Literal["response_synthesis", "self_correction", "__end__"]:
    """
    Route after SQL execution:
    - Success → response_synthesis
    - Error + retries remaining → self_correction
    - Error + max retries → response_synthesis (with error message)
    """
    if state.get("pipeline_error"):
        return END

    if not state.get("execution_error"):
        return "response_synthesis"

    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", MAX_RETRIES)

    if retry_count < max_retries:
        logger.info("[Router] SQL error, retry %d/%d → self_correction", retry_count + 1, max_retries)
        return "self_correction"

    logger.warning("[Router] SQL failed after %d retries → response_synthesis", max_retries)
    return "response_synthesis"


def route_after_correction(
    state: PipelineState,
) -> Literal["safety_validation", "__end__"]:
    """Route after self-correction: always re-validate safety."""
    if state.get("pipeline_error"):
        return END
    return "safety_validation"


# =============================================================================
# GRAPH COMPILATION
# =============================================================================

def build_pipeline():
    """
    Build and compile the LangGraph NL→SQL StateGraph.

    Graph Structure:
        START
          ↓
        schema_retrieval ──(error)──→ END
          ↓
        reasoning ──────────────────→ response_synthesis (META/AMBIGUOUS)
          ↓ (DATA_QUERY)
        sql_generation
          ↓
        safety_validation ──────────→ self_correction (rejected + retries)
          ↓ (approved)               ↓
        sql_execution    ←───────────┘ (via safety_validation)
          ↓ (success)
        response_synthesis
          ↓
        END

    Returns:
        Compiled LangGraph Runnable (callable with .invoke() or .ainvoke())
    """
    graph = StateGraph(PipelineState)

    # ── Add Nodes ───────────────────────────────────────────────────────────
    graph.add_node("schema_retrieval", schema_retrieval_node)
    graph.add_node("reasoning", reasoning_node)
    graph.add_node("sql_generation", sql_generation_node)
    graph.add_node("safety_validation", safety_validation_node)
    graph.add_node("sql_execution", sql_execution_node)
    graph.add_node("self_correction", self_correction_node)
    graph.add_node("response_synthesis", response_synthesis_node)

    # ── Define Entry Point ───────────────────────────────────────────────────
    graph.set_entry_point("schema_retrieval")

    # ── Define Edges ─────────────────────────────────────────────────────────

    # schema_retrieval → reasoning (or END on error)
    graph.add_conditional_edges(
        "schema_retrieval",
        route_after_pipeline_check,
        {"reasoning": "reasoning", END: END},
    )

    # reasoning → sql_generation or response_synthesis (intent-based routing)
    graph.add_conditional_edges(
        "reasoning",
        route_after_reasoning,
        {
            "sql_generation": "sql_generation",
            "response_synthesis": "response_synthesis",
            END: END,
        },
    )

    # sql_generation → safety_validation (always)
    graph.add_edge("sql_generation", "safety_validation")

    # safety_validation → sql_execution or self_correction
    graph.add_conditional_edges(
        "safety_validation",
        route_after_safety,
        {
            "sql_execution": "sql_execution",
            "self_correction": "self_correction",
            "response_synthesis": "response_synthesis",
            END: END,
        },
    )

    # sql_execution → response_synthesis or self_correction
    graph.add_conditional_edges(
        "sql_execution",
        route_after_execution,
        {
            "response_synthesis": "response_synthesis",
            "self_correction": "self_correction",
            END: END,
        },
    )

    # self_correction → safety_validation (re-validate corrected SQL)
    graph.add_conditional_edges(
        "self_correction",
        route_after_correction,
        {"safety_validation": "safety_validation", END: END},
    )

    # response_synthesis → END (always)
    graph.add_edge("response_synthesis", END)

    # ── Compile ──────────────────────────────────────────────────────────────
    compiled = graph.compile()
    logger.info("LangGraph pipeline compiled successfully.")
    return compiled


# =============================================================================
# SINGLETON ACCESSOR
# =============================================================================

_pipeline = None


def get_pipeline():
    """
    Get the singleton compiled LangGraph pipeline.

    The pipeline is compiled once at startup and reused for all queries.
    It is thread-safe and async-safe.

    Returns:
        Compiled LangGraph Runnable
    """
    global _pipeline
    if _pipeline is None:
        logger.info("Compiling LangGraph pipeline...")
        _pipeline = build_pipeline()
    return _pipeline
