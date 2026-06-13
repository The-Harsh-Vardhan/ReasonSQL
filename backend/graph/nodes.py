"""
LangGraph Node Functions — ReasonSQL 2.0

Each function is a LangGraph node (agent) that reads PipelineState,
performs work, and returns a partial state update.

Node Lifecycle:
    schema_retrieval → reasoning → sql_generation → safety_validation
        → sql_execution → [self_correction] → response_synthesis

Why function-based nodes:
    - Simple to test independently
    - LangSmith traces each node invocation separately
    - Conditional edges route between nodes based on state
    - No class inheritance needed — functions are first-class citizens in LangGraph
"""

import json
import time
import logging
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage

from backend.db_connection import (
    get_schema_as_text,
    get_tables,
    execute_query_async,
)
from backend.retrieval import HybridSchemaRetriever, SchemaIndexer
from backend.llm import (
    get_llm_with_fallback,
    REASONING_PROMPT,
    SQL_GENERATION_PROMPT,
    SELF_CORRECTION_PROMPT,
    RESPONSE_SYNTHESIS_PROMPT,
    META_QUERY_PROMPT,
)
from backend.llm.output_schemas import (
    SQLGeneratorOutput,
    ResponseSynthesizerOutput,
    SelfCorrectionOutput,
    MetaQueryOutput,
)
from configs import (
    FORBIDDEN_KEYWORDS,
    DEFAULT_LIMIT,
    MAX_RETRIES,
    RAG_THRESHOLD_TABLES,
    VERBOSE,
)
from .state import PipelineState

logger = logging.getLogger("reasonsql.graph.nodes")


# =============================================================================
# MODULE-LEVEL SINGLETONS (initialized once at startup)
# =============================================================================
# These are lazy-initialized when the first query arrives to avoid
# loading heavy models (FAISS, CrossEncoder) at import time.

_schema_indexer: SchemaIndexer | None = None
_hybrid_retriever: HybridSchemaRetriever | None = None
_llm = None  # LangChain fallback chain


def _get_llm():
    """Get or initialize the LangChain LLM fallback chain."""
    global _llm
    if _llm is None:
        _llm = get_llm_with_fallback(temperature=0.1)
    return _llm


def _get_retriever(table_schemas: Dict[str, str]) -> HybridSchemaRetriever:
    """Get or rebuild the hybrid retriever when schema changes."""
    global _schema_indexer, _hybrid_retriever

    if _schema_indexer is None or set(table_schemas.keys()) != set(
        d.metadata["table"] for d in (_schema_indexer.documents or [])
    ):
        logger.info("Rebuilding FAISS index for %d tables...", len(table_schemas))
        _schema_indexer = SchemaIndexer()
        _schema_indexer.index_schema(table_schemas)
        _hybrid_retriever = HybridSchemaRetriever(_schema_indexer)

    return _hybrid_retriever


# =============================================================================
# HELPER: SAFE LLM INVOCATION WITH JSON PARSING
# =============================================================================

async def _invoke_llm_json(prompt_template, variables: Dict[str, Any]) -> Dict[str, Any]:
    """
    Invoke an LLM with a ChatPromptTemplate and parse the JSON response.

    Args:
        prompt_template: LangChain ChatPromptTemplate
        variables: Template variable values

    Returns:
        Parsed JSON dict from LLM response

    Raises:
        ValueError: If LLM response is not valid JSON
    """
    llm = _get_llm()
    chain = prompt_template | llm

    response = await chain.ainvoke(variables)
    content = response.content.strip()

    # Strip markdown code fences if present (```json ... ```)
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])
        content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        # Try to extract first JSON object from the response
        import re
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"LLM returned non-JSON response: {content[:200]}") from e


async def _invoke_llm_structured(
    prompt_template,
    variables: Dict[str, Any],
    output_schema,
    fallback_top_key: str,
) -> Dict[str, Any]:
    """
    Try LangChain structured output first; fall back to JSON parsing.

    Structured output uses the provider's function-calling / JSON-mode API.
    If the provider (e.g., Gemini via LiteLLM) doesn't support it cleanly,
    falls back to _invoke_llm_json transparently.

    Args:
        prompt_template: LangChain ChatPromptTemplate
        variables: Template variable values
        output_schema: Pydantic BaseModel class for structured output
        fallback_top_key: Top-level key to extract from JSON fallback response

    Returns:
        Dict of the schema's fields
    """
    llm = _get_llm()
    try:
        # Try structured output (provider function-calling / JSON schema)
        structured_chain = prompt_template | llm.with_structured_output(output_schema)
        result = await structured_chain.ainvoke(variables)
        logger.debug("[StructuredOutput] Success via %s", output_schema.__name__)
        return result.model_dump()
    except Exception as e:
        logger.debug(
            "[StructuredOutput] %s fallback to JSON (%s)",
            output_schema.__name__, str(e)[:80]
        )
        # Fall back to JSON parsing
        raw = await _invoke_llm_json(prompt_template, variables)
        return raw.get(fallback_top_key, {})


def _add_trace(state: PipelineState, agent: str, summary: str, detail: str = "") -> None:
    """Append an agent trace entry to the state's reasoning_trace."""
    trace = state.get("reasoning_trace", [])
    trace.append({"agent": agent, "summary": summary, "detail": detail})
    state["reasoning_trace"] = trace


# =============================================================================
# NODE 1: SCHEMA RETRIEVAL
# =============================================================================

async def schema_retrieval_node(state: PipelineState) -> PipelineState:
    """
    Retrieve relevant table schemas using hybrid RAG.

    For small schemas (≤ RAG_THRESHOLD_TABLES): Use full schema (no RAG needed).
    For large schemas (> RAG_THRESHOLD_TABLES): Hybrid BM25 + FAISS + CrossEncoder.

    This node sets:
        - full_table_schemas: All table schemas as text
        - retrieved_tables: Tables selected by RAG (or all if small schema)
        - schema_context: Formatted schema string for LLM prompts
        - retrieval_method: 'hybrid_rag' or 'full_schema'
    """
    logger.info("[SchemaRetrieval] Loading schema from database...")

    try:
        # Get schema as text strings (table_name → formatted description)
        table_schemas = get_schema_as_text()
        all_tables = list(table_schemas.keys())
        total_tables = len(all_tables)

        logger.info("[SchemaRetrieval] Found %d tables.", total_tables)

        if total_tables <= RAG_THRESHOLD_TABLES:
            # Small schema: use all tables (no RAG overhead)
            retrieved_tables = all_tables
            method = "full_schema"
            logger.info("[SchemaRetrieval] Small schema (%d tables) — using full schema.", total_tables)
        else:
            # Large schema: hybrid retrieval + cross-encoder reranking
            retriever = _get_retriever(table_schemas)
            retrieved_tables = retriever.retrieve(state.get("user_query", ""))
            method = "hybrid_rag"
            logger.info(
                "[SchemaRetrieval] RAG selected %d/%d tables: %s",
                len(retrieved_tables), total_tables, retrieved_tables,
            )

        # Build schema context string for LLM prompt
        schema_context = "\n".join(
            table_schemas[t] for t in retrieved_tables if t in table_schemas
        )

        _add_trace(
            state, "SchemaRetrieval",
            f"{method}: {len(retrieved_tables)}/{total_tables} tables",
            ", ".join(retrieved_tables),
        )

        return {
            **state,
            "full_table_schemas": table_schemas,
            "retrieved_tables": retrieved_tables,
            "schema_context": schema_context,
            "retrieval_method": method,
        }

    except Exception as e:
        logger.error("[SchemaRetrieval] Error: %s", e)
        _add_trace(state, "SchemaRetrieval", f"ERROR: {e}", "")
        return {**state, "pipeline_error": f"Schema retrieval failed: {e}"}


# =============================================================================
# NODE 2: REASONING & PLANNING (LLM)
# =============================================================================

async def reasoning_node(state: PipelineState) -> PipelineState:
    """
    Multi-agent reasoning: Intent analysis + clarification + decomposition + planning.

    Single LLM call that runs 4 logical agents in parallel (batched prompt).
    Sets intent, resolved_query, query_plan, assumptions, clarification_questions.
    """
    logger.info("[Reasoning] Analyzing query: %r", state.get("user_query"))

    # Format conversation history for context
    history = state.get("history", [])
    history_text = ""
    if history:
        history_text = "\n".join(
            f"- {msg['role'].upper()}: {msg['content']}"
            for msg in history[-5:]  # Last 5 turns
        )
    else:
        history_text = "(No conversation history)"

    try:
        result = await _invoke_llm_json(REASONING_PROMPT, {
            "user_query": state.get("user_query", ""),
            "schema_context": state.get("schema_context", ""),
            "history": history_text,
        })

        intent_data = result.get("intent_analyzer", {})
        clarify_data = result.get("clarification_agent", {})
        decomp_data = result.get("query_decomposer", {})
        plan_data = result.get("query_planner", {})

        intent = intent_data.get("intent", "DATA_QUERY")
        resolved_query = clarify_data.get("resolved_query", state.get("user_query", ""))
        assumptions = clarify_data.get("assumptions", [])
        clarification_questions = clarify_data.get("clarification_questions", [])
        query_plan = plan_data.get("plan_description", "")

        # For AMBIGUOUS intent — pre-fill final_answer with questions
        final_answer = ""
        if intent == "AMBIGUOUS" and clarification_questions:
            questions_text = "\n".join(f"- {q}" for q in clarification_questions)
            final_answer = (
                f"### ❓ Clarification Needed\n\n"
                f"{intent_data.get('reasoning', 'Ambiguous terms detected.')}\n\n"
                f"**Please clarify:**\n{questions_text}"
            )

        _add_trace(
            state, "IntentAnalyzer",
            f"Intent: {intent} ({intent_data.get('confidence', 0):.0%})",
            intent_data.get("reasoning", ""),
        )
        _add_trace(state, "ClarificationAgent", f"Resolved: {resolved_query}", str(assumptions))
        _add_trace(state, "QueryDecomposer", f"Complex: {decomp_data.get('is_complex', False)}", "")
        _add_trace(state, "QueryPlanner", f"Tables: {plan_data.get('relevant_tables', [])}", query_plan)

        return {
            **state,
            "intent": intent,
            "intent_confidence": intent_data.get("confidence", 0.0),
            "resolved_query": resolved_query,
            "assumptions": assumptions,
            "clarification_questions": clarification_questions,
            "is_complex": decomp_data.get("is_complex", False),
            "query_plan": query_plan,
            "final_answer": final_answer,
        }

    except Exception as e:
        logger.error("[Reasoning] LLM error: %s", e)
        _add_trace(state, "Reasoning", f"ERROR: {e}", "")
        return {**state, "pipeline_error": f"Reasoning failed: {e}", "intent": "DATA_QUERY"}


# =============================================================================
# NODE 3: SQL GENERATION (LLM)
# =============================================================================

async def sql_generation_node(state: PipelineState) -> PipelineState:
    """
    Generate SQL query from the query plan and schema context.

    Uses structured output (SQLGeneratorOutput) with JSON fallback.
    Enforces PostgreSQL syntax, double-quoting, LIMIT, and no SELECT *.
    """
    logger.info("[SQLGeneration] Generating SQL for: %r", state.get("resolved_query"))

    try:
        sql_data = await _invoke_llm_structured(
            SQL_GENERATION_PROMPT,
            {
                "resolved_query": state.get("resolved_query", state.get("user_query", "")),
                "schema_context": state.get("schema_context", ""),
                "query_plan": state.get("query_plan", ""),
                "default_limit": DEFAULT_LIMIT,
            },
            SQLGeneratorOutput,
            "sql_generator",
        )

        generated_sql = sql_data.get("sql", "").strip()

        _add_trace(
            state, "SQLGenerator",
            f"Generated SQL ({len(generated_sql)} chars)",
            generated_sql[:200],
        )

        return {**state, "generated_sql": generated_sql, "corrected_sql": ""}

    except Exception as e:
        logger.error("[SQLGeneration] LLM error: %s", e)
        _add_trace(state, "SQLGenerator", f"ERROR: {e}", "")
        return {**state, "pipeline_error": f"SQL generation failed: {e}", "generated_sql": ""}


# =============================================================================
# NODE 4: SAFETY VALIDATION (Deterministic)
# =============================================================================

def safety_validation_node(state: PipelineState) -> PipelineState:
    """
    Rule-based SQL safety validation.

    Checks:
    1. No forbidden keywords (INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE)
    2. LIMIT clause present (auto-adds if missing)
    3. No SELECT *

    This is deterministic — no LLM call needed.
    Being the last line of defense, it is intentionally strict.
    """
    # Use corrected SQL if available (from self-correction), else generated SQL
    sql = (state.get("corrected_sql") or state.get("generated_sql", "")).strip()

    if not sql:
        return {
            **state,
            "safety_approved": False,
            "safety_violations": ["No SQL to validate"],
        }

    violations = []
    sql_upper = sql.upper()

    # Check forbidden keywords
    for kw in FORBIDDEN_KEYWORDS:
        if kw in sql_upper:
            violations.append(f"Forbidden keyword: {kw}")

    # Auto-add LIMIT if missing (graceful fix rather than rejection)
    if "LIMIT" not in sql_upper:
        sql = sql.rstrip(";").strip() + f" LIMIT {DEFAULT_LIMIT};"
        if state.get("corrected_sql"):
            state = {**state, "corrected_sql": sql}
        else:
            state = {**state, "generated_sql": sql}
        _add_trace(state, "SafetyValidator", f"Auto-added LIMIT {DEFAULT_LIMIT}", sql[:100])

    # Check for SELECT *
    if "SELECT *" in sql_upper or "SELECT\n*" in sql_upper:
        violations.append("SELECT * is forbidden — specify columns explicitly")

    approved = len(violations) == 0
    status = "✓ APPROVED" if approved else f"✗ REJECTED: {violations}"

    _add_trace(state, "SafetyValidator", status, sql[:150])

    logger.info("[SafetyValidator] %s", status)

    return {**state, "safety_approved": approved, "safety_violations": violations}


# =============================================================================
# NODE 5: SQL EXECUTION (Deterministic, Async)
# =============================================================================

async def sql_execution_node(state: PipelineState) -> PipelineState:
    """
    Execute the safety-approved SQL via SQLAlchemy async session.

    Captures results, row count, and execution time.
    On error, stores the error message for self-correction routing.
    """
    sql = (state.get("corrected_sql") or state.get("generated_sql", "")).strip()

    logger.info("[SQLExecutor] Executing: %s", sql[:100])

    try:
        start = time.time()
        results = await execute_query_async(sql)
        elapsed_ms = (time.time() - start) * 1000

        row_count = len(results)
        logger.info("[SQLExecutor] Success: %d rows in %.0fms", row_count, elapsed_ms)

        _add_trace(
            state, "SQLExecutor",
            f"✓ {row_count} rows in {elapsed_ms:.0f}ms",
            f"SQL: {sql[:100]}",
        )

        return {
            **state,
            "execution_result": results,
            "execution_error": "",
            "row_count": row_count,
            "execution_time_ms": elapsed_ms,
        }

    except Exception as e:
        error_msg = str(e)
        logger.error("[SQLExecutor] Error: %s", error_msg)

        _add_trace(state, "SQLExecutor", f"✗ Error: {error_msg[:100]}", sql[:100])

        return {
            **state,
            "execution_result": None,
            "execution_error": error_msg,
            "row_count": 0,
        }


# =============================================================================
# NODE 6: SELF-CORRECTION (LLM — Conditional)
# =============================================================================

async def self_correction_node(state: PipelineState) -> PipelineState:
    """
    Fix a failed SQL query using LLM analysis with structured output.

    Only invoked when sql_execution fails or safety_validation rejects.
    Limited by max_retries to prevent infinite loops.
    """
    retry_count = state.get("retry_count", 0) + 1
    logger.info("[SelfCorrection] Attempt %d/%d", retry_count, state.get("max_retries", MAX_RETRIES))

    failed_sql = state.get("corrected_sql") or state.get("generated_sql", "")
    error = state.get("execution_error") or "; ".join(state.get("safety_violations", []))

    try:
        correction_data = await _invoke_llm_structured(
            SELF_CORRECTION_PROMPT,
            {
                "user_query": state.get("user_query", ""),
                "schema_context": state.get("schema_context", ""),
                "failed_sql": failed_sql,
                "error_message": error,
            },
            SelfCorrectionOutput,
            "self_correction",
        )

        corrected_sql = correction_data.get("corrected_sql", "").strip()
        root_cause = correction_data.get("root_cause", "Unknown")

        logger.info("[SelfCorrection] Root cause: %s", root_cause)
        logger.info("[SelfCorrection] Corrected SQL: %s", corrected_sql[:100])

        _add_trace(
            state, "SelfCorrectionAgent",
            f"Attempt {retry_count}: {root_cause}",
            corrected_sql[:200],
        )

        return {
            **state,
            "corrected_sql": corrected_sql,
            "correction_root_cause": root_cause,
            "retry_count": retry_count,
            "execution_error": "",  # Clear error for retry
            "safety_violations": [],
        }

    except Exception as e:
        logger.error("[SelfCorrection] LLM error: %s", e)
        _add_trace(state, "SelfCorrectionAgent", f"ERROR: {e}", "")
        return {**state, "retry_count": retry_count, "pipeline_error": f"Self-correction failed: {e}"}


# =============================================================================
# NODE 7: RESPONSE SYNTHESIS (LLM)
# =============================================================================

async def response_synthesis_node(state: PipelineState) -> PipelineState:
    """
    Synthesize a human-readable answer from query results.

    For META_QUERY: Uses META_QUERY_PROMPT (schema explanation)
    For DATA_QUERY: Uses RESPONSE_SYNTHESIS_PROMPT (data answer)
    For AMBIGUOUS: Returns pre-filled clarification questions (no LLM call)
    """
    intent = state.get("intent", "DATA_QUERY")
    logger.info("[ResponseSynthesis] Synthesizing %s response...", intent)

    # AMBIGUOUS: answer already set by reasoning_node
    if intent == "AMBIGUOUS":
        _add_trace(state, "ResponseSynthesizer", "Clarification questions returned (no LLM call)", "")
        return state

    # META_QUERY: explain schema structure
    if intent == "META_QUERY":
        try:
            result = await _invoke_llm_json(META_QUERY_PROMPT, {
                "user_query": state.get("user_query", ""),
                "schema_context": state.get("schema_context", ""),
            })
            meta_data = result.get("meta_response", {})
            answer = meta_data.get("answer", "I could not find the requested schema information.")
            _add_trace(state, "ResponseSynthesizer", "META_QUERY: schema explanation", answer[:100])
            return {**state, "final_answer": answer, "key_insights": []}
        except Exception as e:
            return {**state, "final_answer": f"Schema query failed: {e}"}

    # DATA_QUERY: synthesize data results into readable answer
    results = state.get("execution_result") or []
    row_count = state.get("row_count", 0)

    # Build results preview (first 5 rows as JSON)
    results_preview = json.dumps(results[:5], default=str, indent=2) if results else "[]"

    # Check for execution failure
    if state.get("execution_error"):
        answer = (
            f"❌ Unable to execute the query.\n\n"
            f"**Error:** {state['execution_error']}\n\n"
            f"The system attempted self-correction but could not resolve the issue. "
            f"Please rephrase your question."
        )
        _add_trace(state, "ResponseSynthesizer", "Execution error — returning failure message", "")
        return {**state, "final_answer": answer, "key_insights": []}

    try:
        synth_data = await _invoke_llm_structured(
            RESPONSE_SYNTHESIS_PROMPT,
            {
                "user_query": state.get("user_query", ""),
                "sql_used": state.get("corrected_sql") or state.get("generated_sql", ""),
                "row_count": row_count,
                "results_preview": results_preview,
            },
            ResponseSynthesizerOutput,
            "response_synthesizer",
        )

        answer = synth_data.get("answer", "Query completed successfully.")
        insights = synth_data.get("key_insights", [])

        _add_trace(state, "ResponseSynthesizer", f"Answer synthesized ({row_count} rows)", answer[:100])

        return {**state, "final_answer": answer, "key_insights": insights}

    except Exception as e:
        logger.error("[ResponseSynthesis] LLM error: %s", e)
        # Fallback: return raw results summary
        fallback = f"Query returned {row_count} rows. First result: {results[:1]}"
        return {**state, "final_answer": fallback, "key_insights": []}
