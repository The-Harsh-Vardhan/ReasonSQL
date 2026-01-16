"""
Quota-Optimized Orchestrator for NL2SQL Pipeline.

OPTIMIZATION GOAL:
==================
Reduce LLM API calls from ~12 per query to ~4-6 while maintaining:
- Architectural clarity (12 agents still exist conceptually)
- Full reasoning transparency
- Deterministic control flow

AGENT CLASSIFICATION:
====================
┌─────────────────────────┬──────────────┬─────────────────────────────────────┐
│ Agent                   │ Type         │ LLM Call Participation              │
├─────────────────────────┼──────────────┼─────────────────────────────────────┤
│ IntentAnalyzer          │ LLM_REQUIRED │ Call 1: Query Understanding         │
│ ClarificationAgent      │ LLM_REQUIRED │ Call 1: Query Understanding         │
│ SchemaExplorer          │ NON_LLM      │ Database introspection only         │
│ QueryDecomposer         │ LLM_REQUIRED │ Call 2: Query Planning              │
│ DataExplorer            │ NON_LLM      │ Database sampling only              │
│ QueryPlanner            │ LLM_REQUIRED │ Call 2: Query Planning              │
│ SQLGenerator            │ LLM_REQUIRED │ Call 3: SQL Generation              │
│ SafetyValidator         │ NON_LLM      │ Rule-based validation               │
│ SQLExecutor             │ NON_LLM      │ Database execution only             │
│ SelfCorrection          │ LLM_REQUIRED │ Call 4: Correction (conditional)    │
│ ResultValidator         │ NON_LLM      │ Rule-based validation               │
│ ResponseSynthesizer     │ LLM_REQUIRED │ Call 5: Response Synthesis          │
└─────────────────────────┴──────────────┴─────────────────────────────────────┘

LLM CALL BUDGET:
===============
- Normal query (no corrections): 4 calls
- Query with self-correction:    5-6 calls
- Hard cap: 8 calls (configurable)

CONSOLIDATED CALLS:
==================
Call 1: QUERY_UNDERSTANDING
  - Intent classification (DATA_QUERY / META_QUERY / AMBIGUOUS)
  - Ambiguity detection and resolution
  - Complexity assessment
  - Relevant table/column identification

Call 2: QUERY_PLANNING (skipped for META_QUERY)
  - Query decomposition (if complex)
  - Join strategy
  - Filter conditions
  - Column selection

Call 3: SQL_GENERATION
  - Generate valid SQLite SQL
  - Apply safety constraints

Call 4: SELF_CORRECTION (conditional, on failure only)
  - Analyze error
  - Propose fix
  - Generate corrected SQL

Call 5: RESPONSE_SYNTHESIS
  - Generate human-readable answer
  - Explain approach
"""
import time
import json
import re
import sqlite3
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto

from config import (
    get_llm, DATABASE_PATH, VERBOSE, MAX_RETRIES, 
    DEFAULT_LIMIT, FORBIDDEN_KEYWORDS
)
from models.agent_outputs import (
    AgentStatus, PipelineState,
    IntentAnalyzerOutput, IntentType,
    ClarificationOutput,
    SchemaExplorerOutput, TableSchema,
    QueryDecomposerOutput,
    DataExplorerOutput,
    QueryPlannerOutput,
    SQLGeneratorOutput,
    SafetyValidatorOutput,
    SQLExecutorOutput,
    SelfCorrectionOutput,
    ResultValidatorOutput,
    ResponseSynthesizerOutput
)
from models import FinalResponse, ExecutionStatus, ReasoningTrace, AgentAction


# ============================================================
# LLM BUDGET TRACKING
# ============================================================

@dataclass
class LLMBudget:
    """
    Tracks LLM API call usage for quota management.
    
    Enforces hard cap on LLM calls per query to prevent
    runaway costs and rate limit issues.
    """
    max_calls: int = 8  # Hard cap (configurable)
    calls_made: int = 0
    call_log: List[Dict[str, Any]] = field(default_factory=list)
    
    def can_call(self) -> bool:
        """Check if we have budget remaining."""
        return self.calls_made < self.max_calls
    
    def remaining(self) -> int:
        """Get remaining call budget."""
        return self.max_calls - self.calls_made
    
    def record_call(self, stage: str, tokens_used: int = 0, success: bool = True):
        """Record an LLM call."""
        self.calls_made += 1
        self.call_log.append({
            "call_number": self.calls_made,
            "stage": stage,
            "tokens_used": tokens_used,
            "success": success,
            "timestamp": time.time()
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get budget usage summary."""
        return {
            "total_calls": self.calls_made,
            "max_calls": self.max_calls,
            "remaining": self.remaining(),
            "calls": self.call_log
        }


class BudgetExceededError(Exception):
    """Raised when LLM call budget is exceeded."""
    pass


# ============================================================
# LLM CALL STAGES (Consolidated)
# ============================================================

class LLMStage(Enum):
    """
    Consolidated LLM call stages.
    Each stage may serve multiple logical agents.
    """
    QUERY_UNDERSTANDING = "query_understanding"   # Intent + Clarification
    QUERY_PLANNING = "query_planning"             # Decomposition + Planning
    SQL_GENERATION = "sql_generation"             # SQL output
    SELF_CORRECTION = "self_correction"           # Error recovery
    RESPONSE_SYNTHESIS = "response_synthesis"     # Final answer


# ============================================================
# PIPELINE STEPS (State Machine)
# ============================================================

class Step:
    """Pipeline step identifiers."""
    START = "START"
    QUERY_UNDERSTANDING = "QUERY_UNDERSTANDING"  # Consolidated: Intent + Clarification
    SCHEMA_EXPLORATION = "SCHEMA_EXPLORATION"    # NON-LLM: Database introspection
    DATA_EXPLORATION = "DATA_EXPLORATION"        # NON-LLM: Data sampling
    QUERY_PLANNING = "QUERY_PLANNING"            # Consolidated: Decomposition + Planning
    SQL_GENERATION = "SQL_GENERATION"            # LLM: Generate SQL
    SAFETY_VALIDATION = "SAFETY_VALIDATION"      # NON-LLM: Rule-based check
    SQL_EXECUTION = "SQL_EXECUTION"              # NON-LLM: Execute query
    SELF_CORRECTION = "SELF_CORRECTION"          # LLM: Fix errors (conditional)
    RESULT_VALIDATION = "RESULT_VALIDATION"      # NON-LLM: Sanity checks
    RESPONSE_SYNTHESIS = "RESPONSE_SYNTHESIS"    # LLM: Generate answer
    END = "END"
    BLOCKED = "BLOCKED"


# ============================================================
# OPTIMIZED PIPELINE STATE
# ============================================================

@dataclass
class OptimizedPipelineState:
    """
    Pipeline state with budget tracking.
    """
    user_query: str
    current_step: str = Step.START
    
    # LLM Budget
    budget: LLMBudget = field(default_factory=LLMBudget)
    
    # Timing
    start_time_ms: float = 0
    end_time_ms: float = 0
    
    # Retry tracking
    retry_count: int = 0
    max_retries: int = 2  # Reduced from 3 to save quota
    
    # Agent outputs (populated as pipeline progresses)
    # Query Understanding (consolidated)
    intent: Optional[IntentType] = None
    intent_confidence: float = 0.0
    intent_reason: str = ""
    is_complex: bool = False
    needs_data_context: bool = False
    relevant_tables: List[str] = field(default_factory=list)
    relevant_columns: List[str] = field(default_factory=list)
    ambiguous_terms: List[str] = field(default_factory=list)
    resolved_terms: Dict[str, str] = field(default_factory=dict)
    assumptions_made: List[str] = field(default_factory=list)
    
    # Schema (NON-LLM)
    schema_context: str = ""
    tables: List[TableSchema] = field(default_factory=list)
    
    # Data samples (NON-LLM)
    data_samples: Dict[str, List] = field(default_factory=dict)
    
    # Query Planning (consolidated)
    query_plan: str = ""
    decomposition_steps: List[str] = field(default_factory=list)
    join_strategy: str = ""
    
    # SQL Generation
    generated_sql: str = ""
    
    # Safety (NON-LLM)
    safety_approved: bool = False
    safety_violations: List[str] = field(default_factory=list)
    
    # Execution (NON-LLM)
    execution_result: Optional[List] = None
    execution_error: str = ""
    row_count: int = 0
    
    # Result Validation (NON-LLM)
    result_valid: bool = True
    validation_warnings: List[str] = field(default_factory=list)
    
    # Response
    final_answer: str = ""
    
    # Trace
    trace: List[Dict] = field(default_factory=list)
    
    def add_trace(self, agent: str, action: str, summary: str, detail: str = ""):
        """Add entry to reasoning trace."""
        self.trace.append({
            "agent": agent,
            "action": action,
            "summary": summary,
            "detail": detail,
            "llm_calls_so_far": self.budget.calls_made
        })
    
    def can_retry(self) -> bool:
        """Check if retry is allowed."""
        return self.retry_count < self.max_retries and self.budget.can_call()


# ============================================================
# QUOTA-OPTIMIZED ORCHESTRATOR
# ============================================================

class QuotaOptimizedOrchestrator:
    """
    Orchestrator optimized for LLM API quota management.
    
    KEY OPTIMIZATIONS:
    1. Consolidated LLM calls (12 agents → 4-6 LLM calls)
    2. NON-LLM agents use database/rules only
    3. Explicit budget tracking and enforcement
    4. Reduced retry limit (3 → 2)
    
    CALL DISTRIBUTION:
    - Normal query:  4 calls (Understanding + Planning + SQL + Response)
    - Meta query:    2 calls (Understanding + Response)
    - With retries:  +1-2 calls per retry
    """
    
    def __init__(self, verbose: bool = VERBOSE, max_llm_calls: int = 8):
        self.verbose = verbose
        self.max_llm_calls = max_llm_calls
        self.llm = get_llm()
    
    def _log(self, message: str):
        """Log if verbose mode is on."""
        if self.verbose:
            print(f"[ORCHESTRATOR] {message}")
    
    # ============================================================
    # MAIN ENTRY POINT
    # ============================================================
    
    def process_query(self, user_query: str) -> FinalResponse:
        """
        Process a natural language query with quota optimization.
        
        Expected LLM calls:
        - Simple query: 4 (understanding + planning + sql + response)
        - Meta query: 2 (understanding + response)
        - With 1 retry: 5-6
        - With 2 retries: 6-7
        """
        state = OptimizedPipelineState(
            user_query=user_query,
            start_time_ms=time.time() * 1000,
            max_retries=min(2, MAX_RETRIES)  # Cap at 2 for quota
        )
        state.budget = LLMBudget(max_calls=self.max_llm_calls)
        
        self._log(f"{'='*60}")
        self._log(f"PROCESSING: {user_query}")
        self._log(f"LLM Budget: {self.max_llm_calls} calls max")
        self._log(f"{'='*60}")
        
        try:
            # Run state machine
            while state.current_step not in [Step.END, Step.BLOCKED]:
                state = self._execute_step(state)
            
        except BudgetExceededError as e:
            self._log(f"⚠️ BUDGET EXCEEDED: {e}")
            state.current_step = Step.BLOCKED
            state.final_answer = f"Query processing stopped: LLM call budget exceeded ({state.budget.calls_made}/{state.budget.max_calls} calls used)"
        
        # Finalize
        state.end_time_ms = time.time() * 1000
        total_time = state.end_time_ms - state.start_time_ms
        
        return self._build_response(state, total_time)
    
    # ============================================================
    # STATE MACHINE
    # ============================================================
    
    def _execute_step(self, state: OptimizedPipelineState) -> OptimizedPipelineState:
        """Execute current step and determine next step."""
        current = state.current_step
        
        # ----------------------------------------
        # START → QUERY_UNDERSTANDING
        # ----------------------------------------
        if current == Step.START:
            self._log("→ Starting pipeline")
            state.current_step = Step.QUERY_UNDERSTANDING
            return state
        
        # ----------------------------------------
        # QUERY_UNDERSTANDING (LLM Call 1)
        # Consolidates: IntentAnalyzer + ClarificationAgent
        # ----------------------------------------
        elif current == Step.QUERY_UNDERSTANDING:
            self._log("→ Step 1: Query Understanding [LLM CALL]")
            state = self._llm_query_understanding(state)
            
            # Route based on result
            if state.intent == IntentType.AMBIGUOUS and not state.resolved_terms and not state.assumptions_made:
                self._log("  → BLOCKED: Unresolved ambiguity")
                state.current_step = Step.BLOCKED
            else:
                state.current_step = Step.SCHEMA_EXPLORATION
            return state
        
        # ----------------------------------------
        # SCHEMA_EXPLORATION (NON-LLM)
        # Pure database introspection
        # ----------------------------------------
        elif current == Step.SCHEMA_EXPLORATION:
            self._log("→ Step 2: Schema Exploration [NO LLM]")
            state = self._nonllm_schema_exploration(state)
            
            # Route based on intent
            if state.intent == IntentType.META_QUERY:
                self._log("  → META_QUERY: Skip to Response")
                state.current_step = Step.RESPONSE_SYNTHESIS
            elif state.needs_data_context:
                self._log("  → Need data context")
                state.current_step = Step.DATA_EXPLORATION
            else:
                state.current_step = Step.QUERY_PLANNING
            return state
        
        # ----------------------------------------
        # DATA_EXPLORATION (NON-LLM)
        # Pure database sampling
        # ----------------------------------------
        elif current == Step.DATA_EXPLORATION:
            self._log("→ Step 3: Data Exploration [NO LLM]")
            state = self._nonllm_data_exploration(state)
            state.current_step = Step.QUERY_PLANNING
            return state
        
        # ----------------------------------------
        # QUERY_PLANNING (LLM Call 2)
        # Consolidates: QueryDecomposer + QueryPlanner
        # ----------------------------------------
        elif current == Step.QUERY_PLANNING:
            self._log("→ Step 4: Query Planning [LLM CALL]")
            state = self._llm_query_planning(state)
            state.current_step = Step.SQL_GENERATION
            return state
        
        # ----------------------------------------
        # SQL_GENERATION (LLM Call 3)
        # ----------------------------------------
        elif current == Step.SQL_GENERATION:
            self._log("→ Step 5: SQL Generation [LLM CALL]")
            state = self._llm_sql_generation(state)
            state.current_step = Step.SAFETY_VALIDATION
            return state
        
        # ----------------------------------------
        # SAFETY_VALIDATION (NON-LLM)
        # Rule-based validation
        # ----------------------------------------
        elif current == Step.SAFETY_VALIDATION:
            self._log("→ Step 6: Safety Validation [NO LLM]")
            state = self._nonllm_safety_validation(state)
            
            if not state.safety_approved:
                self._log(f"  → BLOCKED: Safety violations: {state.safety_violations}")
                state.current_step = Step.BLOCKED
            else:
                state.current_step = Step.SQL_EXECUTION
            return state
        
        # ----------------------------------------
        # SQL_EXECUTION (NON-LLM)
        # ----------------------------------------
        elif current == Step.SQL_EXECUTION:
            self._log("→ Step 7: SQL Execution [NO LLM]")
            state = self._nonllm_sql_execution(state)
            
            if state.execution_error:
                self._log(f"  → Execution error: {state.execution_error}")
                if state.can_retry():
                    state.current_step = Step.SELF_CORRECTION
                else:
                    self._log("  → No retries remaining")
                    state.current_step = Step.RESPONSE_SYNTHESIS
            else:
                state.current_step = Step.RESULT_VALIDATION
            return state
        
        # ----------------------------------------
        # SELF_CORRECTION (LLM Call 4 - Conditional)
        # Only called on failure
        # ----------------------------------------
        elif current == Step.SELF_CORRECTION:
            self._log(f"→ Step 8: Self-Correction [LLM CALL] (retry {state.retry_count + 1})")
            state.retry_count += 1
            state = self._llm_self_correction(state)
            
            # Go back to safety validation with new SQL
            state.current_step = Step.SAFETY_VALIDATION
            return state
        
        # ----------------------------------------
        # RESULT_VALIDATION (NON-LLM)
        # ----------------------------------------
        elif current == Step.RESULT_VALIDATION:
            self._log("→ Step 9: Result Validation [NO LLM]")
            state = self._nonllm_result_validation(state)
            state.current_step = Step.RESPONSE_SYNTHESIS
            return state
        
        # ----------------------------------------
        # RESPONSE_SYNTHESIS (LLM Call 5)
        # ----------------------------------------
        elif current == Step.RESPONSE_SYNTHESIS:
            self._log("→ Step 10: Response Synthesis [LLM CALL]")
            state = self._llm_response_synthesis(state)
            state.current_step = Step.END
            return state
        
        return state
    
    # ============================================================
    # LLM CALLS (Consolidated)
    # ============================================================
    
    def _call_llm(self, stage: LLMStage, prompt: str, state: OptimizedPipelineState) -> str:
        """
        Centralized LLM call with budget enforcement and rate limit handling.
        
        All LLM calls go through this method to ensure:
        1. Budget is checked before calling
        2. Rate limits are handled with exponential backoff
        3. Calls are logged
        4. Errors are handled consistently
        """
        if not state.budget.can_call():
            raise BudgetExceededError(
                f"LLM call budget exceeded. Used: {state.budget.calls_made}/{state.budget.max_calls}"
            )
        
        self._log(f"    [LLM] Calling for stage: {stage.value} (call #{state.budget.calls_made + 1})")
        
        max_retries = 3
        base_delay = 5  # seconds
        last_error: Optional[Exception] = None
        
        for attempt in range(max_retries):
            try:
                # Use CrewAI's LLM interface
                response = self.llm.call([{"role": "user", "content": prompt}])
                
                # Extract text from response
                if hasattr(response, 'content'):
                    result = response.content
                elif isinstance(response, str):
                    result = response
                else:
                    result = str(response)
                
                state.budget.record_call(stage.value, success=True)
                return result
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check for retryable errors (429 rate limit, 503 overloaded)
                is_retryable = (
                    "429" in str(e) or 
                    "503" in str(e) or
                    "rate" in error_str or 
                    "quota" in error_str or
                    "overload" in error_str or
                    "unavailable" in error_str
                )
                
                if is_retryable and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    self._log(f"    [LLM] Retryable error. Waiting {delay}s before retry {attempt + 2}/{max_retries}")
                    time.sleep(delay)
                    continue
                
                # For non-retryable errors or final attempt, fail
                state.budget.record_call(stage.value, success=False)
                self._log(f"    [LLM] Error: {e}")
                raise
        
        # All retries exhausted
        state.budget.record_call(stage.value, success=False)
        self._log(f"    [LLM] All retries exhausted")
        raise last_error if last_error else Exception("LLM call failed after all retries")
    
    def _llm_query_understanding(self, state: OptimizedPipelineState) -> OptimizedPipelineState:
        """
        LLM Call 1: Query Understanding
        
        Consolidates:
        - IntentAnalyzer: Classify query type
        - ClarificationAgent: Detect and resolve ambiguity
        
        Single LLM call replaces 2 agent calls.
        """
        prompt = f"""Analyze this natural language query for a SQL database.

USER QUERY: "{state.user_query}"

Provide a JSON response with:
{{
    "intent": "DATA_QUERY" | "META_QUERY" | "AMBIGUOUS",
    "intent_reason": "Brief explanation of classification",
    "confidence": 0.0-1.0,
    "is_complex": true/false (needs JOINs, CTEs, subqueries, or set operations),
    "needs_data_context": true/false (references 'recent', 'top', date ranges, etc.),
    "relevant_tables": ["table1", "table2"],
    "relevant_columns": ["col1", "col2"],
    "ambiguous_terms": ["term1", "term2"] (if any),
    "resolved_terms": {{"term": "resolution"}} (provide defaults for ambiguous terms),
    "assumptions_made": ["assumption1"] (what you assumed to resolve ambiguity)
}}

Classification rules:
- DATA_QUERY: Asks for data from the database (counts, lists, aggregations)
- META_QUERY: Asks about database structure (what tables exist, column names)
- AMBIGUOUS: Cannot determine what user wants without clarification

For ambiguous terms like "recent", "top", "best", provide sensible defaults:
- "recent" → last 30 days
- "top" → highest by relevant metric
- "best" → top 10 by revenue/count

Respond with ONLY the JSON object."""

        response = self._call_llm(LLMStage.QUERY_UNDERSTANDING, prompt, state)
        
        # Parse response
        data = self._parse_json(response)
        
        # Map to state
        intent_str = data.get("intent", "DATA_QUERY").upper()
        if intent_str == "META_QUERY":
            state.intent = IntentType.META_QUERY
        elif intent_str == "AMBIGUOUS":
            state.intent = IntentType.AMBIGUOUS
        else:
            state.intent = IntentType.DATA_QUERY
        
        state.intent_confidence = data.get("confidence", 0.8)
        state.intent_reason = data.get("intent_reason", "")
        state.is_complex = data.get("is_complex", False)
        state.needs_data_context = data.get("needs_data_context", False)
        state.relevant_tables = data.get("relevant_tables", [])
        state.relevant_columns = data.get("relevant_columns", [])
        state.ambiguous_terms = data.get("ambiguous_terms", [])
        state.resolved_terms = data.get("resolved_terms", {})
        state.assumptions_made = data.get("assumptions_made", [])
        
        state.add_trace(
            "IntentAnalyzer + ClarificationAgent",
            "Classified query and resolved ambiguity",
            f"Intent: {state.intent}, Complex: {state.is_complex}",
            f"Assumptions: {state.assumptions_made}"
        )
        
        return state
    
    def _llm_query_planning(self, state: OptimizedPipelineState) -> OptimizedPipelineState:
        """
        LLM Call 2: Query Planning
        
        Consolidates:
        - QueryDecomposer: Break down complex queries
        - QueryPlanner: Design query structure
        
        Single LLM call replaces 2 agent calls.
        """
        # Build context
        context_parts = [
            f"USER QUERY: \"{state.user_query}\"",
            f"\nQUERY CONTEXT:",
            f"- Intent: {state.intent}",
            f"- Is Complex: {state.is_complex}",
            f"- Relevant Tables: {state.relevant_tables}",
        ]
        
        if state.assumptions_made:
            context_parts.append(f"- Assumptions: {state.assumptions_made}")
        
        if state.resolved_terms:
            context_parts.append(f"- Resolved Terms: {state.resolved_terms}")
        
        context_parts.append(f"\nDATABASE SCHEMA:\n{state.schema_context}")
        
        if state.data_samples:
            context_parts.append(f"\nDATA SAMPLES:\n{json.dumps(state.data_samples, indent=2)}")
        
        prompt = "\n".join(context_parts) + """

Design a query plan. Provide a JSON response:
{
    "decomposition_steps": ["step1", "step2"] (if complex, else empty),
    "join_strategy": "Description of JOINs needed",
    "columns_to_select": ["col1", "col2"] (NEVER use SELECT *),
    "filters": ["condition1", "condition2"],
    "aggregations": ["COUNT", "SUM", etc.] (if needed),
    "order_by": "column ASC/DESC" (if needed),
    "limit": 100 (ALWAYS include a LIMIT),
    "query_plan": "Step-by-step description of how to build the query"
}

SAFETY RULES:
1. NEVER use SELECT * - always list specific columns
2. ALWAYS include a LIMIT clause
3. Use appropriate JOINs based on foreign keys
4. Order results meaningfully

Respond with ONLY the JSON object."""

        response = self._call_llm(LLMStage.QUERY_PLANNING, prompt, state)
        data = self._parse_json(response)
        
        state.decomposition_steps = data.get("decomposition_steps", [])
        state.join_strategy = data.get("join_strategy", "")
        state.query_plan = data.get("query_plan", response)
        
        state.add_trace(
            "QueryDecomposer + QueryPlanner",
            "Designed query plan",
            f"Steps: {len(state.decomposition_steps)}, Join: {state.join_strategy[:50]}",
            state.query_plan[:200]
        )
        
        return state
    
    def _llm_sql_generation(self, state: OptimizedPipelineState) -> OptimizedPipelineState:
        """
        LLM Call 3: SQL Generation
        
        Generates valid SQLite SQL from the query plan.
        """
        prompt = f"""Generate a SQLite SQL query based on this plan.

USER QUERY: "{state.user_query}"

QUERY PLAN:
{state.query_plan}

DATABASE SCHEMA:
{state.schema_context}

RULES:
1. Output ONLY the SQL query, no explanations
2. Use proper SQLite syntax
3. Include a LIMIT clause
4. Select specific columns (no SELECT *)
5. Use proper JOINs with ON clauses
6. Handle NULL values appropriately

SQL:"""

        response = self._call_llm(LLMStage.SQL_GENERATION, prompt, state)
        
        # Extract SQL from response
        sql = self._extract_sql(response)
        state.generated_sql = sql
        
        state.add_trace(
            "SQLGenerator",
            "Generated SQL query",
            f"SQL: {sql[:100]}...",
            sql
        )
        
        return state
    
    def _llm_self_correction(self, state: OptimizedPipelineState) -> OptimizedPipelineState:
        """
        LLM Call 4: Self-Correction (Conditional)
        
        Only called when execution fails. Analyzes error and generates fix.
        """
        prompt = f"""Fix this SQL query that failed to execute.

ORIGINAL QUERY: "{state.user_query}"

FAILED SQL:
{state.generated_sql}

ERROR:
{state.execution_error}

DATABASE SCHEMA:
{state.schema_context}

Analyze the error and provide:
1. What went wrong
2. A corrected SQL query

Output ONLY the corrected SQL query, no explanations.

CORRECTED SQL:"""

        response = self._call_llm(LLMStage.SELF_CORRECTION, prompt, state)
        
        sql = self._extract_sql(response)
        state.generated_sql = sql
        state.execution_error = ""  # Clear for retry
        
        state.add_trace(
            "SelfCorrection",
            f"Corrected SQL (attempt {state.retry_count})",
            f"New SQL: {sql[:100]}...",
            sql
        )
        
        return state
    
    def _llm_response_synthesis(self, state: OptimizedPipelineState) -> OptimizedPipelineState:
        """
        LLM Call 5: Response Synthesis
        
        Generates human-readable answer from results.
        """
        # Handle META_QUERY
        if state.intent == IntentType.META_QUERY:
            prompt = f"""Answer this database schema question.

USER QUESTION: "{state.user_query}"

DATABASE SCHEMA:
{state.schema_context}

Provide a clear, helpful answer about the database structure.
Be concise but complete."""

        # Handle empty/error results
        elif state.execution_error or state.execution_result is None:
            prompt = f"""The query could not be completed successfully.

USER QUESTION: "{state.user_query}"
ERROR: {state.execution_error or "Query execution failed"}
SQL ATTEMPTED: {state.generated_sql}

Provide a helpful response explaining what happened and suggesting alternatives if possible."""

        # Normal response
        else:
            result_preview = str(state.execution_result[:10]) if state.execution_result else "No results"
            prompt = f"""Generate a natural language answer to this question.

USER QUESTION: "{state.user_query}"

SQL EXECUTED:
{state.generated_sql}

RESULTS ({state.row_count} rows):
{result_preview}

{'[Results truncated for display]' if state.row_count > 10 else ''}

Provide a clear, conversational answer that:
1. Directly answers the question
2. Mentions key numbers/facts from the results
3. Is concise (2-3 sentences for simple queries)

Do not include the SQL in your answer."""

        response = self._call_llm(LLMStage.RESPONSE_SYNTHESIS, prompt, state)
        state.final_answer = response.strip()
        
        state.add_trace(
            "ResponseSynthesizer",
            "Generated response",
            state.final_answer[:100],
            state.final_answer
        )
        
        return state
    
    # ============================================================
    # NON-LLM OPERATIONS (Database/Rules Only)
    # ============================================================
    
    def _nonllm_schema_exploration(self, state: OptimizedPipelineState) -> OptimizedPipelineState:
        """
        NON-LLM: Schema Exploration
        
        Pure database introspection - no LLM needed.
        """
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            
            schema_parts = [f"Database has {len(tables)} tables:\n"]
            
            for table in tables:
                # Get columns
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                
                # Get foreign keys
                cursor.execute(f"PRAGMA foreign_key_list({table})")
                fks = cursor.fetchall()
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cursor.fetchone()[0]
                
                col_info = [f"{c[1]} ({c[2]})" for c in columns]
                schema_parts.append(f"\n{table} ({row_count} rows):")
                schema_parts.append(f"  Columns: {', '.join(col_info)}")
                
                if fks:
                    fk_info = [f"{fk[3]} -> {fk[2]}.{fk[4]}" for fk in fks]
                    schema_parts.append(f"  FKs: {', '.join(fk_info)}")
                
                # Store table schema
                state.tables.append(TableSchema(
                    name=table,
                    columns=[c[1] for c in columns],
                    primary_key=next((c[1] for c in columns if c[5]), None),
                    row_count=row_count
                ))
            
            conn.close()
            state.schema_context = "\n".join(schema_parts)
            
        except Exception as e:
            state.schema_context = f"Error exploring schema: {e}"
        
        state.add_trace(
            "SchemaExplorer",
            "Explored database schema [NO LLM]",
            f"Found {len(state.tables)} tables",
            state.schema_context[:200]
        )
        
        return state
    
    def _nonllm_data_exploration(self, state: OptimizedPipelineState) -> OptimizedPipelineState:
        """
        NON-LLM: Data Exploration
        
        Sample data from relevant tables - no LLM needed.
        """
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            for table in state.relevant_tables[:3]:  # Limit to 3 tables
                try:
                    cursor.execute(f"SELECT * FROM {table} LIMIT 5")
                    state.data_samples[table] = cursor.fetchall()
                except:
                    pass
            
            conn.close()
            
        except Exception as e:
            self._log(f"Data exploration error: {e}")
        
        state.add_trace(
            "DataExplorer",
            "Sampled data [NO LLM]",
            f"Sampled {len(state.data_samples)} tables",
            str(list(state.data_samples.keys()))
        )
        
        return state
    
    def _nonllm_safety_validation(self, state: OptimizedPipelineState) -> OptimizedPipelineState:
        """
        NON-LLM: Safety Validation
        
        Rule-based SQL safety check - no LLM needed.
        """
        sql = state.generated_sql.upper()
        violations = []
        
        # Check forbidden keywords
        for keyword in FORBIDDEN_KEYWORDS:
            if keyword in sql:
                violations.append(f"Forbidden keyword: {keyword}")
        
        # Check for SELECT *
        if "SELECT *" in sql or "SELECT  *" in sql:
            violations.append("SELECT * not allowed - must specify columns")
        
        # Check for LIMIT
        if "LIMIT" not in sql:
            violations.append("LIMIT clause required")
        
        # Check it starts with SELECT
        sql_stripped = state.generated_sql.strip().upper()
        if not sql_stripped.startswith("SELECT"):
            violations.append("Only SELECT queries allowed")
        
        state.safety_violations = violations
        state.safety_approved = len(violations) == 0
        
        state.add_trace(
            "SafetyValidator",
            "Validated SQL safety [NO LLM]",
            "APPROVED" if state.safety_approved else f"REJECTED: {violations}",
            state.generated_sql
        )
        
        return state
    
    def _nonllm_sql_execution(self, state: OptimizedPipelineState) -> OptimizedPipelineState:
        """
        NON-LLM: SQL Execution
        
        Execute query against database - no LLM needed.
        """
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            cursor.execute(state.generated_sql)
            results = cursor.fetchall()
            
            state.execution_result = results
            state.row_count = len(results)
            state.execution_error = ""
            
            conn.close()
            
        except Exception as e:
            state.execution_error = str(e)
            state.execution_result = None
            state.row_count = 0
        
        state.add_trace(
            "SQLExecutor",
            "Executed SQL [NO LLM]",
            f"Rows: {state.row_count}" if not state.execution_error else f"Error: {state.execution_error[:50]}",
            state.generated_sql
        )
        
        return state
    
    def _nonllm_result_validation(self, state: OptimizedPipelineState) -> OptimizedPipelineState:
        """
        NON-LLM: Result Validation
        
        Rule-based sanity checks - no LLM needed.
        """
        warnings = []
        
        if state.execution_result:
            # Check for empty results
            if state.row_count == 0:
                warnings.append("Query returned no results")
            
            # Check for NULL values
            for row in state.execution_result[:10]:
                if None in row:
                    warnings.append("Results contain NULL values")
                    break
            
            # Check for negative counts
            for row in state.execution_result[:10]:
                for val in row:
                    if isinstance(val, (int, float)) and val < 0:
                        warnings.append("Results contain negative numbers")
                        break
        
        state.validation_warnings = warnings
        state.result_valid = len(warnings) == 0 or state.row_count > 0
        
        state.add_trace(
            "ResultValidator",
            "Validated results [NO LLM]",
            f"Valid: {state.result_valid}, Warnings: {len(warnings)}",
            str(warnings)
        )
        
        return state
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def _parse_json(self, text: str) -> Dict:
        """Extract JSON from LLM response."""
        try:
            # Try direct parse
            return json.loads(text)
        except:
            pass
        
        # Try to find JSON in response
        patterns = [
            r'\{[\s\S]*\}',  # Greedy
            r'\{[^{}]*\}',   # Non-nested
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    continue
        
        return {}
    
    def _extract_sql(self, text: str) -> str:
        """Extract SQL from LLM response."""
        # Remove markdown code blocks
        text = re.sub(r'```sql\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # Find SELECT statement
        match = re.search(r'(SELECT[\s\S]+?)(?:;|$)', text, re.IGNORECASE)
        if match:
            sql = match.group(1).strip()
            if not sql.endswith(';'):
                sql += ';'
            return sql
        
        return text.strip()
    
    def _build_response(self, state: OptimizedPipelineState, total_time: float) -> FinalResponse:
        """Build final response from pipeline state."""
        # Determine status
        if state.current_step == Step.BLOCKED:
            if state.safety_violations:
                status = ExecutionStatus.BLOCKED
            else:
                status = ExecutionStatus.VALIDATION_FAILED
        elif state.execution_error:
            status = ExecutionStatus.ERROR
        elif state.row_count == 0 and state.intent == IntentType.DATA_QUERY:
            status = ExecutionStatus.EMPTY
        else:
            status = ExecutionStatus.SUCCESS
        
        # Convert trace list to AgentAction objects
        actions = []
        for t in state.trace:
            actions.append(AgentAction(
                agent_name=t.get("agent", "Unknown"),
                action=t.get("action", ""),
                input_summary=t.get("detail", ""),
                output_summary=t.get("summary", ""),
                reasoning=f"LLM calls so far: {t.get('llm_calls_so_far', 0)}"
            ))
        
        # Build ReasoningTrace
        reasoning_trace = ReasoningTrace(
            user_query=state.user_query,
            actions=actions,
            total_time_ms=total_time,
            correction_attempts=state.retry_count,
            final_status=status
        )
        
        return FinalResponse(
            answer=state.final_answer or "Unable to process query",
            sql_used=state.generated_sql or "N/A",
            reasoning_trace=reasoning_trace,
            row_count=state.row_count,
            warnings=state.validation_warnings
        )


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def create_quota_optimized_orchestrator(verbose: bool = VERBOSE, max_calls: int = 8):
    """Factory function for creating the optimized orchestrator."""
    return QuotaOptimizedOrchestrator(verbose=verbose, max_llm_calls=max_calls)


def run_query(query: str, verbose: bool = False, max_calls: int = 8) -> FinalResponse:
    """
    Run a query through the quota-optimized orchestrator.
    
    Args:
        query: Natural language question
        verbose: Enable verbose logging
        max_calls: Maximum LLM API calls allowed (default: 8)
        
    Returns:
        FinalResponse with answer, SQL, trace, and metrics
    """
    orchestrator = QuotaOptimizedOrchestrator(verbose=verbose, max_llm_calls=max_calls)
    return orchestrator.process_query(query)
