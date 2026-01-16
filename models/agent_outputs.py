"""
Structured output models for each agent in the pipeline.

DESIGN PRINCIPLE:
================
Every agent returns a STRUCTURED output with:
- status: "ok" | "ambiguous" | "error" | "retry" | "blocked"
- reason: Why this status was chosen
- data: Agent-specific structured data

This enables deterministic control flow in the orchestrator.
The orchestrator inspects `status` to decide what to do next.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from enum import Enum


# ============================================================
# BASE OUTPUT MODEL
# ============================================================

class AgentStatus(str, Enum):
    """Standard status codes for agent outputs."""
    OK = "ok"                  # Success - proceed to next step
    AMBIGUOUS = "ambiguous"    # Needs clarification - pause pipeline
    ERROR = "error"            # Failed - may trigger retry
    RETRY = "retry"            # Self-correction needed
    BLOCKED = "blocked"        # Safety validation failed - hard stop


class BaseAgentOutput(BaseModel):
    """Base class for all agent outputs."""
    status: AgentStatus = Field(description="Agent execution status")
    reason: str = Field(description="Explanation for the status")
    agent_name: str = Field(description="Which agent produced this output")
    
    class Config:
        use_enum_values = True


# ============================================================
# 1. INTENT ANALYZER OUTPUT
# ============================================================

class IntentType(str, Enum):
    DATA_QUERY = "DATA_QUERY"      # User wants data
    META_QUERY = "META_QUERY"      # User wants schema info
    AMBIGUOUS = "AMBIGUOUS"        # Needs clarification


class IntentAnalyzerOutput(BaseAgentOutput):
    """
    Output from IntentAnalyzerAgent.
    
    Flow Decision:
    - If intent == AMBIGUOUS: route to ClarificationAgent
    - If intent == META_QUERY: route to SchemaExplorer → ResponseSynthesizer → END
    - If intent == DATA_QUERY: continue normal flow
    """
    agent_name: str = Field(default="IntentAnalyzer")
    intent: IntentType = Field(description="Classified intent type")
    confidence: float = Field(ge=0.0, le=1.0, description="Classification confidence")
    relevant_tables: List[str] = Field(default_factory=list, description="Tables needed")
    relevant_columns: List[str] = Field(default_factory=list, description="Columns needed")
    is_complex: bool = Field(default=False, description="Needs QueryDecomposer?")
    needs_data_context: bool = Field(default=False, description="Needs DataExplorer?")
    ambiguous_terms: List[str] = Field(default_factory=list, description="Terms needing clarification")
    
    @classmethod
    def from_text(cls, text: str, raw_intent: str) -> "IntentAnalyzerOutput":
        """Parse from agent text output (fallback)."""
        intent = IntentType.DATA_QUERY
        if "META_QUERY" in text.upper():
            intent = IntentType.META_QUERY
        elif "AMBIGUOUS" in text.upper():
            intent = IntentType.AMBIGUOUS
        
        status = AgentStatus.OK
        if intent == IntentType.AMBIGUOUS:
            status = AgentStatus.AMBIGUOUS
        
        return cls(
            status=status,
            reason=f"Intent classified as {intent.value}",
            intent=intent,
            confidence=0.8,
            relevant_tables=[],
            relevant_columns=[],
            is_complex="complex" in text.lower(),
            needs_data_context="recent" in text.lower() or "range" in text.lower()
        )


# ============================================================
# 2. CLARIFICATION AGENT OUTPUT
# ============================================================

class ClarificationOutput(BaseAgentOutput):
    """
    Output from ClarificationAgent.
    
    Flow Decision:
    - If status == OK: ambiguity resolved, continue flow
    - If status == AMBIGUOUS: still unclear, return to user
    """
    agent_name: str = Field(default="ClarificationAgent")
    resolved_terms: Dict[str, str] = Field(
        default_factory=dict, 
        description="Map of ambiguous term -> resolved value"
    )
    clarification_questions: List[str] = Field(
        default_factory=list,
        description="Questions to ask user (if status == AMBIGUOUS)"
    )
    assumptions_made: List[str] = Field(
        default_factory=list,
        description="Defaults assumed when clarification not possible"
    )
    refined_query: Optional[str] = Field(
        default=None,
        description="Query with ambiguity resolved"
    )


# ============================================================
# 3. SCHEMA EXPLORER OUTPUT
# ============================================================

class TableSchema(BaseModel):
    """Schema for a single table."""
    name: str
    columns: List[str]
    primary_key: Optional[str] = None
    foreign_keys: List[str] = Field(default_factory=list)
    row_count: Optional[int] = None


class SchemaExplorerOutput(BaseAgentOutput):
    """
    Output from SchemaExplorerAgent.
    
    Provides structured schema context for downstream agents.
    """
    agent_name: str = Field(default="SchemaExplorer")
    tables: List[TableSchema] = Field(default_factory=list)
    relationships: List[str] = Field(default_factory=list)
    relevant_tables_for_query: List[str] = Field(default_factory=list)
    schema_summary: str = Field(default="", description="Human-readable summary")


# ============================================================
# 4. QUERY DECOMPOSER OUTPUT
# ============================================================

class QueryStep(BaseModel):
    """A single step in a complex query decomposition."""
    step_number: int
    description: str
    operation: str = Field(description="CTE | SUBQUERY | JOIN | UNION | INTERSECT | EXCEPT")
    depends_on: List[int] = Field(default_factory=list, description="Previous step numbers")


class QueryDecomposerOutput(BaseAgentOutput):
    """
    Output from QueryDecomposerAgent.
    
    Breaks complex queries into executable steps.
    """
    agent_name: str = Field(default="QueryDecomposer")
    is_decomposed: bool = Field(default=False, description="Was decomposition needed?")
    steps: List[QueryStep] = Field(default_factory=list)
    recommended_approach: str = Field(
        default="",
        description="CTE | SUBQUERY | MULTIPLE_QUERIES | SIMPLE"
    )
    complexity_reason: str = Field(default="", description="Why decomposition was needed")


# ============================================================
# 5. DATA EXPLORER OUTPUT
# ============================================================

class ColumnStats(BaseModel):
    """Statistics for a column."""
    column_name: str
    min_value: Optional[str] = None
    max_value: Optional[str] = None
    sample_values: List[str] = Field(default_factory=list)
    null_count: Optional[int] = None


class DataExplorerOutput(BaseAgentOutput):
    """
    Output from DataExplorerAgent.
    
    Provides actual data context for query planning.
    """
    agent_name: str = Field(default="DataExplorer")
    explored_tables: List[str] = Field(default_factory=list)
    column_stats: List[ColumnStats] = Field(default_factory=list)
    date_ranges: Dict[str, str] = Field(
        default_factory=dict,
        description="Column -> 'min_date to max_date' mapping"
    )
    value_distributions: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Column -> sample distinct values"
    )
    insights: List[str] = Field(default_factory=list, description="Key observations")


# ============================================================
# 6. QUERY PLANNER OUTPUT
# ============================================================

class JoinPlan(BaseModel):
    """Planned table join."""
    table: str
    join_type: str = "INNER"
    on_condition: str


class FilterPlan(BaseModel):
    """Planned filter condition."""
    column: str
    operator: str
    value: Any


class QueryPlannerOutput(BaseAgentOutput):
    """
    Output from QueryPlannerAgent.
    
    Structured query plan that SQLGenerator will convert to SQL.
    """
    agent_name: str = Field(default="QueryPlanner")
    base_table: str = Field(description="Primary table")
    select_columns: List[str] = Field(description="Columns to select (no SELECT *)")
    joins: List[JoinPlan] = Field(default_factory=list)
    filters: List[FilterPlan] = Field(default_factory=list)
    group_by: List[str] = Field(default_factory=list)
    order_by: List[str] = Field(default_factory=list)
    limit: int = Field(default=100, ge=1, le=1000)
    has_aggregation: bool = Field(default=False)
    reasoning: str = Field(default="", description="Why this plan was chosen")


# ============================================================
# 7. SQL GENERATOR OUTPUT
# ============================================================

class SQLGeneratorOutput(BaseAgentOutput):
    """
    Output from SQLGeneratorAgent.
    
    Contains the generated SQL query.
    """
    agent_name: str = Field(default="SQLGenerator")
    sql: str = Field(description="The generated SQL query")
    uses_cte: bool = Field(default=False, description="Whether query uses WITH clause")
    table_count: int = Field(default=1, description="Number of tables involved")


# ============================================================
# 8. SAFETY VALIDATOR OUTPUT (GATE)
# ============================================================

class SafetyValidatorOutput(BaseAgentOutput):
    """
    Output from SafetyValidatorAgent.
    
    CRITICAL: This is a GATE. If status != OK, execution MUST stop.
    
    Flow Decision:
    - If status == OK (APPROVED): proceed to SQLExecutor
    - If status == BLOCKED (REJECTED): return to SelfCorrection or fail
    """
    agent_name: str = Field(default="SafetyValidator")
    decision: Literal["APPROVED", "REJECTED"] = Field(description="Gate decision")
    has_limit: bool = Field(default=False)
    has_select_star: bool = Field(default=False)
    is_read_only: bool = Field(default=True)
    forbidden_keywords_found: List[str] = Field(default_factory=list)
    violations: List[str] = Field(default_factory=list, description="What failed validation")
    suggested_fixes: List[str] = Field(default_factory=list)


# ============================================================
# 9. SQL EXECUTOR OUTPUT
# ============================================================

class SQLExecutorOutput(BaseAgentOutput):
    """
    Output from SQLExecutorAgent.
    
    Flow Decision:
    - If status == OK: proceed to ResultValidator
    - If status == ERROR or EMPTY: may trigger SelfCorrection (if retries remain)
    """
    agent_name: str = Field(default="SQLExecutor")
    sql_executed: str = Field(description="The SQL that was run")
    row_count: int = Field(default=0)
    column_names: List[str] = Field(default_factory=list)
    data: List[Dict[str, Any]] = Field(default_factory=list, description="Query results")
    execution_time_ms: float = Field(default=0.0)
    error_message: Optional[str] = Field(default=None)
    is_empty: bool = Field(default=False)


# ============================================================
# 10. SELF-CORRECTION OUTPUT
# ============================================================

class SelfCorrectionOutput(BaseAgentOutput):
    """
    Output from SelfCorrectionAgent.
    
    Analyzes what went wrong and proposes a fix.
    """
    agent_name: str = Field(default="SelfCorrection")
    original_error: str = Field(description="What failed")
    diagnosis: str = Field(description="Root cause analysis")
    correction_strategy: str = Field(description="How to fix it")
    revised_approach: str = Field(default="", description="New plan to try")
    should_retry: bool = Field(default=True, description="Should we try again?")
    skip_to_step: Optional[str] = Field(
        default=None,
        description="Which step to retry from: PLANNER | GENERATOR | EXPLORER"
    )


# ============================================================
# 11. RESULT VALIDATOR OUTPUT
# ============================================================

class ResultValidatorOutput(BaseAgentOutput):
    """
    Output from ResultValidatorAgent.
    
    Sanity-checks the query results.
    """
    agent_name: str = Field(default="ResultValidator")
    is_valid: bool = Field(default=True, description="Results pass sanity checks")
    anomalies_detected: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    matches_intent: bool = Field(default=True, description="Results match the question")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


# ============================================================
# 12. RESPONSE SYNTHESIZER OUTPUT
# ============================================================

class ResponseSynthesizerOutput(BaseAgentOutput):
    """
    Output from ResponseSynthesizerAgent.
    
    The final human-readable answer.
    """
    agent_name: str = Field(default="ResponseSynthesizer")
    answer: str = Field(description="Human-readable answer")
    explanation: str = Field(default="", description="How we got this answer")
    data_summary: str = Field(default="", description="Summary of the data")
    suggestions: List[str] = Field(default_factory=list, description="Follow-up suggestions")


# ============================================================
# PIPELINE STATE
# ============================================================

class PipelineState(BaseModel):
    """
    Complete state of the pipeline at any point.
    
    The orchestrator maintains this state and passes relevant
    parts to each agent. This enables full traceability.
    """
    user_query: str
    current_step: str = Field(default="START")
    
    # Agent outputs (filled as pipeline progresses)
    intent_output: Optional[IntentAnalyzerOutput] = None
    clarification_output: Optional[ClarificationOutput] = None
    schema_output: Optional[SchemaExplorerOutput] = None
    decomposer_output: Optional[QueryDecomposerOutput] = None
    data_explorer_output: Optional[DataExplorerOutput] = None
    planner_output: Optional[QueryPlannerOutput] = None
    generator_output: Optional[SQLGeneratorOutput] = None
    safety_output: Optional[SafetyValidatorOutput] = None
    executor_output: Optional[SQLExecutorOutput] = None
    correction_output: Optional[SelfCorrectionOutput] = None
    result_validator_output: Optional[ResultValidatorOutput] = None
    response_output: Optional[ResponseSynthesizerOutput] = None
    
    # Retry tracking
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)
    
    # Timing
    start_time_ms: Optional[float] = None
    end_time_ms: Optional[float] = None
    
    # Trace
    trace: List[Dict[str, Any]] = Field(default_factory=list)
    
    def add_trace(self, agent_name: str, action: str, decision: str, output_summary: str):
        """Add an entry to the reasoning trace."""
        self.trace.append({
            "step": len(self.trace) + 1,
            "agent": agent_name,
            "action": action,
            "decision": decision,
            "output_summary": output_summary[:200]
        })
    
    def can_retry(self) -> bool:
        """Check if retries are available."""
        return self.retry_count < self.max_retries
    
    def increment_retry(self):
        """Increment retry counter."""
        self.retry_count += 1
