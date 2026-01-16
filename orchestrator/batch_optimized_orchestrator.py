"""
Batch-Optimized Orchestrator for NL2SQL Pipeline.

QUOTA-SAFETY REFACTOR
======================
This orchestrator implements STRICT agent batching to minimize Gemini API calls
while maintaining all 12 logical agents for transparency and debuggability.

AGENT → BATCH MAPPING (MANDATORY)
==================================
┌──────────────────────┬────────────────┬──────────────────────────────────┐
│ Logical Agent        │ Execution Type │ Batch Assignment                 │
├──────────────────────┼────────────────┼──────────────────────────────────┤
│ IntentAnalyzer       │ LLM            │ BATCH 1: Reasoning & Planning    │
│ ClarificationAgent   │ LLM            │ BATCH 1: Reasoning & Planning    │
│ QueryDecomposer      │ LLM            │ BATCH 1: Reasoning & Planning    │
│ QueryPlanner         │ LLM            │ BATCH 1: Reasoning & Planning    │
├──────────────────────┼────────────────┼──────────────────────────────────┤
│ SchemaExplorer       │ Deterministic  │ NO BATCH (Database introspection)│
│ DataExplorer         │ Deterministic  │ NO BATCH (Database sampling)     │
│ SafetyValidator      │ Deterministic  │ NO BATCH (Rule-based checks)     │
│ SQLExecutor          │ Deterministic  │ NO BATCH (Query execution)       │
│ ResultValidator      │ Deterministic  │ NO BATCH (Sanity checks)         │
├──────────────────────┼────────────────┼──────────────────────────────────┤
│ SQLGenerator         │ LLM            │ BATCH 2: SQL Generation          │
├──────────────────────┼────────────────┼──────────────────────────────────┤
│ SelfCorrectionAgent  │ LLM            │ BATCH 3: Correction (conditional)│
├──────────────────────┼────────────────┼──────────────────────────────────┤
│ ResponseSynthesizer  │ LLM            │ BATCH 4: Response                │
└──────────────────────┴────────────────┴──────────────────────────────────┘

API CALL BUDGET
===============
Normal query:  2-3 calls (Batch 1 + Batch 2 + Batch 4)
With retry:    3-5 calls (Batch 1 + Batch 2 + Batch 3 + Batch 2 + Batch 4)
HARD LIMIT:    5 requests/minute (enforced at runtime)

WHY THIS BATCHING?
==================
- BATCH 1 combines early reasoning (intent, clarification, decomposition, planning)
  because they all operate on the user query + schema without needing SQL execution
- BATCH 2 is isolated because SQL generation requires the plan from Batch 1
- BATCH 3 is conditional (only on error) and requires execution feedback
- BATCH 4 is last because it needs final results

Rate Limiter Design
===================
Uses sliding window with 1-minute buckets to enforce 5 req/min hard limit.
Aborts gracefully if exceeded (no silent overruns).
"""

import time
import json
import sqlite3
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime, timedelta

from config import DATABASE_PATH, VERBOSE, DEFAULT_LIMIT, FORBIDDEN_KEYWORDS
from models import FinalResponse, ExecutionStatus, ReasoningTrace, AgentAction
from .llm_client import create_llm_client, LLMError, LLMProvider


# ============================================================
# RATE LIMITER (HARD ENFORCEMENT)
# ============================================================

class RateLimiter:
    """
    Sliding window rate limiter with HARD enforcement.
    Ensures max 5 Gemini requests per 60-second window.
    """
    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_times: deque = deque()
    
    def can_proceed(self) -> bool:
        """Check if request is allowed under rate limit."""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)
        
        # Remove expired timestamps
        while self.request_times and self.request_times[0] < cutoff:
            self.request_times.popleft()
        
        return len(self.request_times) < self.max_requests
    
    def record_request(self):
        """Record a new request timestamp."""
        self.request_times.append(datetime.now())
    
    def get_status(self) -> Dict[str, Any]:
        """Get current rate limit status."""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)
        
        # Clean old entries
        while self.request_times and self.request_times[0] < cutoff:
            self.request_times.popleft()
        
        used = len(self.request_times)
        return {
            "used": used,
            "limit": self.max_requests,
            "remaining": self.max_requests - used,
            "window_seconds": self.window_seconds
        }
    
    def wait_time(self) -> float:
        """Calculate seconds to wait before next request is allowed."""
        if self.can_proceed():
            return 0.0
        
        now = datetime.now()
        oldest = self.request_times[0]
        wait_until = oldest + timedelta(seconds=self.window_seconds)
        wait_seconds = (wait_until - now).total_seconds()
        return max(0.0, wait_seconds)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded and query must abort."""
    pass


# ============================================================
# PIPELINE STATE
# ============================================================

@dataclass
class BatchPipelineState:
    """
    State tracking for batched execution pipeline.
    """
    user_query: str
    start_time_ms: float = 0
    
    # Batch execution log
    batches_executed: List[str] = field(default_factory=list)
    llm_calls_made: int = 0
    
    # Provider tracking (for transparency)
    providers_used: List[Dict[str, Any]] = field(default_factory=list)
    
    # Retry tracking
    retry_count: int = 0
    max_retries: int = 2
    
    # Agent outputs (populated by batches)
    # BATCH 1: Reasoning & Planning
    intent: str = "DATA_QUERY"  # DATA_QUERY | META_QUERY | AMBIGUOUS
    intent_confidence: float = 0.0
    is_complex: bool = False
    needs_data_context: bool = False
    relevant_tables: List[str] = field(default_factory=list)
    resolved_query: str = ""  # After clarification
    assumptions: List[str] = field(default_factory=list)
    decomposition_steps: List[str] = field(default_factory=list)
    query_plan: str = ""
    
    # Deterministic agents (no batch)
    schema_context: str = ""
    data_samples: Dict[str, List] = field(default_factory=dict)
    
    # BATCH 2: SQL Generation
    generated_sql: str = ""
    
    # Deterministic: Safety & Execution
    safety_approved: bool = False
    safety_violations: List[str] = field(default_factory=list)
    execution_result: Optional[List] = None
    execution_error: str = ""
    row_count: int = 0
    
    # Deterministic: Result Validation
    validation_warnings: List[str] = field(default_factory=list)
    
    # BATCH 3: Self-Correction (conditional)
    correction_analysis: str = ""
    corrected_sql: str = ""
    
    # BATCH 4: Response
    final_answer: str = ""
    
    # Trace (all 12 agents logged even though batched)
    trace: List[Dict] = field(default_factory=list)
    
    def add_trace(self, agent: str, summary: str, detail: str = ""):
        """Log agent execution in trace."""
        # Get provider info for this agent's batch
        provider_info = {}
        if self.batches_executed and self.providers_used:
            # Find the provider info for the current batch
            current_batch = self.batches_executed[-1]
            for prov in self.providers_used:
                if prov["batch"] == current_batch:
                    provider_info = prov
                    break
        
        self.trace.append({
            "agent": agent,
            "summary": summary,
            "detail": detail,
            "llm_batch": self.batches_executed[-1] if self.batches_executed else "NONE",
            "llm_calls_so_far": self.llm_calls_made,
            "provider": provider_info.get("provider", "N/A"),
            "fallback_occurred": provider_info.get("fallback_occurred", False),
            "fallback_reason": provider_info.get("fallback_reason", "")
        })


# ============================================================
# BATCH-OPTIMIZED ORCHESTRATOR
# ============================================================

class BatchOptimizedOrchestrator:
    """
    Quota-safe NL2SQL orchestrator with agent batching, rate limiting, and automatic fallback.
    
    Key Features:
    - Only orchestrator calls LLM (agents are passive)
    - Max 5 Gemini requests per minute (hard enforced)
    - Automatic fallback to Groq when Gemini quota exhausted
    - All 12 logical agents maintained for transparency
    - Batched LLM calls use multi-role prompts with structured JSON output
    
    FALLBACK LOGIC:
    - Primary: Gemini (for speed and quality)
    - Fallback: Groq (when Gemini quota exhausted or rate limited)
    - Transparent: Reasoning trace shows which provider was used
    """
    
    def __init__(self, verbose: bool = VERBOSE):
        self.verbose = verbose
        self.llm = create_llm_client(primary="gemini", fallback="groq", verbose=verbose)
        self.rate_limiter = RateLimiter(max_requests=5, window_seconds=60)
    
    def _log(self, message: str):
        if self.verbose:
            print(f"[ORCHESTRATOR] {message}")
    
    def process_query(self, user_query: str) -> FinalResponse:
        """
        Process query with batched LLM calls.
        
        Expected flow:
        1. BATCH 1: Reasoning & Planning (1 API call)
        2. Schema/Data exploration (deterministic, 0 API calls)
        3. BATCH 2: SQL Generation (1 API call)
        4. Safety/Execution (deterministic, 0 API calls)
        5. BATCH 3: Correction if needed (conditional, 0-2 API calls)
        6. BATCH 4: Response (1 API call)
        
        Total: 2-5 API calls depending on corrections
        """
        state = BatchPipelineState(
            user_query=user_query,
            start_time_ms=time.time() * 1000
        )
        
        self._log(f"{'='*60}")
        self._log(f"QUERY: {user_query}")
        self._log(f"Rate Limit: {self.rate_limiter.get_status()}")
        self._log(f"{'='*60}")
        
        try:
            # BATCH 1: Reasoning & Planning (Intent, Clarify, Decompose, Plan)
            self._log("→ BATCH 1: Reasoning & Planning [LLM]")
            state = self._batch_1_reasoning_and_planning(state)
            
            if state.intent == "AMBIGUOUS" and not state.resolved_query:
                return self._abort(state, "Unresolved ambiguity")
            
            # Deterministic: Schema Exploration
            self._log("→ SchemaExplorer [Deterministic]")
            state = self._deterministic_schema_exploration(state)
            
            # For meta-queries, skip to response
            if state.intent == "META_QUERY":
                self._log("→ META_QUERY detected, skipping SQL generation")
                state = self._batch_4_response_synthesis(state)
                return self._finalize(state)
            
            # Deterministic: Data Exploration (if needed)
            if state.needs_data_context:
                self._log("→ DataExplorer [Deterministic]")
                state = self._deterministic_data_exploration(state)
            
            # BATCH 2: SQL Generation
            self._log("→ BATCH 2: SQL Generation [LLM]")
            state = self._batch_2_sql_generation(state)
            
            # Deterministic: Safety Validation
            self._log("→ SafetyValidator [Deterministic]")
            state = self._deterministic_safety_validation(state)
            
            if not state.safety_approved:
                return self._abort(state, f"Safety violations: {state.safety_violations}")
            
            # Deterministic: SQL Execution (with retry loop)
            retry_loop = 0
            while retry_loop <= state.max_retries:
                self._log(f"→ SQLExecutor [Deterministic] (attempt {retry_loop + 1})")
                state = self._deterministic_sql_execution(state)
                
                if not state.execution_error:
                    break  # Success
                
                # Retry with correction
                if retry_loop < state.max_retries:
                    self._log(f"→ BATCH 3: Self-Correction [LLM] (retry {retry_loop + 1})")
                    state = self._batch_3_self_correction(state)
                    
                    # Re-validate corrected SQL
                    state = self._deterministic_safety_validation(state)
                    if not state.safety_approved:
                        return self._abort(state, "Corrected SQL failed safety check")
                    
                    retry_loop += 1
                    state.retry_count = retry_loop
                else:
                    self._log("→ Max retries reached")
                    break
            
            # Deterministic: Result Validation
            if not state.execution_error:
                self._log("→ ResultValidator [Deterministic]")
                state = self._deterministic_result_validation(state)
            
            # BATCH 4: Response Synthesis
            self._log("→ BATCH 4: Response Synthesis [LLM]")
            state = self._batch_4_response_synthesis(state)
            
            return self._finalize(state)
        
        except RateLimitExceeded as e:
            self._log(f"⚠️ RATE LIMIT EXCEEDED: {e}")
            return self._abort(state, str(e))
        except Exception as e:
            self._log(f"⚠️ ERROR: {e}")
            return self._abort(state, f"Internal error: {str(e)}")
    
    # ============================================================
    # CENTRALIZED LLM CALLER
    # ============================================================
    
    def call_llm_batch(self, batch_name: str, roles: List[str], 
                       prompt: str, state: BatchPipelineState) -> Dict[str, Any]:
        """
        Centralized LLM batch caller with automatic fallback.
        
        Enforces:
        - Rate limiting (5 req/min hard limit)
        - Automatic Gemini to Groq fallback on quota errors
        - Structured JSON output per role
        - Logging and traceability
        
        Args:
            batch_name: Name of batch (e.g., "BATCH 1: Reasoning & Planning")
            roles: List of agent roles in this batch
            prompt: Multi-role prompt requesting JSON output
            state: Current pipeline state
        
        Returns:
            Parsed JSON dict with results per role
        """
        # Check rate limit
        if not self.rate_limiter.can_proceed():
            wait_time = self.rate_limiter.wait_time()
            raise RateLimitExceeded(
                f"Rate limit of {self.rate_limiter.max_requests} requests/minute exceeded. "
                f"Would need to wait {wait_time:.1f}s. Aborting to prevent overrun."
            )
        
        # Make LLM call with automatic fallback
        self._log(f"  → Calling LLM for: {', '.join(roles)}")
        
        try:
            # Call with automatic fallback (Gemini → Groq)
            llm_response = self.llm.generate(prompt, metadata={"batch": batch_name})
            content = llm_response.content
            
            # Record request
            self.rate_limiter.record_request()
            state.llm_calls_made += 1
            state.batches_executed.append(batch_name)
            
            # Track provider used
            provider_info = {
                "batch": batch_name,
                "provider": llm_response.provider.value,
                "model": llm_response.model,
                "fallback_occurred": llm_response.fallback_occurred
            }
            if llm_response.fallback_occurred:
                provider_info["fallback_reason"] = llm_response.fallback_reason
            state.providers_used.append(provider_info)
            
            # Log provider used
            if llm_response.fallback_occurred:
                self._log(f"  ⚠️ Fallback to {llm_response.provider.value.upper()} (Reason: {llm_response.fallback_reason})")
            else:
                self._log(f"  ✓ {llm_response.provider.value.upper()} call successful")
            
            # Parse JSON
            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            self._log(f"  ✓ API call successful (Total: {state.llm_calls_made}, Remaining: {self.rate_limiter.get_status()['remaining']})")
            return result
        
        except json.JSONDecodeError as e:
            self._log(f"  ✗ JSON parse error: {e}")
            self._log(f"  Raw response: {content[:200]}...")
            raise
        except LLMError as e:
            self._log(f"  ✗ Both providers failed: {e}")
            raise
        
        except Exception as e:
            self._log(f"  ✗ Unexpected error: {e}")
            raise
            raise
        except Exception as e:
            self._log(f"  ✗ LLM call failed: {e}")
            raise
    
    # ============================================================
    # BATCH 1: REASONING & PLANNING
    # Consolidates: IntentAnalyzer, ClarificationAgent, QueryDecomposer, QueryPlanner
    # ============================================================
    
    def _batch_1_reasoning_and_planning(self, state: BatchPipelineState) -> BatchPipelineState:
        """
        Single LLM call executing 4 logical agents:
        1. IntentAnalyzer: Classify intent (DATA/META/AMBIGUOUS)
        2. ClarificationAgent: Resolve ambiguities or make assumptions
        3. QueryDecomposer: Break into steps if complex
        4. QueryPlanner: Design query plan
        """
        prompt = f"""You are a multi-agent NL2SQL system. Analyze this query through 4 sequential agent roles.
Return a JSON object with results from each agent.

USER QUERY: {state.user_query}

Execute these agents in order:

1. **IntentAnalyzer**: Classify intent
   - "DATA_QUERY": Requesting data from database
   - "META_QUERY": Asking about database structure (what tables, columns, etc.)
   - "AMBIGUOUS": Too vague to process
   
2. **ClarificationAgent**: Resolve ambiguities
   - If ambiguous terms exist (e.g., "recent", "best"), provide reasonable assumptions
   - List all assumptions made
   - Rewrite query with clarifications
   
3. **QueryDecomposer**: Analyze complexity
   - Is this a simple or complex query?
   - Does it need data context (date ranges, value samples)?
   - Break into logical steps if complex
   
4. **QueryPlanner**: Design the query plan
   - What tables are needed?
   - What joins are required?
   - What filters/aggregations?
   - What columns to select?

Return JSON in this EXACT format:
{{
  "intent_analyzer": {{
    "intent": "DATA_QUERY" | "META_QUERY" | "AMBIGUOUS",
    "confidence": 0.0-1.0,
    "reasoning": "why this classification"
  }},
  "clarification_agent": {{
    "has_ambiguity": true/false,
    "resolved_query": "clarified version of query",
    "assumptions": ["assumption 1", "assumption 2"]
  }},
  "query_decomposer": {{
    "is_complex": true/false,
    "needs_data_context": true/false,
    "steps": ["step 1", "step 2"]
  }},
  "query_planner": {{
    "relevant_tables": ["table1", "table2"],
    "plan_description": "high-level query strategy"
  }}
}}
"""
        
        result = self.call_llm_batch(
            batch_name="BATCH 1: Reasoning & Planning",
            roles=["IntentAnalyzer", "ClarificationAgent", "QueryDecomposer", "QueryPlanner"],
            prompt=prompt,
            state=state
        )
        
        # Extract results
        intent_data = result.get("intent_analyzer", {})
        clarify_data = result.get("clarification_agent", {})
        decomp_data = result.get("query_decomposer", {})
        plan_data = result.get("query_planner", {})
        
        # Populate state
        state.intent = intent_data.get("intent", "DATA_QUERY")
        state.intent_confidence = intent_data.get("confidence", 0.0)
        state.resolved_query = clarify_data.get("resolved_query", state.user_query)
        state.assumptions = clarify_data.get("assumptions", [])
        state.is_complex = decomp_data.get("is_complex", False)
        state.needs_data_context = decomp_data.get("needs_data_context", False)
        state.decomposition_steps = decomp_data.get("steps", [])
        state.relevant_tables = plan_data.get("relevant_tables", [])
        state.query_plan = plan_data.get("plan_description", "")
        
        # Log all 4 agents
        state.add_trace("IntentAnalyzer", 
                       f"Intent: {state.intent} (confidence: {state.intent_confidence:.2f})",
                       intent_data.get("reasoning", ""))
        state.add_trace("ClarificationAgent",
                       f"Resolved query: {state.resolved_query}",
                       f"Assumptions: {state.assumptions}")
        state.add_trace("QueryDecomposer",
                       f"Complex: {state.is_complex}, Steps: {len(state.decomposition_steps)}",
                       str(state.decomposition_steps))
        state.add_trace("QueryPlanner",
                       f"Tables: {state.relevant_tables}",
                       state.query_plan)
        
        return state
    
    # ============================================================
    # DETERMINISTIC AGENTS (No LLM calls)
    # ============================================================
    
    def _deterministic_schema_exploration(self, state: BatchPipelineState) -> BatchPipelineState:
        """SchemaExplorer: Pure database introspection."""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Build schema context
            schema_parts = []
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table});")
                columns = cursor.fetchall()
                col_str = ", ".join([f"{c[1]} {c[2]}" for c in columns])
                schema_parts.append(f"{table}({col_str})")
            
            state.schema_context = "; ".join(schema_parts)
            conn.close()
            
            state.add_trace("SchemaExplorer",
                           f"Found {len(tables)} tables",
                           state.schema_context[:200] + "...")
        except Exception as e:
            state.add_trace("SchemaExplorer", f"Error: {e}", "")
        
        return state
    
    def _deterministic_data_exploration(self, state: BatchPipelineState) -> BatchPipelineState:
        """DataExplorer: Sample data from relevant tables."""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            for table in state.relevant_tables[:3]:  # Limit to 3 tables
                cursor.execute(f"SELECT * FROM {table} LIMIT 3;")
                samples = cursor.fetchall()
                state.data_samples[table] = [list(row) for row in samples]
            
            conn.close()
            
            state.add_trace("DataExplorer",
                           f"Sampled {len(state.data_samples)} tables",
                           str(list(state.data_samples.keys())))
        except Exception as e:
            state.add_trace("DataExplorer", f"Error: {e}", "")
        
        return state
    
    def _deterministic_safety_validation(self, state: BatchPipelineState) -> BatchPipelineState:
        """SafetyValidator: Rule-based SQL safety checks."""
        sql = state.corrected_sql if state.corrected_sql else state.generated_sql
        violations = []
        
        # Check forbidden keywords
        sql_upper = sql.upper()
        for keyword in FORBIDDEN_KEYWORDS:
            if keyword in sql_upper:
                violations.append(f"Forbidden keyword: {keyword}")
        
        # Check for LIMIT
        if "LIMIT" not in sql_upper:
            violations.append("Missing LIMIT clause")
        
        # Check for SELECT *
        if "SELECT *" in sql_upper or "SELECT*" in sql_upper:
            violations.append("SELECT * is forbidden")
        
        state.safety_approved = len(violations) == 0
        state.safety_violations = violations
        
        status = "✓ APPROVED" if state.safety_approved else f"✗ REJECTED: {violations}"
        state.add_trace("SafetyValidator", status, sql[:100])
        
        return state
    
    def _deterministic_sql_execution(self, state: BatchPipelineState) -> BatchPipelineState:
        """SQLExecutor: Execute SQL query."""
        sql = state.corrected_sql if state.corrected_sql else state.generated_sql
        
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute(sql)
            results = cursor.fetchall()
            conn.close()
            
            state.execution_result = [list(row) for row in results]
            state.row_count = len(results)
            state.execution_error = ""
            
            state.add_trace("SQLExecutor",
                           f"✓ Success: {state.row_count} rows",
                           sql)
        except Exception as e:
            state.execution_error = str(e)
            state.execution_result = None
            state.row_count = 0
            
            state.add_trace("SQLExecutor",
                           f"✗ Error: {e}",
                           sql)
        
        return state
    
    def _deterministic_result_validation(self, state: BatchPipelineState) -> BatchPipelineState:
        """ResultValidator: Sanity checks on results."""
        warnings = []
        
        if state.row_count == 0:
            warnings.append("Empty result set")
        
        # Check for negative counts
        if state.execution_result:
            for row in state.execution_result:
                for val in row:
                    if isinstance(val, (int, float)) and val < 0:
                        warnings.append(f"Negative value detected: {val}")
                        break
        
        state.validation_warnings = warnings
        
        status = "✓ Valid" if not warnings else f"⚠ Warnings: {warnings}"
        state.add_trace("ResultValidator", status, "")
        
        return state
    
    # ============================================================
    # BATCH 2: SQL GENERATION
    # ============================================================
    
    def _batch_2_sql_generation(self, state: BatchPipelineState) -> BatchPipelineState:
        """Single LLM call for SQLGenerator agent."""
        prompt = f"""You are SQLGenerator agent. Generate valid SQLite SQL for this query.

USER QUERY: {state.resolved_query}
QUERY PLAN: {state.query_plan}
SCHEMA: {state.schema_context}

SAFETY RULES (MANDATORY):
1. Always include LIMIT clause (default: {DEFAULT_LIMIT})
2. Never use SELECT * (specify columns explicitly)
3. Only use SELECT statements (no INSERT, UPDATE, DELETE, DROP)

Return JSON:
{{
  "sql_generator": {{
    "sql": "your SQL query here",
    "explanation": "why this SQL matches the plan"
  }}
}}
"""
        
        result = self.call_llm_batch(
            batch_name="BATCH 2: SQL Generation",
            roles=["SQLGenerator"],
            prompt=prompt,
            state=state
        )
        
        sql_data = result.get("sql_generator", {})
        state.generated_sql = sql_data.get("sql", "")
        
        state.add_trace("SQLGenerator",
                       "Generated SQL",
                       state.generated_sql)
        
        return state
    
    # ============================================================
    # BATCH 3: SELF-CORRECTION (Conditional)
    # ============================================================
    
    def _batch_3_self_correction(self, state: BatchPipelineState) -> BatchPipelineState:
        """Single LLM call for SelfCorrectionAgent (only on error)."""
        prompt = f"""You are SelfCorrectionAgent. The SQL query failed. Analyze and fix it.

ORIGINAL QUERY: {state.resolved_query}
FAILED SQL: {state.generated_sql}
ERROR: {state.execution_error}
SCHEMA: {state.schema_context}

Analyze the error and generate corrected SQL.

Return JSON:
{{
  "self_correction": {{
    "analysis": "what went wrong",
    "corrected_sql": "fixed SQL query",
    "changes_made": "what you changed"
  }}
}}
"""
        
        result = self.call_llm_batch(
            batch_name="BATCH 3: Self-Correction",
            roles=["SelfCorrectionAgent"],
            prompt=prompt,
            state=state
        )
        
        corr_data = result.get("self_correction", {})
        state.correction_analysis = corr_data.get("analysis", "")
        state.corrected_sql = corr_data.get("corrected_sql", "")
        
        state.add_trace("SelfCorrectionAgent",
                       f"Retry {state.retry_count + 1}: {state.correction_analysis}",
                       state.corrected_sql)
        
        return state
    
    # ============================================================
    # BATCH 4: RESPONSE SYNTHESIS
    # ============================================================
    
    def _batch_4_response_synthesis(self, state: BatchPipelineState) -> BatchPipelineState:
        """Single LLM call for ResponseSynthesizer agent."""
        result_summary = f"{state.row_count} rows" if state.execution_result else "No results"
        
        prompt = f"""You are ResponseSynthesizer agent. Generate a human-readable answer.

USER QUERY: {state.user_query}
QUERY RESULTS: {result_summary}
DATA: {str(state.execution_result[:5]) if state.execution_result else "None"}
ERROR: {state.execution_error if state.execution_error else "None"}

Generate a natural language answer that:
1. Directly answers the user's question
2. Is concise and clear
3. Handles empty results gracefully

Return JSON:
{{
  "response_synthesizer": {{
    "answer": "your human-readable answer here"
  }}
}}
"""
        
        result = self.call_llm_batch(
            batch_name="BATCH 4: Response Synthesis",
            roles=["ResponseSynthesizer"],
            prompt=prompt,
            state=state
        )
        
        resp_data = result.get("response_synthesizer", {})
        state.final_answer = resp_data.get("answer", "Unable to generate response")
        
        state.add_trace("ResponseSynthesizer",
                       "Generated answer",
                       state.final_answer[:100])
        
        return state
    
    # ============================================================
    # FINALIZATION
    # ============================================================
    
    def _finalize(self, state: BatchPipelineState) -> FinalResponse:
        """Build final response."""
        total_time = time.time() * 1000 - state.start_time_ms
        
        # Determine status
        if state.execution_error:
            status = ExecutionStatus.ERROR
        elif state.row_count == 0 and not state.execution_error:
            status = ExecutionStatus.EMPTY
        else:
            status = ExecutionStatus.SUCCESS
        
        # Build reasoning trace
        trace_actions = [
            AgentAction(
                agent_name=t["agent"],
                action=t["summary"],
                input_summary=state.user_query if i == 0 else "Previous agent output",
                output_summary=t["detail"] if t["detail"] else t["summary"],
                reasoning=t["summary"]
            )
            for i, t in enumerate(state.trace)
        ]
        
        trace = ReasoningTrace(
            user_query=state.user_query,
            actions=trace_actions,
            total_time_ms=int(total_time),
            correction_attempts=state.retry_count,
            final_status=status
        )
        
        sql_used = state.corrected_sql if state.corrected_sql else state.generated_sql
        
        self._log(f"{'='*60}")
        self._log(f"COMPLETED: {state.llm_calls_made} LLM calls, {total_time:.0f}ms")
        self._log(f"Rate Limit Status: {self.rate_limiter.get_status()}")
        
        # Log provider usage
        if state.providers_used:
            self._log("Provider Usage:")
            for prov in state.providers_used:
                fallback_str = f" (Fallback from Gemini: {prov['fallback_reason']})" if prov['fallback_occurred'] else ""
                self._log(f"  - {prov['batch']}: {prov['provider'].upper()}{fallback_str}")
        
        self._log(f"{'='*60}")
        
        return FinalResponse(
            answer=state.final_answer,
            sql_used=sql_used,
            row_count=state.row_count,
            reasoning_trace=trace,
            warnings=state.validation_warnings
        )
    
    def _abort(self, state: BatchPipelineState, reason: str) -> FinalResponse:
        """Abort execution with error response."""
        total_time = time.time() * 1000 - state.start_time_ms
        
        trace_actions = [
            AgentAction(
                agent_name=t["agent"],
                action=t["summary"],
                input_summary=state.user_query if i == 0 else "Previous agent output",
                output_summary=t["detail"] if t["detail"] else t["summary"],
                reasoning=t["summary"]
            )
            for i, t in enumerate(state.trace)
        ]
        
        trace_actions.append(
            AgentAction(
                agent_name="Orchestrator",
                action="Abort query processing",
                input_summary="Pipeline state",
                output_summary=f"ABORTED: {reason}",
                reasoning=f"ABORTED: {reason}"
            )
        )
        
        trace = ReasoningTrace(
            user_query=state.user_query,
            actions=trace_actions,
            total_time_ms=int(total_time),
            correction_attempts=state.retry_count,
            final_status=ExecutionStatus.BLOCKED
        )
        
        return FinalResponse(
            answer=f"Query aborted: {reason}",
            sql_used="",
            row_count=0,
            reasoning_trace=trace,
            warnings=[reason]
        )


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def run_query(query: str, verbose: bool = VERBOSE) -> FinalResponse:
    """Run a query with the batch-optimized orchestrator."""
    orchestrator = BatchOptimizedOrchestrator(verbose=verbose)
    return orchestrator.process_query(query)
