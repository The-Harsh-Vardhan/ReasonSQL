"""
Batch-Optimized Orchestrator for ReasonSQL Pipeline.

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
HARD LIMITS:   
  - 5 requests/minute (enforced at runtime)
  - MAX_LLM_CALLS_PER_QUERY (default: 5, configurable in .env)
  - MAX_LLM_TOKENS per call (default: 256, configurable in .env)

TOKEN QUOTA ENFORCEMENT
=======================
To prevent mid-demo failures from quota exhaustion:
1. MAX_LLM_TOKENS enforced on EVERY LLM call (Gemini, Groq)
2. MAX_LLM_CALLS_PER_QUERY enforced per query execution
3. Temperature capped at 0.2 for consistency
4. No local overrides allowed by agents

Configure in .env:
  MAX_LLM_TOKENS=256           # Conservative for demos
  MAX_LLM_CALLS_PER_QUERY=5    # Prevents runaway retries

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
Token limits prevent excessive TPD (tokens per day) usage on providers.
"""

import time
import json
import sqlite3
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime, timedelta

from configs import DATABASE_PATH, VERBOSE, DEFAULT_LIMIT, FORBIDDEN_KEYWORDS, get_gemini_key_count, MAX_LLM_CALLS_PER_QUERY
from backend.db_connection import get_connection_context, get_db_type
from backend.models import FinalResponse, ExecutionStatus, ReasoningTrace, AgentAction
from .llm_client import create_llm_client, LLMError, LLMProvider
from .json_utils import safe_parse_llm_json, JSONExtractionError


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
    
    CRITICAL INVARIANT:
    ===================
    reasoning_trace MUST ALWAYS exist, even for blocked/aborted queries.
    This ensures FinalResponse can always access it.
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
    
    # Reasoning trace (ALWAYS populated - initialized in process_query)
    reasoning_trace: Optional['ReasoningTrace'] = field(default=None)
    
    # Agent outputs (populated by batches)
    # BATCH 1: Reasoning & Planning
    # CRITICAL: Intent is IMMUTABLE - set ONCE in BATCH 1, never modified
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
    sql_was_executed: bool = False  # Track if SQL execution occurred
    
    # Deterministic: Safety & Execution
    safety_approved: bool = False
    safety_violations: List[str] = field(default_factory=list)
    fk_violations: List[str] = field(default_factory=list)  # FK-specific violations for self-correction
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
    Quota-safe ReasonSQL orchestrator with agent batching, rate limiting, and automatic fallback.
    
    Key Features:
    - Only orchestrator calls LLM (agents are passive)
    - Max 5 Gemini requests per minute (hard enforced)
    - Automatic tertiary fallback: Gemini → Groq → Qwen (last resort)
    - All 12 logical agents maintained for transparency
    - Batched LLM calls use multi-role prompts with structured JSON output
    
    FALLBACK CHAIN (STRICT ORDER):
    ================================
    - Primary: Gemini (for speed and quality)
    - Secondary: Groq (when Gemini exhausted)
    - Tertiary: Qwen (LAST RESORT - when both Gemini and Groq exhausted)
      * Limited to 512 tokens
      * No retry loops
      * Clearly signaled in reasoning trace
    """
    
    def __init__(self, verbose: bool = VERBOSE):
        self.verbose = verbose
        # Initialize with conditional tertiary fallback: Gemini → Groq → [Qwen if enabled]
        # Qwen controlled by ENABLE_QWEN_FALLBACK feature flag
        self.llm = create_llm_client(primary="gemini", fallback="groq", verbose=verbose)
        
        # Scale rate limit by number of available keys (5 RPM per key)
        key_count = get_gemini_key_count()
        total_limit = 5 * key_count
        if key_count > 1 and self.verbose:
            print(f"[Orchestrator] 🔑 Multi-key rotation active: {key_count} keys found. Limit increased to {total_limit} RPM.")
            
        self.rate_limiter = RateLimiter(max_requests=total_limit, window_seconds=60)
    
    def _log(self, message: str):
        if self.verbose:
            print(f"[Orchestrator] {message}")
            
    def run_query(self, user_query: str):
        """Alias for backward compatibility."""
        return self.process_query(user_query)
    
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
        
        # CRITICAL: Initialize reasoning_trace immediately
        # This ensures it exists even if we abort early
        state.reasoning_trace = ReasoningTrace(
            user_query=user_query,
            actions=[],
            total_time_ms=0,
            correction_attempts=0,
            final_status=ExecutionStatus.SUCCESS  # Will be updated
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
            
            # ============================================================
            # CRITICAL EARLY-EXIT: Meta-Query Handling
            # ============================================================
            # Intent is IMMUTABLE (set in BATCH 1).
            # Meta-queries MUST exit here - they NEVER execute SQL.
            # This is the ONLY place meta-query handling occurs.
            # ============================================================
            if state.intent == "META_QUERY":
                self._log("→ META_QUERY detected, skipping SQL generation")
                state = self._batch_4_response_synthesis(state)
                # sql_was_executed remains False - critical for invariant checks
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
            
            # If FK violations detected, trigger self-correction immediately
            if state.fk_violations:
                self._log(f"→ FK VIOLATIONS detected: {len(state.fk_violations)} issues")
                
                retry_loop = 0
                while retry_loop <= state.max_retries:
                    # Try self-correction
                    self._log(f"→ BATCH 3: FK Self-Correction [LLM] (attempt {retry_loop + 1})")
                    state = self._batch_3_self_correction(state)
                    
                    # Re-validate corrected SQL
                    state = self._deterministic_safety_validation(state)
                    
                    if state.safety_approved:
                        self._log("→ FK correction successful")
                        break
                    
                    if retry_loop < state.max_retries:
                        retry_loop += 1
                        state.retry_count = retry_loop
                    else:
                        self._log("→ Max FK correction attempts reached")
                        return self._abort(state, f"FK violations persist after {state.max_retries} attempts: {state.fk_violations}")
            
            if not state.safety_approved:
                return self._abort(state, f"Safety violations: {state.safety_violations}")
            
            # Deterministic: SQL Execution (with retry loop)
            retry_loop = 0
            while retry_loop <= state.max_retries:
                self._log(f"→ SQLExecutor [Deterministic] (attempt {retry_loop + 1})")
                state = self._deterministic_sql_execution(state)
                state.sql_was_executed = True  # Mark SQL execution occurred
                
                if not state.execution_error:
                    break  # Success
                
                # Retry with correction
                if retry_loop < state.max_retries:
                    self._log(f"→ BATCH 3: Self-Correction [LLM] (retry {retry_loop + 1})")
                    state = self._batch_3_self_correction(state)
                    
                    # Re-validate corrected SQL
                    state = self._deterministic_safety_validation(state)
                    if not state.safety_approved:
                        violations_detail = "; ".join(state.safety_violations)
                        self._log(f"→ Corrected SQL still has violations: {violations_detail}")
                        return self._abort(state, f"Corrected SQL failed safety check: {violations_detail}")
                    
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
            # CRITICAL: Always call ResponseSynthesizer for DATA_QUERY
            # (intent was set in BATCH 1 and is immutable)
            self._log("→ BATCH 4: Response Synthesis [LLM]")
            state = self._batch_4_response_synthesis(state)
            
            # FINAL INVARIANT CHECK before returning
            if state.intent == "DATA_QUERY" and not state.final_answer:
                raise RuntimeError(
                    f"CRITICAL BUG: DATA_QUERY but ResponseSynthesizer did not generate answer. "
                    f"Answer: {state.final_answer}"
                )
            
            return self._finalize(state)
        
        except RateLimitExceeded as e:
            self._log(f"⚠️ RATE LIMIT EXCEEDED: {e}")
            return self._abort(state, str(e))
        except QuotaExceededError as e:
            # LLM quota exhausted across all enabled providers - graceful abort
            self._log("⚠️ LLM QUOTA EXHAUSTED - returning graceful failure")
            
            # Get provider attempt history for reasoning trace
            provider_stats = self.llm.get_stats()
            provider_attempts = provider_stats.get('last_provider_attempts', [])
            fallback_chain = provider_stats.get('fallback_chain', 'unknown')
            
            self._log(f"   Fallback chain: {fallback_chain}")
            self._log(f"   Provider attempts: {len(provider_attempts)}")
            
            return self._abort_quota_exhausted(state, str(e), provider_attempts)
        except Exception as e:
            self._log(f"⚠️ ERROR: {e}")
            return self._abort(state, f"Internal error: {str(e)}")
    
    # ============================================================
    # CENTRALIZED LLM CALLER
    # ============================================================
    
    def call_llm_batch(self, batch_name: str, roles: List[str], 
                       prompt: str, state: BatchPipelineState) -> Dict[str, Any]:
        """
        Centralized LLM batch caller with automatic fallback and strict quota enforcement.
        
        Enforces:
        - Rate limiting (5 req/min hard limit)
        - Token limits (MAX_LLM_TOKENS per call - configured in .env)
        - Call count limits (MAX_LLM_CALLS_PER_QUERY - configured in .env)
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
            
        Raises:
            RateLimitExceeded: If max LLM calls per query exceeded
        """
        # CRITICAL: Enforce max LLM calls per query (hard cap)
        if state.llm_calls_made >= MAX_LLM_CALLS_PER_QUERY:
            raise RateLimitExceeded(
                f"Maximum LLM calls per query exceeded: {state.llm_calls_made}/{MAX_LLM_CALLS_PER_QUERY}. "
                f"This prevents quota exhaustion. Increase MAX_LLM_CALLS_PER_QUERY in .env if needed."
            )
        
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
            
            # Track provider used with clear labels
            provider_name = llm_response.provider.value
            
            # Determine provider role for UI display
            if provider_name == "gemini":
                provider_label = "Gemini (Primary)"
            elif provider_name == "groq":
                if llm_response.fallback_occurred:
                    provider_label = "Groq (Secondary Fallback)"
                else:
                    provider_label = "Groq (Primary)"
            elif provider_name == "qwen":
                provider_label = "Qwen2.5-Coder-32B (Tertiary/Last-Resort Fallback)"
            else:
                provider_label = provider_name
            
            provider_info = {
                "batch": batch_name,
                "provider": provider_name,
                "provider_label": provider_label,  # User-friendly label
                "model": llm_response.model,
                "fallback_occurred": llm_response.fallback_occurred
            }
            if llm_response.fallback_occurred:
                provider_info["fallback_reason"] = llm_response.fallback_reason
                # Add warning for tertiary fallback
                if provider_name == "qwen":
                    provider_info["warning"] = "⚠️ Tertiary fallback model used - both Gemini and Groq unavailable"
            
            state.providers_used.append(provider_info)
            
            # Log provider used with clear indication of fallback level
            if llm_response.fallback_occurred:
                if provider_name == "qwen":
                    self._log(f"  ⚠️⚠️⚠️ TERTIARY FALLBACK to {provider_label}")
                    self._log(f"  ⚠️ Reason: {llm_response.fallback_reason}")
                else:
                    self._log(f"  ⚠️ Secondary fallback to {provider_label}")
                    self._log(f"  Reason: {llm_response.fallback_reason}")
            else:
                self._log(f"  ✓ {llm_response.provider.value.upper()} call successful")
            
            # SAFE JSON PARSING: Extract first JSON object, ignore extra text
            try:
                result, stripped_text = safe_parse_llm_json(content)
                
                # Log if extra text was stripped (transparency)
                if stripped_text:
                    stripped_preview = stripped_text[:100]
                    self._log(f"  ℹ️ Stripped {len(stripped_text)} chars of extra text: '{stripped_preview}...'")
                    # Record in reasoning trace for debugging
                    if state.reasoning_trace:
                        state.reasoning_trace.actions.append(
                            AgentAction(
                                agent_name=f"{batch_name}_parser",
                                action="stripped_extra_text",
                                input_summary=f"LLM response with {len(stripped_text)} chars extra text",
                                output_summary=f"Stripped {len(stripped_text)} chars: {stripped_preview}...",
                                reasoning=f"LLM returned JSON + commentary. Stripped {len(stripped_text)} characters."
                            )
                        )
                
                self._log(f"  ✓ JSON parsed successfully (Total: {state.llm_calls_made}, Remaining: {self.rate_limiter.get_status()['remaining']})")
                return result
            
            except JSONExtractionError as e:
                self._log(f"  ✗ JSON extraction failed: {e}")
                self._log(f"  Raw LLM response: '{content[:500]}'...")
                raise LLMError(f"Failed to extract valid JSON from LLM response: {e}")
        except LLMError as e:
            self._log(f"  ✗ LLM error: {e}")
            raise
        except Exception as e:
            self._log(f"  ✗ Unexpected error: {e}")
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
   - "AMBIGUOUS": Queries with subjective terms ("recent", "best", "top", "some") WITHOUT explicit qualifiers (like "top 5"). 
     - CRITICAL: subjective terms = AMBIGUOUS. Do not guess.

2. **ClarificationAgent**: Resolve ambiguities
   - If AMBIGUOUS: Generate 2-3 specific clarification questions.
   - If NOT ambiguous: List assumptions made (e.g., "top" implies ORDER BY DESC LIMIT 5).
   - "has_ambiguity": true if subjective terms are present.
   - "clarification_questions": ["question 1", "question 2"] (Required if AMBIGUOUS)
   
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
    "assumptions": ["assumption 1", "assumption 2"],
    "clarification_questions": ["question 1", "question 2"]
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
        clarification_questions = clarify_data.get("clarification_questions", [])
        
        state.is_complex = decomp_data.get("is_complex", False)
        state.needs_data_context = decomp_data.get("needs_data_context", False)
        state.decomposition_steps = decomp_data.get("steps", [])
        state.relevant_tables = plan_data.get("relevant_tables", [])
        state.query_plan = plan_data.get("plan_description", "")
        
        # Handle AMBIGUOUS intent
        if state.intent == "AMBIGUOUS":
            reasoning = intent_data.get("reasoning", "Subjective terms detected.")
            questions_text = "\n".join([f"- {q}" for q in clarification_questions])
            state.final_answer = (
                f"### ❓ Clarification Needed\n\n"
                f"{reasoning}\n\n"
                f"**Please clarify:**\n{questions_text}"
            )
            state.reasoning_trace.final_status = ExecutionStatus.BLOCKED
            
            # Log trace and return early
            state.add_trace("IntentAnalyzer", 
                        f"Intent: {state.intent} (confidence: {state.intent_confidence:.2f})",
                        reasoning)
            state.add_trace("ClarificationAgent",
                        "Identified Ambiguity",
                        f"Questions:\n{questions_text}")
            
            # Since we abort here, we must finalize
            self._finalize(state)
            return state

        # Log all 4 agents (Normal flow)
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
            db_type = get_db_type()
            
            with get_connection_context() as conn:
                cursor = conn.cursor()
                
                # Get all tables
                if db_type == "sqlite":
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = [row[0] for row in cursor.fetchall()]
                else:
                    cursor.execute("""
                        SELECT table_name FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    """)
                    tables = [row[0] if isinstance(row, tuple) else row['table_name'] for row in cursor.fetchall()]
                
                # Build schema context
                schema_parts = []
                for table in tables:
                    if db_type == "sqlite":
                        cursor.execute(f"PRAGMA table_info({table});")
                        columns = cursor.fetchall()
                        col_str = ", ".join([f"{c[1]} {c[2]}" for c in columns])
                    else:
                        cursor.execute("""
                            SELECT column_name, data_type FROM information_schema.columns
                            WHERE table_schema = 'public' AND table_name = %s
                            ORDER BY ordinal_position
                        """, (table,))
                        columns = cursor.fetchall()
                        col_str = ", ".join([f"{c[0] if isinstance(c, tuple) else c['column_name']} {c[1] if isinstance(c, tuple) else c['data_type']}" for c in columns])
                    schema_parts.append(f"{table}({col_str})")
                
                state.schema_context = "; ".join(schema_parts)
                
                state.add_trace("SchemaExplorer",
                               f"Found {len(tables)} tables",
                               state.schema_context[:200] + "...")
        except Exception as e:
            state.add_trace("SchemaExplorer", f"Error: {e}", "")
        
        return state
    
    def _deterministic_data_exploration(self, state: BatchPipelineState) -> BatchPipelineState:
        """DataExplorer: Sample data from relevant tables."""
        try:
            with get_connection_context() as conn:
                cursor = conn.cursor()
                
                for table in state.relevant_tables[:3]:  # Limit to 3 tables
                    cursor.execute(f"SELECT * FROM {table} LIMIT 3;")
                    samples = cursor.fetchall()
                    # Handle both tuple and dict row formats
                    state.data_samples[table] = [list(row) if isinstance(row, tuple) else list(row.values()) for row in samples]
                
                state.add_trace("DataExplorer",
                               f"Sampled {len(state.data_samples)} tables",
                               str(list(state.data_samples.keys())))
        except Exception as e:
            state.add_trace("DataExplorer", f"Error: {e}", "")
        
        return state
    
    def _deterministic_safety_validation(self, state: BatchPipelineState) -> BatchPipelineState:
        """
        SafetyValidator: Rule-based SQL safety checks + FK JOIN validation.
        
        Validates:
        1. No forbidden keywords (INSERT, DELETE, DROP, etc.)
        2. LIMIT clause present
        3. No SELECT *
        4. JOIN conditions match actual FK relationships (CRITICAL)
        """
        sql = state.corrected_sql if state.corrected_sql else state.generated_sql
        violations = []
        fk_violations = []
        
        # Check forbidden keywords
        sql_upper = sql.upper()
        for keyword in FORBIDDEN_KEYWORDS:
            if keyword in sql_upper:
                violations.append(f"Forbidden keyword: {keyword}")
        
        # Auto-add LIMIT if missing (instead of rejecting)
        if "LIMIT" not in sql_upper:
            # Add LIMIT to the SQL
            sql = sql.rstrip(";").strip() + " LIMIT 100;"
            # Update the state with the corrected SQL
            if state.corrected_sql:
                state.corrected_sql = sql
            else:
                state.generated_sql = sql
            # Log that we auto-added LIMIT
            state.add_trace("SafetyValidator", "Auto-added LIMIT 100 clause", sql[:100])
        
        # Check for SELECT *
        if "SELECT *" in sql_upper or "SELECT*" in sql_upper:
            violations.append("SELECT * is forbidden")
        
        # CRITICAL: Validate all JOIN conditions against schema FK relationships
        join_conditions = self.schema_graph.get_all_joins_in_sql(sql)
        
        if join_conditions:
            for join_cond in join_conditions:
                is_valid, error_msg = self.schema_graph.validate_join_condition(join_cond)
                
                if not is_valid:
                    fk_violations.append(error_msg)
                    
                    # Extract table names for suggestion
                    import re
                    pattern = r'(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)'
                    match = re.search(pattern, join_cond, re.IGNORECASE)
                    if match:
                        table1, _, table2, _ = match.groups()
                        suggestion = self.schema_graph.suggest_correct_joins(table1, table2)
                        fk_violations.append(f"Suggestion: {suggestion}")
        
        # Combine all violations
        all_violations = violations + fk_violations
        
        state.safety_approved = len(all_violations) == 0
        state.safety_violations = all_violations
        
        # Store FK violations separately for self-correction
        state.fk_violations = fk_violations
        
        if state.safety_approved:
            status = "✓ APPROVED (all safety checks passed)"
        elif fk_violations:
            status = f"✗ FK VIOLATION: {len(fk_violations)} invalid JOIN(s)"
        else:
            status = f"✗ REJECTED: {violations}"
        
        state.add_trace("SafetyValidator", status, sql[:100])
        
        return state

    
    def _deterministic_sql_execution(self, state: BatchPipelineState) -> BatchPipelineState:
        """SQLExecutor: Execute SQL query."""
        sql = state.corrected_sql if state.corrected_sql else state.generated_sql
        
        try:
            with get_connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                results = cursor.fetchall()
                
                # Handle both tuple and dict row formats
                state.execution_result = [list(row) if isinstance(row, tuple) else list(row.values()) for row in results]
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
        """Single LLM call for SelfCorrectionAgent (handles execution errors AND FK violations)."""
        
        # Determine if this is a FK violation or execution error
        if state.fk_violations:
            error_context = f"FK SCHEMA VIOLATION: {'; '.join(state.fk_violations)}"
            failed_sql = state.generated_sql
        elif state.safety_violations:
            error_context = f"SAFETY VIOLATIONS: {'; '.join(state.safety_violations)}"
            failed_sql = state.corrected_sql if state.corrected_sql else state.generated_sql
        else:
            error_context = f"EXECUTION ERROR: {state.execution_error}"
            failed_sql = state.generated_sql
        
        prompt = f"""You are SelfCorrectionAgent. The SQL query has issues. Analyze and fix it.

ORIGINAL QUERY: {state.resolved_query}
FAILED SQL: {failed_sql}
{error_context}
SCHEMA: {state.schema_context}

SAFETY RULES (MANDATORY - ALL corrections MUST follow these):
1. ALWAYS include LIMIT clause (default: {DEFAULT_LIMIT})
2. NEVER use SELECT * - specify column names explicitly
3. Only SELECT statements allowed (no INSERT, UPDATE, DELETE, DROP)

CRITICAL: If the error mentions FK (foreign key) violations:
- The JOIN condition violates the database schema's foreign key relationships
- You MUST use the suggested FK path provided in the error message
- Example: If joining Artist to Track, you need intermediate table Album:
  WRONG: Artist.ArtistId = Track.AlbumId (violates FK)
  RIGHT: Artist JOIN Album ON Artist.ArtistId = Album.ArtistId JOIN Track ON Album.AlbumId = Track.AlbumId

If the error mentions SAFETY violations:
- Missing LIMIT: Add "LIMIT {DEFAULT_LIMIT}" at the end
- SELECT *: Replace with explicit column names
- Forbidden keywords: Rewrite to use only SELECT

Analyze the error and generate corrected SQL that passes ALL safety checks.

Return JSON:
{{
  "self_correction": {{
    "analysis": "what went wrong (especially FK/safety violations)",
    "corrected_sql": "fixed SQL query with proper FK paths AND safety compliance",
    "changes_made": "what you changed (especially JOIN corrections and safety fixes)"
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
        
        # Enhanced trace for FK corrections
        if state.fk_violations:
            trace_summary = f"FK CORRECTION (Retry {state.retry_count + 1}): {state.correction_analysis}"
        else:
            trace_summary = f"Retry {state.retry_count + 1}: {state.correction_analysis}"
        
        state.add_trace("SelfCorrectionAgent",
                       trace_summary,
                       state.corrected_sql)
        
        return state
    
    # ============================================================
    # BATCH 4: RESPONSE SYNTHESIS
    # ============================================================
    
    def _batch_4_response_synthesis(self, state: BatchPipelineState) -> BatchPipelineState:
        """Single LLM call for ResponseSynthesizer agent."""
        # Handle META_QUERY differently - use schema context instead of query results
        if state.intent == "META_QUERY":
            # Format schema for readable output
            schema_text = state.schema_context.replace(';', '\n') if state.schema_context else "No schema available"
            
            prompt = f"""You are ResponseSynthesizer agent. Generate a human-readable answer for a META QUERY about database structure.

USER QUERY: {state.user_query}

DATABASE SCHEMA:
{schema_text}

Generate a natural language answer that:
1. Directly answers the user's question about the database structure
2. Lists the relevant tables clearly
3. Is concise and well-formatted

IMPORTANT: Return ONLY valid JSON in this exact format:
{{
  "response_synthesizer": {{
    "answer": "your human-readable answer here"
  }}
}}
"""
        else:
            # Regular data query - use execution results
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
        """Build final response with strict invariant enforcement."""
        total_time = time.time() * 1000 - state.start_time_ms
        
        # ============================================================
        # CRITICAL: Intent is IMMUTABLE and set ONLY in BATCH 1
        # Meta-query handling MUST be early-exit only (line 285-288)
        # ============================================================
        
        # INVARIANT A: If SQL was executed, this CANNOT be a meta-query
        if state.sql_was_executed and state.intent == "META_QUERY":
            raise RuntimeError(
                f"CRITICAL BUG: Intent={state.intent} but SQL was executed. "
                f"This violates immutability - intent should have caused early-exit at line 285-288. "
                f"SQL: {state.generated_sql[:100]}"
            )
        
        # INVARIANT B: If intent is DATA_QUERY, SQL must have been generated
        if state.intent == "DATA_QUERY" and not state.generated_sql and not state.execution_error:
            raise RuntimeError(
                f"CRITICAL BUG: Intent=DATA_QUERY but no SQL generated and no error. "
                f"Pipeline flow violated."
            )
        
        # Intent is determined ONCE in BATCH 1 and is FINAL
        is_meta = state.intent == "META_QUERY"
        
        # INVARIANT C: Meta-queries should have exited early (never reach here)
        if is_meta:
            self._log("⚠️ WARNING: META_QUERY reached _finalize - should have exited at line 287")
        
        # Determine status based on EXECUTION outcomes, NOT intent reinterpretation
        if state.execution_error:
            status = ExecutionStatus.ERROR
        elif is_meta:
            # Meta-queries that somehow reach here (shouldn't happen)
            status = ExecutionStatus.SUCCESS
        elif state.row_count == 0 and not state.execution_error:
            status = ExecutionStatus.EMPTY
        elif state.sql_was_executed and state.row_count > 0:
            # INVARIANT D: If SQL executed successfully with rows, status MUST be SUCCESS
            status = ExecutionStatus.SUCCESS
        else:
            status = ExecutionStatus.SUCCESS
        
        # Update reasoning trace with final data
        # Convert trace list to AgentAction objects if needed
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
        
        # Add trace_actions to existing reasoning_trace
        if state.reasoning_trace:
            state.reasoning_trace.actions.extend(trace_actions)
            state.reasoning_trace.total_time_ms = int(total_time)
            state.reasoning_trace.correction_attempts = state.retry_count
            state.reasoning_trace.final_status = status
            trace = state.reasoning_trace
        else:
            # Fallback if reasoning_trace wasn't initialized (shouldn't happen)
            trace = ReasoningTrace(
                user_query=state.user_query,
                actions=trace_actions,
                total_time_ms=int(total_time),
                correction_attempts=state.retry_count,
                final_status=status
            )
        
        # Determine final SQL used
        sql_used = state.corrected_sql if state.corrected_sql else state.generated_sql
        
        # CRITICAL: Only mark as "No SQL needed" if BOTH:
        # 1. Intent is META_QUERY (set in BATCH 1)
        # 2. SQL was NEVER executed (early-exit path)
        # This prevents valid SQL results from being discarded
        if is_meta and not state.sql_was_executed:
            sql_used = "No SQL needed (meta query)"
        elif state.sql_was_executed and not sql_used:
            # INVARIANT E: If SQL was executed, we must have SQL text
            raise RuntimeError(
                f"CRITICAL BUG: SQL was executed but no SQL text available. "
                f"Generated: {state.generated_sql}, Corrected: {state.corrected_sql}"
            )
        
        self._log(f"{'='*60}")
        self._log(f"COMPLETED: {state.llm_calls_made} LLM calls, {total_time:.0f}ms")
        self._log(f"Rate Limit Status: {self.rate_limiter.get_status()}")
        
        # Log provider usage with clear fallback indicators
        if state.providers_used:
            self._log("Provider Usage:")
            for prov in state.providers_used:
                provider_display = prov.get('provider_label', prov['provider'].upper())
                
                if prov['fallback_occurred']:
                    if prov['provider'] == 'qwen':
                        # Tertiary fallback - critical warning
                        self._log(f"  - {prov['batch']}: ⚠️⚠️⚠️ {provider_display}")
                        self._log(f"    └─ Reason: {prov['fallback_reason']}")
                        if 'warning' in prov:
                            self._log(f"    └─ {prov['warning']}")
                    else:
                        # Secondary fallback
                        self._log(f"  - {prov['batch']}: ⚠️ {provider_display}")
                        self._log(f"    └─ Reason: {prov['fallback_reason']}")
                else:
                    # Primary provider
                    self._log(f"  - {prov['batch']}: ✓ {provider_display}")
        
        self._log(f"{'='*60}")
        
        return FinalResponse(
            answer=state.final_answer,
            sql_used=sql_used,
            row_count=state.row_count,
            reasoning_trace=trace,
            warnings=state.validation_warnings,
            is_meta_query=is_meta
        )
    
    def _abort(self, state: BatchPipelineState, reason: str) -> FinalResponse:
        """Abort execution with error response."""
        total_time = time.time() * 1000 - state.start_time_ms
        
        # Convert trace list to AgentAction objects
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
        
        # Add abort action
        abort_action = AgentAction(
            agent_name="Orchestrator",
            action="abort_query",
            input_summary="Pipeline state",
            output_summary=f"ABORTED: {reason}",
            reasoning=f"Query processing aborted: {reason}"
        )
        
        # Update existing reasoning_trace
        if state.reasoning_trace:
            state.reasoning_trace.actions.extend(trace_actions)
            state.reasoning_trace.actions.append(abort_action)
            state.reasoning_trace.total_time_ms = int(total_time)
            state.reasoning_trace.correction_attempts = state.retry_count
            state.reasoning_trace.final_status = ExecutionStatus.BLOCKED
            trace = state.reasoning_trace
        else:
            # Fallback if reasoning_trace wasn't initialized
            trace_actions.append(abort_action)
            trace = ReasoningTrace(
                user_query=state.user_query,
                actions=trace_actions,
                total_time_ms=int(total_time),
                correction_attempts=state.retry_count,
                final_status=ExecutionStatus.BLOCKED
            )
        
        return FinalResponse(
            answer=f"Query blocked: {reason}",
            sql_used="Not generated (query blocked)",
            row_count=0,
            reasoning_trace=trace,
            warnings=[reason]
        )
    
    def _abort_quota_exhausted(
        self,
        state: BatchPipelineState,
        error_message: str,
        provider_attempts: list
    ) -> FinalResponse:
        """
        Create graceful quota exhaustion response.
        
        Shows:
        - Clear user message about quota exhaustion
        - Provider attempt history in reasoning trace
        - Partial progress preserved
        - No hard crash, no partial SQL
        
        This is VISIBLE to judges in both CLI and UI.
        """
        total_time = time.time() * 1000 - state.start_time_ms
        
        # Build trace from existing actions
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
        
        # Add quota exhaustion info to reasoning trace
        provider_summary = "\\n".join([
            f"  • {attempt['provider'].title()}: {attempt['status']}" +
            (f" - {attempt['reason']}" if attempt.get('status') == 'failed' else "")
            for attempt in provider_attempts
        ])
        
        trace_actions.append(
            AgentAction(
                agent_name="QuotaManager",
                action="ABORTED_DUE_TO_QUOTA",
                input_summary=f"LLM quota exhausted after {len(provider_attempts)} provider attempts",
                output_summary=f"System gracefully aborted",
                reasoning=(
                    f"Provider fallback chain exhausted:\\n{provider_summary}\\n\\n"
                    f"All enabled LLM providers are temporarily unavailable. "
                    f"Please wait a few minutes for quota reset and retry."
                )
            )
        )
        
        trace = ReasoningTrace(
            user_query=state.user_query,
            actions=trace_actions,
            total_time_ms=int(total_time),
            correction_attempts=state.retry_count,
            final_status=ExecutionStatus.ERROR
        )
        
        return FinalResponse(
            answer=error_message,
            sql_used="",  # No partial SQL on quota exhaustion
            row_count=0,
            reasoning_trace=trace,
            warnings=["LLM quota exhausted", f"{len(provider_attempts)} providers attempted"]
        )


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def run_query(query: str, verbose: bool = VERBOSE) -> FinalResponse:
    """Run a query with the batch-optimized orchestrator."""
    orchestrator = BatchOptimizedOrchestrator(verbose=verbose)
    return orchestrator.process_query(query)
