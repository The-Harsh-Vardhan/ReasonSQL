"""
Deterministic State-Machine Orchestrator for NL2SQL Pipeline.

DESIGN PRINCIPLES:
==================
1. CENTRAL CONTROL: Orchestrator decides what runs next, not agents
2. EXPLICIT FLOW: Every branch is visible and documented
3. STRUCTURED I/O: Agents return typed outputs, orchestrator inspects status
4. NO AGENT-TO-AGENT CALLS: Agents never talk directly to each other
5. FULL TRACEABILITY: Every decision is logged with reasoning

EXECUTION FLOW:
===============
User Input
→ IntentAnalyzerAgent
→ if intent == AMBIGUOUS:
     ClarificationAgent (pause until resolved)
→ if intent == META_QUERY:
     SchemaExplorerAgent → ResponseSynthesizerAgent → END
→ SchemaExplorerAgent
→ if query is COMPLEX:
     QueryDecomposerAgent
→ if planner needs data context:
     DataExplorerAgent
→ QueryPlannerAgent
→ SQLGeneratorAgent
→ SafetyValidatorAgent  ← HARD GATE
→ SQLExecutorAgent
→ if execution fails OR empty result:
     SelfCorrectionAgent (max retries = 3)
     → QueryPlannerAgent → SQLGeneratorAgent → SafetyValidatorAgent → SQLExecutorAgent
→ ResultValidatorAgent
→ ResponseSynthesizerAgent
→ FINAL RESPONSE
"""
import time
import json
import re
from typing import Optional, Tuple, Dict, Any
from crewai import Crew, Process, Task, Agent

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
from models import FinalResponse, ReasoningTrace, AgentAction, ExecutionStatus
from agents import create_all_agents
from config import VERBOSE, MAX_RETRIES


# ============================================================
# STEP DEFINITIONS (State Machine States)
# ============================================================

class Step:
    """Pipeline step identifiers."""
    START = "START"
    INTENT_ANALYSIS = "INTENT_ANALYSIS"
    CLARIFICATION = "CLARIFICATION"
    SCHEMA_EXPLORATION = "SCHEMA_EXPLORATION"
    QUERY_DECOMPOSITION = "QUERY_DECOMPOSITION"
    DATA_EXPLORATION = "DATA_EXPLORATION"
    QUERY_PLANNING = "QUERY_PLANNING"
    SQL_GENERATION = "SQL_GENERATION"
    SAFETY_VALIDATION = "SAFETY_VALIDATION"
    SQL_EXECUTION = "SQL_EXECUTION"
    SELF_CORRECTION = "SELF_CORRECTION"
    RESULT_VALIDATION = "RESULT_VALIDATION"
    RESPONSE_SYNTHESIS = "RESPONSE_SYNTHESIS"
    END = "END"
    BLOCKED = "BLOCKED"


# ============================================================
# DETERMINISTIC ORCHESTRATOR
# ============================================================

class DeterministicOrchestrator:
    """
    State-machine orchestrator that controls the NL2SQL pipeline.
    
    KEY BEHAVIORS:
    1. Runs one agent at a time
    2. Inspects agent output to decide next step
    3. Maintains full pipeline state
    4. Enforces retry limits
    5. Blocks on safety failures
    6. Produces complete reasoning trace
    """
    
    def __init__(self, verbose: bool = VERBOSE):
        self.verbose = verbose
        self.agents: Dict[str, Agent] = create_all_agents()
    
    def _log(self, message: str):
        """Log if verbose mode is on."""
        if self.verbose:
            print(f"[ORCHESTRATOR] {message}")
    
    def process_query(self, user_query: str) -> FinalResponse:
        """
        Process a natural language query through the full pipeline.
        
        This is the main entry point. It:
        1. Initializes pipeline state
        2. Runs the state machine until END or BLOCKED
        3. Returns structured final response
        """
        # Initialize state
        state = PipelineState(
            user_query=user_query,
            current_step=Step.START,
            max_retries=MAX_RETRIES,
            start_time_ms=time.time() * 1000
        )
        
        self._log(f"{'='*60}")
        self._log(f"PROCESSING: {user_query}")
        self._log(f"{'='*60}")
        
        # Run state machine
        while state.current_step not in [Step.END, Step.BLOCKED]:
            state = self._execute_step(state)
        
        # Compute timing
        state.end_time_ms = time.time() * 1000
        total_time = state.end_time_ms - (state.start_time_ms or state.end_time_ms)
        
        # Build final response
        return self._build_final_response(state, total_time)
    
    def _execute_step(self, state: PipelineState) -> PipelineState:
        """
        Execute the current step and determine the next step.
        
        This is the state machine transition function.
        """
        current = state.current_step
        
        # ============================================
        # START → INTENT_ANALYSIS
        # ============================================
        if current == Step.START:
            self._log("→ Starting pipeline")
            state.current_step = Step.INTENT_ANALYSIS
            return state
        
        # ============================================
        # INTENT_ANALYSIS
        # Decision: AMBIGUOUS → CLARIFICATION
        #           META_QUERY → SCHEMA → RESPONSE → END
        #           DATA_QUERY → SCHEMA → continue
        # ============================================
        elif current == Step.INTENT_ANALYSIS:
            self._log("→ Step 1: Intent Analysis")
            output = self._run_intent_analyzer(state)
            state.intent_output = output
            
            state.add_trace(
                "IntentAnalyzer",
                "Classified query intent",
                f"Intent={output.intent.value}, Confidence={output.confidence}",
                output.reason
            )
            
            # DECISION: Route based on intent
            if output.intent == IntentType.AMBIGUOUS:
                self._log(f"  → Decision: AMBIGUOUS detected, routing to Clarification")
                state.current_step = Step.CLARIFICATION
            elif output.intent == IntentType.META_QUERY:
                self._log(f"  → Decision: META_QUERY, will handle with Schema + Response")
                state.current_step = Step.SCHEMA_EXPLORATION
            else:  # DATA_QUERY
                self._log(f"  → Decision: DATA_QUERY, proceeding to Schema Exploration")
                state.current_step = Step.SCHEMA_EXPLORATION
            
            return state
        
        # ============================================
        # CLARIFICATION (blocks until resolved)
        # ============================================
        elif current == Step.CLARIFICATION:
            self._log("→ Step 2: Clarification")
            output = self._run_clarification_agent(state)
            state.clarification_output = output
            
            state.add_trace(
                "ClarificationAgent",
                "Resolved ambiguous terms",
                f"Resolved: {list(output.resolved_terms.keys())}",
                f"Assumptions: {output.assumptions_made}"
            )
            
            # DECISION: If still ambiguous, we need to ask user
            if output.status == AgentStatus.AMBIGUOUS:
                self._log(f"  → Decision: Still ambiguous, cannot proceed")
                # In a real system, this would pause for user input
                # For now, we proceed with assumptions
                if output.assumptions_made:
                    self._log(f"  → Using assumptions: {output.assumptions_made}")
                    state.current_step = Step.SCHEMA_EXPLORATION
                else:
                    state.current_step = Step.BLOCKED
            else:
                state.current_step = Step.SCHEMA_EXPLORATION
            
            return state
        
        # ============================================
        # SCHEMA_EXPLORATION
        # ============================================
        elif current == Step.SCHEMA_EXPLORATION:
            self._log("→ Step 3: Schema Exploration")
            output = self._run_schema_explorer(state)
            state.schema_output = output
            
            state.add_trace(
                "SchemaExplorer",
                "Explored database schema",
                f"Found {len(output.tables)} tables",
                output.schema_summary[:100]
            )
            
            # DECISION: If META_QUERY, go straight to response
            if state.intent_output and state.intent_output.intent == IntentType.META_QUERY:
                self._log(f"  → Decision: META_QUERY handled, going to Response")
                state.current_step = Step.RESPONSE_SYNTHESIS
            # DECISION: Check if complex query needs decomposition
            elif state.intent_output and state.intent_output.is_complex:
                self._log(f"  → Decision: Complex query, routing to Decomposer")
                state.current_step = Step.QUERY_DECOMPOSITION
            # DECISION: Check if data context needed
            elif state.intent_output and state.intent_output.needs_data_context:
                self._log(f"  → Decision: Data context needed, routing to DataExplorer")
                state.current_step = Step.DATA_EXPLORATION
            else:
                self._log(f"  → Decision: Proceeding to Query Planning")
                state.current_step = Step.QUERY_PLANNING
            
            return state
        
        # ============================================
        # QUERY_DECOMPOSITION (optional)
        # ============================================
        elif current == Step.QUERY_DECOMPOSITION:
            self._log("→ Step 4: Query Decomposition")
            output = self._run_query_decomposer(state)
            state.decomposer_output = output
            
            state.add_trace(
                "QueryDecomposer",
                "Decomposed complex query",
                f"Steps: {len(output.steps)}, Approach: {output.recommended_approach}",
                output.complexity_reason
            )
            
            # DECISION: Check if data exploration needed after decomposition
            if state.intent_output and state.intent_output.needs_data_context:
                state.current_step = Step.DATA_EXPLORATION
            else:
                state.current_step = Step.QUERY_PLANNING
            
            return state
        
        # ============================================
        # DATA_EXPLORATION (optional)
        # ============================================
        elif current == Step.DATA_EXPLORATION:
            self._log("→ Step 5: Data Exploration")
            output = self._run_data_explorer(state)
            state.data_explorer_output = output
            
            state.add_trace(
                "DataExplorer",
                "Sampled data for context",
                f"Explored: {output.explored_tables}",
                "; ".join(output.insights[:3])
            )
            
            state.current_step = Step.QUERY_PLANNING
            return state
        
        # ============================================
        # QUERY_PLANNING
        # ============================================
        elif current == Step.QUERY_PLANNING:
            self._log("→ Step 6: Query Planning")
            output = self._run_query_planner(state)
            state.planner_output = output
            
            state.add_trace(
                "QueryPlanner",
                "Created query plan",
                f"Base: {output.base_table}, Joins: {len(output.joins)}, Limit: {output.limit}",
                output.reasoning[:100]
            )
            
            state.current_step = Step.SQL_GENERATION
            return state
        
        # ============================================
        # SQL_GENERATION
        # ============================================
        elif current == Step.SQL_GENERATION:
            self._log("→ Step 7: SQL Generation")
            output = self._run_sql_generator(state)
            state.generator_output = output
            
            state.add_trace(
                "SQLGenerator",
                "Generated SQL query",
                f"Uses CTE: {output.uses_cte}, Tables: {output.table_count}",
                output.sql[:100]
            )
            
            state.current_step = Step.SAFETY_VALIDATION
            return state
        
        # ============================================
        # SAFETY_VALIDATION (HARD GATE)
        # ============================================
        elif current == Step.SAFETY_VALIDATION:
            self._log("→ Step 8: Safety Validation [GATE]")
            output = self._run_safety_validator(state)
            state.safety_output = output
            
            state.add_trace(
                "SafetyValidator",
                "Validated SQL safety",
                f"Decision: {output.decision}",
                f"Violations: {output.violations}" if output.violations else "None"
            )
            
            # HARD GATE: If REJECTED, do not proceed
            if output.decision == "REJECTED":
                self._log(f"  ⛔ SAFETY GATE BLOCKED: {output.violations}")
                
                # If we can retry, go to self-correction
                if state.can_retry():
                    self._log(f"  → Routing to Self-Correction (retry {state.retry_count + 1}/{state.max_retries})")
                    state.increment_retry()
                    state.current_step = Step.SELF_CORRECTION
                else:
                    self._log(f"  → Max retries exceeded, BLOCKED")
                    state.current_step = Step.BLOCKED
            else:  # APPROVED
                self._log(f"  ✅ SAFETY GATE APPROVED")
                state.current_step = Step.SQL_EXECUTION
            
            return state
        
        # ============================================
        # SQL_EXECUTION
        # ============================================
        elif current == Step.SQL_EXECUTION:
            self._log("→ Step 9: SQL Execution")
            output = self._run_sql_executor(state)
            state.executor_output = output
            
            state.add_trace(
                "SQLExecutor",
                "Executed SQL",
                f"Status: {output.status.value}, Rows: {output.row_count}",
                output.error_message or "Success"
            )
            
            # DECISION: Check if execution succeeded
            if output.status == AgentStatus.ERROR or output.is_empty:
                self._log(f"  → Execution failed or empty: {output.error_message or 'Empty result'}")
                
                # If we can retry, go to self-correction
                if state.can_retry():
                    self._log(f"  → Routing to Self-Correction (retry {state.retry_count + 1}/{state.max_retries})")
                    state.increment_retry()
                    state.current_step = Step.SELF_CORRECTION
                else:
                    # Proceed anyway - let result validator and response handle it
                    self._log(f"  → Max retries exceeded, proceeding to validation")
                    state.current_step = Step.RESULT_VALIDATION
            else:
                state.current_step = Step.RESULT_VALIDATION
            
            return state
        
        # ============================================
        # SELF_CORRECTION (retry loop entry)
        # ============================================
        elif current == Step.SELF_CORRECTION:
            self._log(f"→ Step 10: Self-Correction (attempt {state.retry_count})")
            output = self._run_self_correction(state)
            state.correction_output = output
            
            state.add_trace(
                "SelfCorrection",
                "Analyzed failure and proposed fix",
                f"Should retry: {output.should_retry}, Skip to: {output.skip_to_step}",
                output.correction_strategy[:100]
            )
            
            # DECISION: Where to retry from
            if output.should_retry:
                if output.skip_to_step == "PLANNER":
                    state.current_step = Step.QUERY_PLANNING
                elif output.skip_to_step == "GENERATOR":
                    state.current_step = Step.SQL_GENERATION
                elif output.skip_to_step == "EXPLORER":
                    state.current_step = Step.DATA_EXPLORATION
                else:
                    state.current_step = Step.QUERY_PLANNING  # Default
            else:
                state.current_step = Step.BLOCKED
            
            return state
        
        # ============================================
        # RESULT_VALIDATION
        # ============================================
        elif current == Step.RESULT_VALIDATION:
            self._log("→ Step 11: Result Validation")
            output = self._run_result_validator(state)
            state.result_validator_output = output
            
            state.add_trace(
                "ResultValidator",
                "Validated result sanity",
                f"Valid: {output.is_valid}, Matches intent: {output.matches_intent}",
                "; ".join(output.anomalies_detected) or "No anomalies"
            )
            
            state.current_step = Step.RESPONSE_SYNTHESIS
            return state
        
        # ============================================
        # RESPONSE_SYNTHESIS
        # ============================================
        elif current == Step.RESPONSE_SYNTHESIS:
            self._log("→ Step 12: Response Synthesis")
            output = self._run_response_synthesizer(state)
            state.response_output = output
            
            state.add_trace(
                "ResponseSynthesizer",
                "Created human-readable response",
                f"Status: {output.status.value}",
                output.answer[:100]
            )
            
            state.current_step = Step.END
            return state
        
        # ============================================
        # END / BLOCKED (terminal states)
        # ============================================
        else:
            return state
    
    # ================================================================
    # AGENT EXECUTION METHODS
    # Each method runs ONE agent and returns STRUCTURED output
    # ================================================================
    
    def _run_intent_analyzer(self, state: PipelineState) -> IntentAnalyzerOutput:
        """Run IntentAnalyzer and return structured output."""
        task = Task(
            description=f"""
            Analyze the intent of this user query:
            
            "{state.user_query}"
            
            Classify as:
            - DATA_QUERY: User wants to retrieve data
            - META_QUERY: User wants schema/table information
            - AMBIGUOUS: Query is unclear (contains "recent", "best", "top" without specifics)
            
            Output a JSON with:
            {{
                "intent": "DATA_QUERY" | "META_QUERY" | "AMBIGUOUS",
                "confidence": 0.0-1.0,
                "relevant_tables": [],
                "relevant_columns": [],
                "is_complex": true/false,
                "needs_data_context": true/false,
                "ambiguous_terms": [],
                "reason": "..."
            }}
            """,
            expected_output="JSON object with intent classification",
            agent=self.agents["intent_analyzer"]
        )
        
        result = self._run_single_task(task)
        return self._parse_intent_output(result, state.user_query)
    
    def _run_clarification_agent(self, state: PipelineState) -> ClarificationOutput:
        """Run ClarificationAgent and return structured output."""
        ambiguous_terms = state.intent_output.ambiguous_terms if state.intent_output else []
        
        task = Task(
            description=f"""
            Resolve ambiguity in this query:
            
            "{state.user_query}"
            
            Ambiguous terms detected: {ambiguous_terms}
            
            For each ambiguous term, either:
            1. Ask a clarification question, OR
            2. Make a reasonable default assumption
            
            Output JSON:
            {{
                "resolved_terms": {{"term": "resolved_value"}},
                "assumptions_made": ["assumption 1", "assumption 2"],
                "clarification_questions": ["question if still unclear"],
                "refined_query": "query with ambiguity resolved"
            }}
            """,
            expected_output="JSON with resolved terms",
            agent=self.agents["clarification"]
        )
        
        result = self._run_single_task(task)
        return self._parse_clarification_output(result)
    
    def _run_schema_explorer(self, state: PipelineState) -> SchemaExplorerOutput:
        """Run SchemaExplorer and return structured output."""
        task = Task(
            description=f"""
            Explore the database schema to support this query:
            
            "{state.user_query}"
            
            Use the schema_inspector tool to get full schema.
            
            Output JSON:
            {{
                "tables": [{{"name": "...", "columns": [], "primary_key": "...", "row_count": N}}],
                "relationships": ["Table1.col -> Table2.col"],
                "relevant_tables_for_query": ["Table1", "Table2"],
                "schema_summary": "..."
            }}
            """,
            expected_output="JSON with schema information",
            agent=self.agents["schema_explorer"]
        )
        
        result = self._run_single_task(task)
        return self._parse_schema_output(result)
    
    def _run_query_decomposer(self, state: PipelineState) -> QueryDecomposerOutput:
        """Run QueryDecomposer and return structured output."""
        schema_context = state.schema_output.schema_summary if state.schema_output else ""
        
        task = Task(
            description=f"""
            Decompose this complex query into steps:
            
            "{state.user_query}"
            
            Schema context:
            {schema_context}
            
            Output JSON:
            {{
                "is_decomposed": true,
                "steps": [
                    {{"step_number": 1, "description": "...", "operation": "CTE|SUBQUERY|JOIN", "depends_on": []}}
                ],
                "recommended_approach": "CTE|SUBQUERY|MULTIPLE_QUERIES",
                "complexity_reason": "..."
            }}
            """,
            expected_output="JSON with decomposition steps",
            agent=self.agents["query_decomposer"]
        )
        
        result = self._run_single_task(task)
        return self._parse_decomposer_output(result)
    
    def _run_data_explorer(self, state: PipelineState) -> DataExplorerOutput:
        """Run DataExplorer and return structured output."""
        relevant_tables = state.schema_output.relevant_tables_for_query if state.schema_output else []
        
        task = Task(
            description=f"""
            Explore data in these tables to inform query planning:
            
            Query: "{state.user_query}"
            Tables: {relevant_tables}
            
            Use data_sampler tool to check value ranges, date ranges, distributions.
            
            Output JSON:
            {{
                "explored_tables": [],
                "date_ranges": {{"column": "min to max"}},
                "value_distributions": {{"column": ["value1", "value2"]}},
                "insights": ["insight 1", "insight 2"]
            }}
            """,
            expected_output="JSON with data exploration results",
            agent=self.agents["data_explorer"]
        )
        
        result = self._run_single_task(task)
        return self._parse_data_explorer_output(result)
    
    def _run_query_planner(self, state: PipelineState) -> QueryPlannerOutput:
        """Run QueryPlanner and return structured output."""
        # Build context from previous steps
        context_parts = []
        if state.schema_output:
            context_parts.append(f"Schema: {state.schema_output.schema_summary}")
        if state.decomposer_output:
            context_parts.append(f"Decomposition: {state.decomposer_output.recommended_approach}")
        if state.data_explorer_output:
            context_parts.append(f"Data insights: {state.data_explorer_output.insights}")
        if state.clarification_output:
            context_parts.append(f"Clarifications: {state.clarification_output.resolved_terms}")
        if state.correction_output:
            context_parts.append(f"Previous error: {state.correction_output.diagnosis}")
            context_parts.append(f"Correction strategy: {state.correction_output.correction_strategy}")
        
        context = "\n".join(context_parts)
        
        task = Task(
            description=f"""
            Create a query plan for:
            
            "{state.user_query}"
            
            Context:
            {context}
            
            CRITICAL RULES:
            - NO SELECT * (specify columns)
            - MUST include LIMIT
            - Use proper JOINs
            
            Output JSON:
            {{
                "base_table": "...",
                "select_columns": ["table.column"],
                "joins": [{{"table": "...", "join_type": "INNER", "on_condition": "..."}}],
                "filters": [{{"column": "...", "operator": "=", "value": "..."}}],
                "group_by": [],
                "order_by": [],
                "limit": 100,
                "reasoning": "..."
            }}
            """,
            expected_output="JSON query plan",
            agent=self.agents["query_planner"]
        )
        
        result = self._run_single_task(task)
        return self._parse_planner_output(result)
    
    def _run_sql_generator(self, state: PipelineState) -> SQLGeneratorOutput:
        """Run SQLGenerator and return structured output."""
        plan = state.planner_output
        
        task = Task(
            description=f"""
            Generate SQLite SQL from this plan:
            
            Base Table: {plan.base_table if plan else 'Unknown'}
            Columns: {plan.select_columns if plan else []}
            Joins: {[j.model_dump() for j in plan.joins] if plan else []}
            Filters: {[f.model_dump() for f in plan.filters] if plan else []}
            Group By: {plan.group_by if plan else []}
            Order By: {plan.order_by if plan else []}
            Limit: {plan.limit if plan else 100}
            
            Output ONLY the SQL query. No markdown, no explanation.
            """,
            expected_output="Raw SQL query only",
            agent=self.agents["sql_generator"]
        )
        
        result = self._run_single_task(task)
        sql = self._extract_sql(result)
        
        return SQLGeneratorOutput(
            status=AgentStatus.OK,
            reason="SQL generated from plan",
            sql=sql,
            uses_cte="WITH " in sql.upper(),
            table_count=sql.upper().count(" JOIN ") + 1
        )
    
    def _run_safety_validator(self, state: PipelineState) -> SafetyValidatorOutput:
        """Run SafetyValidator and return structured output (GATE)."""
        sql = state.generator_output.sql if state.generator_output else ""
        
        task = Task(
            description=f"""
            SAFETY VALIDATION - You are the FINAL gate before SQL execution.
            
            Validate this SQL:
            ```
            {sql}
            ```
            
            CHECK:
            1. Is it read-only? (no INSERT, UPDATE, DELETE, DROP, ALTER, CREATE)
            2. Does it have LIMIT?
            3. Does it have SELECT * ? (forbidden)
            4. Any other dangerous patterns?
            
            Output JSON:
            {{
                "decision": "APPROVED" or "REJECTED",
                "has_limit": true/false,
                "has_select_star": true/false,
                "is_read_only": true/false,
                "forbidden_keywords_found": [],
                "violations": [],
                "suggested_fixes": []
            }}
            
            You MUST output APPROVED or REJECTED. No other options.
            """,
            expected_output="JSON with APPROVED or REJECTED decision",
            agent=self.agents["safety_validator"]
        )
        
        result = self._run_single_task(task)
        return self._parse_safety_output(result, sql)
    
    def _run_sql_executor(self, state: PipelineState) -> SQLExecutorOutput:
        """Run SQLExecutor and return structured output."""
        sql = state.generator_output.sql if state.generator_output else ""
        
        task = Task(
            description=f"""
            Execute this SQL query:
            ```
            {sql}
            ```
            
            Use the sql_executor tool. Report results.
            
            Output JSON:
            {{
                "row_count": N,
                "column_names": [],
                "data": [{{...}}],
                "execution_time_ms": N,
                "error_message": null or "..."
            }}
            """,
            expected_output="JSON with execution results",
            agent=self.agents["sql_executor"]
        )
        
        result = self._run_single_task(task)
        return self._parse_executor_output(result, sql)
    
    def _run_self_correction(self, state: PipelineState) -> SelfCorrectionOutput:
        """Run SelfCorrection and return structured output."""
        # Gather error context
        error = ""
        if state.executor_output and state.executor_output.error_message:
            error = state.executor_output.error_message
        elif state.safety_output and state.safety_output.decision == "REJECTED":
            error = f"Safety violations: {state.safety_output.violations}"
        
        task = Task(
            description=f"""
            Analyze this failure and propose a fix:
            
            Query: "{state.user_query}"
            SQL attempted: {state.generator_output.sql if state.generator_output else 'N/A'}
            Error: {error}
            
            Diagnose what went wrong and how to fix it.
            
            Output JSON:
            {{
                "original_error": "...",
                "diagnosis": "...",
                "correction_strategy": "...",
                "should_retry": true/false,
                "skip_to_step": "PLANNER" | "GENERATOR" | "EXPLORER"
            }}
            """,
            expected_output="JSON with correction strategy",
            agent=self.agents["self_correction"]
        )
        
        result = self._run_single_task(task)
        return self._parse_correction_output(result, error)
    
    def _run_result_validator(self, state: PipelineState) -> ResultValidatorOutput:
        """Run ResultValidator and return structured output."""
        exec_output = state.executor_output
        
        task = Task(
            description=f"""
            Validate these query results:
            
            Query: "{state.user_query}"
            Row count: {exec_output.row_count if exec_output else 0}
            Columns: {exec_output.column_names if exec_output else []}
            Data sample: {exec_output.data[:5] if exec_output else []}
            
            Check for:
            - Negative values where inappropriate
            - Unexpected NULLs
            - Results that don't match the question
            
            Output JSON:
            {{
                "is_valid": true/false,
                "anomalies_detected": [],
                "warnings": [],
                "matches_intent": true/false,
                "confidence": 0.0-1.0
            }}
            """,
            expected_output="JSON with validation results",
            agent=self.agents["result_validator"]
        )
        
        result = self._run_single_task(task)
        return self._parse_result_validator_output(result)
    
    def _run_response_synthesizer(self, state: PipelineState) -> ResponseSynthesizerOutput:
        """Run ResponseSynthesizer and return structured output."""
        # Handle META_QUERY specially
        if state.intent_output and state.intent_output.intent == IntentType.META_QUERY:
            schema_summary = state.schema_output.schema_summary if state.schema_output else ""
            task = Task(
                description=f"""
                Answer this meta-query about the database:
                
                "{state.user_query}"
                
                Schema information:
                {schema_summary}
                
                Create a clear, helpful answer.
                """,
                expected_output="Human-readable answer",
                agent=self.agents["response_synthesizer"]
            )
        else:
            exec_output = state.executor_output
            task = Task(
                description=f"""
                Create a human-readable answer:
                
                Query: "{state.user_query}"
                SQL used: {state.generator_output.sql if state.generator_output else 'N/A'}
                Row count: {exec_output.row_count if exec_output else 0}
                Data: {exec_output.data[:10] if exec_output else []}
                
                Create a clear, natural answer that directly addresses the question.
                """,
                expected_output="Human-readable answer",
                agent=self.agents["response_synthesizer"]
            )
        
        result = self._run_single_task(task)
        
        return ResponseSynthesizerOutput(
            status=AgentStatus.OK,
            reason="Response synthesized",
            answer=result,
            explanation=f"Answered using {state.executor_output.row_count if state.executor_output else 0} rows"
        )
    
    # ================================================================
    # HELPER METHODS
    # ================================================================
    
    def _run_single_task(self, task: Task) -> str:
        """Execute a single task and return raw string output."""
        crew = Crew(
            agents=[task.agent],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose
        )
        result = crew.kickoff()
        return str(result)
    
    def _extract_sql(self, text: str) -> str:
        """Extract SQL from text output."""
        # Try markdown code block
        match = re.search(r'```(?:sql)?\s*(.+?)\s*```', text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # Try to find SELECT or WITH statement
        match = re.search(r'((?:WITH|SELECT)\s+.+?;)', text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        
        return text.strip()
    
    def _parse_json_from_text(self, text: str) -> Dict[str, Any]:
        """Try to parse JSON from text that may contain other content."""
        # Try direct parse
        try:
            return json.loads(text)
        except:
            pass
        
        # Try to find JSON in text
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        
        return {}
    
    # ================================================================
    # OUTPUT PARSING (text → structured)
    # ================================================================
    
    def _parse_intent_output(self, text: str, query: str) -> IntentAnalyzerOutput:
        """Parse IntentAnalyzer text to structured output."""
        data = self._parse_json_from_text(text)
        
        # Determine intent
        intent_str = data.get("intent", "DATA_QUERY").upper()
        if "META" in intent_str:
            intent = IntentType.META_QUERY
        elif "AMBIG" in intent_str:
            intent = IntentType.AMBIGUOUS
        else:
            intent = IntentType.DATA_QUERY
        
        # Also detect from text
        if "AMBIGUOUS" in text.upper() and intent != IntentType.AMBIGUOUS:
            intent = IntentType.AMBIGUOUS
        
        # Detect complexity indicators
        is_complex = data.get("is_complex", False)
        if not is_complex:
            complex_patterns = ["both", "either", "compare", "difference", "never"]
            is_complex = any(p in query.lower() for p in complex_patterns)
        
        # Detect data context needs
        needs_context = data.get("needs_data_context", False)
        if not needs_context:
            context_patterns = ["recent", "latest", "high", "low", "average", "range"]
            needs_context = any(p in query.lower() for p in context_patterns)
        
        status = AgentStatus.AMBIGUOUS if intent == IntentType.AMBIGUOUS else AgentStatus.OK
        
        return IntentAnalyzerOutput(
            status=status,
            reason=data.get("reason", f"Classified as {intent.value}"),
            intent=intent,
            confidence=data.get("confidence", 0.8),
            relevant_tables=data.get("relevant_tables", []),
            relevant_columns=data.get("relevant_columns", []),
            is_complex=is_complex,
            needs_data_context=needs_context,
            ambiguous_terms=data.get("ambiguous_terms", [])
        )
    
    def _parse_clarification_output(self, text: str) -> ClarificationOutput:
        """Parse ClarificationAgent text to structured output."""
        data = self._parse_json_from_text(text)
        
        resolved = data.get("resolved_terms", {})
        assumptions = data.get("assumptions_made", [])
        questions = data.get("clarification_questions", [])
        
        # If we have resolutions or assumptions, we're OK
        # If only questions, we're still AMBIGUOUS
        if resolved or assumptions:
            status = AgentStatus.OK
        else:
            status = AgentStatus.AMBIGUOUS
        
        return ClarificationOutput(
            status=status,
            reason="Ambiguity resolved with assumptions" if assumptions else "Clarification needed",
            resolved_terms=resolved,
            assumptions_made=assumptions,
            clarification_questions=questions,
            refined_query=data.get("refined_query")
        )
    
    def _parse_schema_output(self, text: str) -> SchemaExplorerOutput:
        """Parse SchemaExplorer text to structured output."""
        data = self._parse_json_from_text(text)
        
        tables = []
        for t in data.get("tables", []):
            if isinstance(t, dict):
                tables.append(TableSchema(
                    name=t.get("name", "unknown"),
                    columns=t.get("columns", []),
                    primary_key=t.get("primary_key"),
                    row_count=t.get("row_count")
                ))
        
        return SchemaExplorerOutput(
            status=AgentStatus.OK,
            reason="Schema explored",
            tables=tables,
            relationships=data.get("relationships", []),
            relevant_tables_for_query=data.get("relevant_tables_for_query", []),
            schema_summary=data.get("schema_summary", text[:500])
        )
    
    def _parse_decomposer_output(self, text: str) -> QueryDecomposerOutput:
        """Parse QueryDecomposer text to structured output."""
        data = self._parse_json_from_text(text)
        
        return QueryDecomposerOutput(
            status=AgentStatus.OK,
            reason="Query decomposed",
            is_decomposed=data.get("is_decomposed", True),
            steps=[],  # Simplified
            recommended_approach=data.get("recommended_approach", "SIMPLE"),
            complexity_reason=data.get("complexity_reason", "")
        )
    
    def _parse_data_explorer_output(self, text: str) -> DataExplorerOutput:
        """Parse DataExplorer text to structured output."""
        data = self._parse_json_from_text(text)
        
        return DataExplorerOutput(
            status=AgentStatus.OK,
            reason="Data explored",
            explored_tables=data.get("explored_tables", []),
            date_ranges=data.get("date_ranges", {}),
            value_distributions=data.get("value_distributions", {}),
            insights=data.get("insights", [])
        )
    
    def _parse_planner_output(self, text: str) -> QueryPlannerOutput:
        """Parse QueryPlanner text to structured output."""
        data = self._parse_json_from_text(text)
        
        return QueryPlannerOutput(
            status=AgentStatus.OK,
            reason="Plan created",
            base_table=data.get("base_table", ""),
            select_columns=data.get("select_columns", []),
            joins=[],  # Simplified
            filters=[],  # Simplified
            group_by=data.get("group_by", []),
            order_by=data.get("order_by", []),
            limit=data.get("limit", 100),
            reasoning=data.get("reasoning", "")
        )
    
    def _parse_safety_output(self, text: str, sql: str) -> SafetyValidatorOutput:
        """Parse SafetyValidator text to structured output."""
        data = self._parse_json_from_text(text)
        
        # Extract decision - default to REJECTED if unclear
        decision = "REJECTED"
        if data.get("decision") == "APPROVED" or "APPROVED" in text.upper():
            if "REJECTED" not in text.upper() or text.upper().find("APPROVED") > text.upper().find("REJECTED"):
                decision = "APPROVED"
        
        # Also do our own validation
        sql_upper = sql.upper()
        has_limit = "LIMIT" in sql_upper
        has_select_star = bool(re.search(r'SELECT\s+\*', sql_upper))
        forbidden = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE"]
        found_forbidden = [kw for kw in forbidden if kw in sql_upper]
        is_read_only = len(found_forbidden) == 0
        
        # Override decision based on actual validation
        violations = []
        if not has_limit:
            violations.append("Missing LIMIT clause")
        if has_select_star:
            violations.append("SELECT * is not allowed")
        if not is_read_only:
            violations.append(f"Forbidden keywords: {found_forbidden}")
        
        if violations:
            decision = "REJECTED"
        
        status = AgentStatus.OK if decision == "APPROVED" else AgentStatus.BLOCKED
        
        return SafetyValidatorOutput(
            status=status,
            reason=f"Safety check: {decision}",
            decision=decision,
            has_limit=has_limit,
            has_select_star=has_select_star,
            is_read_only=is_read_only,
            forbidden_keywords_found=found_forbidden,
            violations=violations,
            suggested_fixes=data.get("suggested_fixes", [])
        )
    
    def _parse_executor_output(self, text: str, sql: str) -> SQLExecutorOutput:
        """Parse SQLExecutor text to structured output."""
        data = self._parse_json_from_text(text)
        
        # Check for errors in text
        has_error = "error" in text.lower() and "no error" not in text.lower()
        is_empty = data.get("row_count", 0) == 0 or "0 rows" in text.lower() or "empty" in text.lower()
        
        error_msg = None
        if has_error:
            # Try to extract error message
            match = re.search(r'(?:error|Error|ERROR)[:\s]+(.+?)(?:\n|$)', text)
            if match:
                error_msg = match.group(1).strip()
        
        status = AgentStatus.OK
        if error_msg:
            status = AgentStatus.ERROR
        
        return SQLExecutorOutput(
            status=status,
            reason="Query executed" if not error_msg else f"Error: {error_msg}",
            sql_executed=sql,
            row_count=data.get("row_count", 0),
            column_names=data.get("column_names", []),
            data=data.get("data", []),
            execution_time_ms=data.get("execution_time_ms", 0),
            error_message=error_msg,
            is_empty=is_empty
        )
    
    def _parse_correction_output(self, text: str, error: str) -> SelfCorrectionOutput:
        """Parse SelfCorrection text to structured output."""
        data = self._parse_json_from_text(text)
        
        return SelfCorrectionOutput(
            status=AgentStatus.RETRY,
            reason="Correction strategy identified",
            original_error=error,
            diagnosis=data.get("diagnosis", "Unknown issue"),
            correction_strategy=data.get("correction_strategy", "Retry with adjustments"),
            should_retry=data.get("should_retry", True),
            skip_to_step=data.get("skip_to_step", "PLANNER")
        )
    
    def _parse_result_validator_output(self, text: str) -> ResultValidatorOutput:
        """Parse ResultValidator text to structured output."""
        data = self._parse_json_from_text(text)
        
        return ResultValidatorOutput(
            status=AgentStatus.OK,
            reason="Results validated",
            is_valid=data.get("is_valid", True),
            anomalies_detected=data.get("anomalies_detected", []),
            warnings=data.get("warnings", []),
            matches_intent=data.get("matches_intent", True),
            confidence=data.get("confidence", 0.9)
        )
    
    # ================================================================
    # FINAL RESPONSE BUILDER
    # ================================================================
    
    def _build_final_response(self, state: PipelineState, total_time_ms: float) -> FinalResponse:
        """Build the final response from pipeline state."""
        # Determine final status
        if state.current_step == Step.BLOCKED:
            status = ExecutionStatus.VALIDATION_FAILED
        elif state.executor_output and state.executor_output.is_empty:
            status = ExecutionStatus.EMPTY
        elif state.executor_output and state.executor_output.error_message:
            status = ExecutionStatus.ERROR
        else:
            status = ExecutionStatus.SUCCESS
        
        # Get answer
        answer = "Unable to process query"
        if state.response_output:
            answer = state.response_output.answer
        elif state.current_step == Step.BLOCKED:
            if state.safety_output:
                answer = f"Query blocked by safety validator: {state.safety_output.violations}"
            else:
                answer = "Query processing was blocked"
        
        # Get SQL
        sql = "N/A"
        if state.generator_output:
            sql = state.generator_output.sql
        
        # Build reasoning trace
        actions = []
        for trace_entry in state.trace:
            actions.append(AgentAction(
                agent_name=trace_entry["agent"],
                action=trace_entry["action"],
                input_summary=trace_entry["decision"],
                output_summary=trace_entry["output_summary"],
                reasoning=trace_entry["decision"]
            ))
        
        reasoning_trace = ReasoningTrace(
            user_query=state.user_query,
            actions=actions,
            total_time_ms=total_time_ms,
            correction_attempts=state.retry_count,
            final_status=status
        )
        
        # Collect warnings
        warnings = []
        if state.retry_count > 0:
            warnings.append(f"Required {state.retry_count} correction attempts")
        if state.result_validator_output and state.result_validator_output.warnings:
            warnings.extend(state.result_validator_output.warnings)
        if state.clarification_output and state.clarification_output.assumptions_made:
            warnings.append(f"Assumptions made: {state.clarification_output.assumptions_made}")
        
        return FinalResponse(
            answer=answer,
            sql_used=sql,
            reasoning_trace=reasoning_trace,
            data_preview=state.executor_output.data[:10] if state.executor_output else None,
            row_count=state.executor_output.row_count if state.executor_output else 0,
            warnings=warnings
        )


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def run_query(query: str, verbose: bool = True) -> FinalResponse:
    """Run a query through the deterministic orchestrator."""
    orchestrator = DeterministicOrchestrator(verbose=verbose)
    return orchestrator.process_query(query)


# Alias for backward compatibility
NL2SQLOrchestrator = DeterministicOrchestrator
