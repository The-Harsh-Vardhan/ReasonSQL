"""
Enhanced Orchestration Logic for ReasonSQL Multi-Agent System.
Incorporates all 12 agents with proper flow control.

EXECUTION FLOW:
==============
User Input
→ IntentAnalyzerAgent (classify query type)
→ (if ambiguous) ClarificationAgent
→ SchemaExplorerAgent
→ (if complex) QueryDecomposerAgent
→ (if needs data context) DataExplorerAgent
→ QueryPlannerAgent
→ SQLGeneratorAgent
→ SafetyValidatorAgent (GATE - must pass)
→ SQLExecutorAgent
→ (on failure) SelfCorrectionAgent → retry loop
→ ResultValidatorAgent
→ ResponseSynthesizerAgent
→ Final Response

"""
import time
import re
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any
from crewai import Crew, Process, Task

from backend.agents import create_all_agents
from backend.tasks import (
    # Core tasks
    create_schema_exploration_task,
    create_intent_analysis_task,
    create_query_planning_task,
    create_sql_generation_task,
    create_sql_execution_task,
    create_self_correction_task,
    create_response_synthesis_task,
    create_meta_query_task,
    # New tasks
    create_clarification_task,
    create_safety_validation_task,
    create_query_decomposition_task,
    create_data_exploration_task,
    create_result_validation_task
)
from backend.models import (
    QueryIntent, ExecutionStatus, AgentAction, ReasoningTrace, FinalResponse
)
from configs import MAX_RETRIES, VERBOSE


# ============================================================
# AMBIGUOUS TERM DETECTION
# ============================================================

AMBIGUOUS_PATTERNS = {
    "temporal": [
        r'\brecent\b', r'\blatest\b', r'\blast\b', r'\bnew\b', r'\bold\b',
        r'\bthis week\b', r'\bthis month\b', r'\bthis year\b'
    ],
    "quantitative": [
        r'\bbest\b', r'\btop\b', r'\bmost\b', r'\bhighest\b', r'\blowest\b',
        r'\bpopular\b', r'\bfavorite\b', r'\bworst\b'
    ],
    "scope": [
        r'\bsome\b', r'\bfew\b', r'\bmany\b', r'\bseveral\b'
    ]
}


def detect_ambiguous_terms(query: str) -> List[str]:
    """Detect ambiguous terms in the query."""
    found_terms = []
    query_lower = query.lower()
    
    for category, patterns in AMBIGUOUS_PATTERNS.items():
        for pattern in patterns:
            matches = re.findall(pattern, query_lower)
            found_terms.extend(matches)
    
    return list(set(found_terms))


def is_complex_query(query: str) -> bool:
    """Detect if query requires decomposition."""
    complexity_indicators = [
        r'\bboth\b.*\band\b',           # "both X and Y"
        r'\beither\b.*\bor\b',          # "either X or Y"
        r'\bbut not\b',                  # "X but not Y"
        r'\bnever\b',                    # negation
        r'\bcompare\b',                  # comparison
        r'\bdifference\b',               # difference
        r'\bintersect\b',                # set operations
        r'\bcross\b',                    # cross-reference
        r'\bwho.*also\b',               # multi-condition
        r'\bcustomers who purchased.*and\b',  # complex joins
    ]
    
    query_lower = query.lower()
    for pattern in complexity_indicators:
        if re.search(pattern, query_lower):
            return True
    return False


# ============================================================
# REASONING TRACE COLLECTOR
# ============================================================

class ReasoningTraceCollector:
    """Collects and formats the reasoning trace from agent actions."""
    
    def __init__(self):
        self.actions: List[AgentAction] = []
        self.start_time: Optional[float] = None
        self.decisions: List[Dict[str, Any]] = []  # Track key decisions
    
    def start(self):
        """Mark the start of processing."""
        self.start_time = time.time()
        self.actions = []
        self.decisions = []
    
    def add_action(self, agent_name: str, action: str, 
                   input_summary: str, output_summary: str, 
                   reasoning: Optional[str] = None,
                   decision: Optional[str] = None):
        """Add an agent action to the trace."""
        self.actions.append(AgentAction(
            agent_name=agent_name,
            action=action,
            input_summary=input_summary,
            output_summary=output_summary,
            reasoning=reasoning,
            timestamp=datetime.now().strftime("%H:%M:%S")
        ))
        
        if decision:
            self.decisions.append({
                "agent": agent_name,
                "decision": decision,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
    
    def add_decision(self, agent_name: str, decision: str, reason: str):
        """Record a key decision point."""
        self.decisions.append({
            "agent": agent_name,
            "decision": decision,
            "reason": reason,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time in milliseconds."""
        if self.start_time:
            return (time.time() - self.start_time) * 1000
        return 0
    
    def get_summary(self) -> str:
        """Get a formatted summary of the reasoning trace."""
        lines = ["=" * 60]
        lines.append("REASONING TRACE")
        lines.append("=" * 60)
        lines.append("")
        
        # Key decisions first
        if self.decisions:
            lines.append("KEY DECISIONS:")
            for d in self.decisions:
                lines.append(f"  [{d['timestamp']}] {d['agent']}: {d['decision']}")
            lines.append("")
        
        # Then detailed actions
        lines.append("AGENT ACTIONS:")
        for i, action in enumerate(self.actions, 1):
            lines.append(f"\nStep {i}: {action.agent_name}")
            lines.append(f"  Action: {action.action}")
            lines.append(f"  Input: {action.input_summary[:150]}{'...' if len(action.input_summary) > 150 else ''}")
            lines.append(f"  Output: {action.output_summary[:150]}{'...' if len(action.output_summary) > 150 else ''}")
            if action.reasoning:
                lines.append(f"  Reasoning: {action.reasoning[:150]}{'...' if len(action.reasoning) > 150 else ''}")
        
        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)


# ============================================================
# ENHANCED ORCHESTRATOR
# ============================================================

class EnhancedReasonSQLOrchestrator:
    """
    Enhanced orchestrator with all 12 agents.
    
    AGENT INVENTORY:
    ================
    Core (7):
    1. schema_explorer - Database structure inspection
    2. intent_analyzer - Query classification
    3. query_planner - SQL plan design
    4. sql_generator - SQL code generation
    5. sql_executor - Safe execution
    6. self_correction - Error recovery
    7. response_synthesizer - Human-readable output
    
    New (5):
    8. clarification - Ambiguity resolution
    9. safety_validator - Pre-execution safety gate
    10. query_decomposer - Complex query breakdown
    11. data_explorer - Data sampling
    12. result_validator - Output sanity checking
    
    EXECUTION FLOW:
    ===============
    1. Intent Analysis → determine query type
    2. Clarification (if ambiguous) → resolve vague terms
    3. Schema Exploration → understand database
    4. Query Decomposition (if complex) → break into steps
    5. Data Exploration (if needed) → sample data for context
    6. Query Planning → design the SQL
    7. SQL Generation → create the SQL
    8. Safety Validation → GATE - approve or reject
    9. SQL Execution → run the query
    10. Self-Correction (on failure) → retry with fixes
    11. Result Validation → sanity check results
    12. Response Synthesis → create human answer
    """
    
    def __init__(self, verbose: bool = VERBOSE):
        self.verbose = verbose
        self.agents = create_all_agents()
        self.trace_collector = ReasoningTraceCollector()
    
    def _log(self, message: str):
        """Log message if verbose mode is on."""
        if self.verbose:
            print(message)
    
    def process_query(self, user_query: str) -> FinalResponse:
        """
        Process a natural language query through all agents.
        
        Args:
            user_query: The natural language question from the user
            
        Returns:
            FinalResponse with answer, SQL, and reasoning trace
        """
        self.trace_collector.start()
        
        self._log(f"\n{'='*60}")
        self._log(f"PROCESSING: {user_query}")
        self._log(f"{'='*60}\n")
        
        # Step 1: Intent Analysis
        intent_result = self._analyze_intent(user_query)
        
        # Step 2: Check for ambiguity and clarify
        ambiguous_terms = detect_ambiguous_terms(user_query)
        clarification_result = None
        if ambiguous_terms or self._is_ambiguous(intent_result):
            clarification_result = self._clarify_ambiguity(user_query, ambiguous_terms)
            if self._needs_user_input(clarification_result):
                return self._request_clarification_response(user_query, clarification_result)
        
        # Step 3: Check if meta-query
        if self._is_meta_query(intent_result):
            return self._handle_meta_query(user_query)
        
        # Step 4: Schema Exploration
        schema_result = self._explore_schema(user_query)
        
        # Step 5: Query Decomposition (for complex queries)
        decomposition_result = None
        if is_complex_query(user_query):
            decomposition_result = self._decompose_query(user_query, schema_result)
        
        # Step 6: Data Exploration (if needed for context)
        data_context = None
        if ambiguous_terms or self._needs_data_context(user_query):
            data_context = self._explore_data(user_query, schema_result)
        
        # Step 7-10: Query Planning → Generation → Safety → Execution (with retry)
        sql, execution_result, correction_attempts = self._execute_query_pipeline(
            user_query, schema_result, decomposition_result, data_context, clarification_result
        )
        
        # Step 11: Result Validation
        validation_result = self._validate_results(user_query, sql, execution_result)
        
        # Step 12: Response Synthesis
        final_response = self._synthesize_response(
            user_query, sql, execution_result, validation_result, correction_attempts
        )
        
        return final_response
    
    # ========================================
    # STEP 1: Intent Analysis
    # ========================================
    
    def _analyze_intent(self, user_query: str) -> str:
        """Analyze the intent of the user query."""
        self._log("🎯 Step 1: Analyzing query intent...")
        
        task = create_intent_analysis_task(
            self.agents["intent_analyzer"],
            user_query,
            None  # No schema context yet
        )
        
        # For intent analysis, we don't need schema context
        task.context = []
        
        crew = Crew(
            agents=[self.agents["intent_analyzer"]],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        result_str = str(result)
        
        self.trace_collector.add_action(
            agent_name="IntentAnalyzer",
            action="Classified query intent",
            input_summary=f"Query: {user_query}",
            output_summary=result_str[:200],
            decision=self._extract_intent_type(result_str)
        )
        
        return result_str
    
    def _extract_intent_type(self, result: str) -> str:
        """Extract intent type from result."""
        result_lower = result.lower()
        if "meta_query" in result_lower:
            return "META_QUERY"
        elif "ambiguous" in result_lower:
            return "AMBIGUOUS"
        else:
            return "DATA_QUERY"
    
    def _is_meta_query(self, intent_result: str) -> bool:
        """Check if query is about database structure."""
        return "meta_query" in intent_result.lower()
    
    def _is_ambiguous(self, intent_result: str) -> bool:
        """Check if intent analysis flagged ambiguity."""
        return "ambiguous" in intent_result.lower() and "clarification" in intent_result.lower()
    
    # ========================================
    # STEP 2: Clarification
    # ========================================
    
    def _clarify_ambiguity(self, user_query: str, ambiguous_terms: List[str]) -> str:
        """Resolve ambiguous terms in the query."""
        self._log(f"❓ Step 2: Clarifying ambiguous terms: {ambiguous_terms}")
        
        task = create_clarification_task(
            self.agents["clarification"],
            user_query,
            ambiguous_terms
        )
        
        crew = Crew(
            agents=[self.agents["clarification"]],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        result_str = str(result)
        
        self.trace_collector.add_action(
            agent_name="ClarificationAgent",
            action="Analyzed ambiguous terms",
            input_summary=f"Terms: {ambiguous_terms}",
            output_summary=result_str[:200],
            reasoning="Resolving vague terms before query planning"
        )
        
        self.trace_collector.add_decision(
            "ClarificationAgent",
            "Proceeding with assumptions" if "default" in result_str.lower() else "Clarification provided",
            f"Ambiguous terms: {ambiguous_terms}"
        )
        
        return result_str
    
    def _needs_user_input(self, clarification_result: str) -> bool:
        """Check if we need to ask the user for input."""
        result_lower = clarification_result.lower()
        return "wait for clarification" in result_lower or "cannot proceed" in result_lower
    
    def _request_clarification_response(self, user_query: str, clarification_result: str) -> FinalResponse:
        """Return a response asking for clarification."""
        return FinalResponse(
            answer=f"I need some clarification to answer your question accurately:\n\n{clarification_result}",
            sql_used="N/A (clarification needed)",
            reasoning_trace=ReasoningTrace(
                user_query=user_query,
                actions=self.trace_collector.actions,
                total_time_ms=self.trace_collector.get_elapsed_time(),
                correction_attempts=0,
                final_status=ExecutionStatus.VALIDATION_FAILED
            ),
            row_count=0,
            warnings=["Query requires clarification before proceeding"]
        )
    
    # ========================================
    # STEP 3: Meta-Query Handling
    # ========================================
    
    def _handle_meta_query(self, user_query: str) -> FinalResponse:
        """Handle meta-queries about database structure."""
        self._log("📋 Handling meta-query...")
        
        task = create_meta_query_task(
            self.agents["schema_explorer"],
            user_query
        )
        
        crew = Crew(
            agents=[self.agents["schema_explorer"]],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        result_str = str(result)
        
        self.trace_collector.add_action(
            agent_name="SchemaExplorer",
            action="Answered meta-query",
            input_summary=f"Query: {user_query}",
            output_summary=result_str[:200]
        )
        
        return FinalResponse(
            answer=result_str,
            sql_used="N/A (meta-query - used schema inspection)",
            reasoning_trace=ReasoningTrace(
                user_query=user_query,
                actions=self.trace_collector.actions,
                total_time_ms=self.trace_collector.get_elapsed_time(),
                correction_attempts=0,
                final_status=ExecutionStatus.SUCCESS
            ),
            row_count=0
        )
    
    # ========================================
    # STEP 4: Schema Exploration
    # ========================================
    
    def _explore_schema(self, user_query: str) -> str:
        """Explore the database schema."""
        self._log("📊 Step 4: Exploring database schema...")
        
        task = create_schema_exploration_task(
            self.agents["schema_explorer"],
            user_query
        )
        
        crew = Crew(
            agents=[self.agents["schema_explorer"]],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        result_str = str(result)
        
        self.trace_collector.add_action(
            agent_name="SchemaExplorer",
            action="Explored database schema",
            input_summary=f"Query: {user_query}",
            output_summary=result_str[:200]
        )
        
        return result_str
    
    # ========================================
    # STEP 5: Query Decomposition
    # ========================================
    
    def _decompose_query(self, user_query: str, schema_context: str) -> str:
        """Decompose complex query into steps."""
        self._log("🔧 Step 5: Decomposing complex query...")
        
        task = create_query_decomposition_task(
            self.agents["query_decomposer"],
            user_query,
            schema_context
        )
        
        crew = Crew(
            agents=[self.agents["query_decomposer"]],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        result_str = str(result)
        
        self.trace_collector.add_action(
            agent_name="QueryDecomposer",
            action="Decomposed complex query",
            input_summary=f"Query: {user_query}",
            output_summary=result_str[:200],
            reasoning="Breaking down multi-step query into atomic operations"
        )
        
        self.trace_collector.add_decision(
            "QueryDecomposer",
            "Query decomposed into steps",
            "Complex query detected - required multi-step approach"
        )
        
        return result_str
    
    # ========================================
    # STEP 6: Data Exploration
    # ========================================
    
    def _needs_data_context(self, user_query: str) -> bool:
        """Check if we need to sample data for context."""
        context_indicators = [
            r'\brecent\b', r'\bhigh\b', r'\blow\b', r'\baverage\b',
            r'\brange\b', r'\bdistribution\b', r'\bexist\b'
        ]
        query_lower = user_query.lower()
        return any(re.search(p, query_lower) for p in context_indicators)
    
    def _explore_data(self, user_query: str, schema_context: str) -> str:
        """Explore data to inform query decisions."""
        self._log("🔍 Step 6: Exploring data for context...")
        
        # Extract likely relevant tables/columns from query and schema
        tables = self._extract_table_names(schema_context, user_query)
        columns = []  # Could be enhanced to extract column names
        
        task = create_data_exploration_task(
            self.agents["data_explorer"],
            user_query,
            tables,
            columns
        )
        
        crew = Crew(
            agents=[self.agents["data_explorer"]],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        result_str = str(result)
        
        self.trace_collector.add_action(
            agent_name="DataExplorer",
            action="Sampled data for context",
            input_summary=f"Tables: {tables}",
            output_summary=result_str[:200],
            reasoning="Gathering actual data ranges to resolve ambiguity"
        )
        
        return result_str
    
    def _extract_table_names(self, schema_context: str, user_query: str) -> List[str]:
        """Extract relevant table names from schema and query."""
        # Simple extraction - look for table names mentioned in schema
        tables = []
        common_tables = ['Customer', 'Invoice', 'Track', 'Album', 'Artist', 
                        'Genre', 'Playlist', 'Employee', 'MediaType']
        
        query_lower = user_query.lower()
        schema_lower = schema_context.lower()
        
        for table in common_tables:
            if table.lower() in query_lower or table.lower() in schema_lower:
                tables.append(table)
        
        return tables[:3]  # Limit to 3 most relevant
    
    # ========================================
    # STEPS 7-10: Query Pipeline with Safety Gate
    # ========================================
    
    def _execute_query_pipeline(self, user_query: str, schema_result: str,
                                 decomposition_result: Optional[str],
                                 data_context: Optional[str],
                                 clarification_result: Optional[str]) -> Tuple[str, str, int]:
        """
        Execute the query pipeline with safety validation and retry.
        
        Returns:
            Tuple of (final_sql, execution_result, correction_attempts)
        """
        correction_attempts = 0
        last_error = ""
        
        # Build enhanced context
        context_parts = [f"Schema:\n{schema_result}"]
        if decomposition_result:
            context_parts.append(f"\nQuery Decomposition:\n{decomposition_result}")
        if data_context:
            context_parts.append(f"\nData Context:\n{data_context}")
        if clarification_result:
            context_parts.append(f"\nClarification:\n{clarification_result}")
        
        full_context = "\n".join(context_parts)
        
        while correction_attempts <= MAX_RETRIES:
            # Step 7: Query Planning
            self._log(f"\n📝 Step 7: Planning query (attempt {correction_attempts + 1})...")
            query_plan = self._plan_query(user_query, full_context, last_error)
            
            # Step 8: SQL Generation
            self._log("⚙️ Step 8: Generating SQL...")
            sql = self._generate_sql(user_query, query_plan)
            
            # Step 9: Safety Validation (GATE)
            self._log("🔒 Step 9: Safety validation...")
            safety_result = self._validate_safety(sql)
            
            if not self._is_safety_approved(safety_result):
                self._log("❌ Safety validation REJECTED")
                self.trace_collector.add_decision(
                    "SafetyValidator",
                    "REJECTED",
                    f"SQL failed safety checks"
                )
                last_error = f"Safety validation failed: {safety_result}"
                correction_attempts += 1
                continue
            
            self.trace_collector.add_decision(
                "SafetyValidator",
                "APPROVED",
                "SQL passed all safety checks"
            )
            
            # Step 10: SQL Execution
            self._log("🚀 Step 10: Executing SQL...")
            execution_result = self._execute_sql(sql)
            
            if self._is_successful(execution_result):
                return sql, execution_result, correction_attempts
            
            # Failed - prepare for retry
            self._log(f"⚠️ Execution failed, attempting self-correction...")
            last_error = execution_result
            
            # Self-correction
            self._log("🔄 Self-correction in progress...")
            correction_result = self._self_correct(user_query, last_error, schema_result)
            full_context += f"\n\nSelf-Correction:\n{correction_result}"
            
            correction_attempts += 1
        
        return sql, execution_result, correction_attempts
    
    def _plan_query(self, user_query: str, context: str, last_error: str = "") -> str:
        """Create query plan."""
        # Create a mock task for context
        description = f"""
        Create a query plan for: "{user_query}"
        
        Context:
        {context[:2000]}
        
        {"Previous error: " + last_error[:500] if last_error else ""}
        """
        
        task = Task(
            description=description,
            expected_output="Detailed query plan",
            agent=self.agents["query_planner"]
        )
        
        crew = Crew(
            agents=[self.agents["query_planner"]],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        result_str = str(result)
        
        self.trace_collector.add_action(
            agent_name="QueryPlanner",
            action="Created query plan",
            input_summary=f"Query: {user_query}",
            output_summary=result_str[:200]
        )
        
        return result_str
    
    def _generate_sql(self, user_query: str, query_plan: str) -> str:
        """Generate SQL from query plan."""
        task = Task(
            description=f"""
            Generate SQL for: "{user_query}"
            
            Query Plan:
            {query_plan[:1500]}
            
            Output ONLY the SQL query. No explanations.
            """,
            expected_output="A single valid SQLite SQL query",
            agent=self.agents["sql_generator"]
        )
        
        crew = Crew(
            agents=[self.agents["sql_generator"]],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        sql = self._extract_sql(str(result))
        
        self.trace_collector.add_action(
            agent_name="SQLGenerator",
            action="Generated SQL",
            input_summary=f"From plan: {query_plan[:100]}...",
            output_summary=sql[:200]
        )
        
        return sql
    
    def _extract_sql(self, result: str) -> str:
        """Extract SQL from result text."""
        # Try to find SQL between markers
        match = re.search(r'```sql\s*(.+?)\s*```', result, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # Try to find SELECT statement
        match = re.search(r'((?:WITH|SELECT)\s+.+?;)', result, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # Just return the result
        return result.strip()
    
    def _validate_safety(self, sql: str) -> str:
        """Validate SQL safety before execution."""
        task = create_safety_validation_task(
            self.agents["safety_validator"],
            sql
        )
        
        crew = Crew(
            agents=[self.agents["safety_validator"]],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        result_str = str(result)
        
        self.trace_collector.add_action(
            agent_name="SafetyValidator",
            action="Validated SQL safety",
            input_summary=f"SQL: {sql[:100]}...",
            output_summary=result_str[:200]
        )
        
        return result_str
    
    def _is_safety_approved(self, safety_result: str) -> bool:
        """Check if safety validation passed."""
        result_lower = safety_result.lower()
        return "approved" in result_lower and "rejected" not in result_lower
    
    def _execute_sql(self, sql: str) -> str:
        """Execute the SQL query."""
        task = Task(
            description=f"""
            Execute this SQL query safely:
            
            ```
            {sql}
            ```
            
            Capture and report:
            - Row count
            - Column names
            - Result data (first 10 rows)
            - Any errors
            """,
            expected_output="Execution results with data or error message",
            agent=self.agents["sql_executor"]
        )
        
        crew = Crew(
            agents=[self.agents["sql_executor"]],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        result_str = str(result)
        
        self.trace_collector.add_action(
            agent_name="SQLExecutor",
            action="Executed SQL",
            input_summary=f"SQL: {sql[:100]}...",
            output_summary=result_str[:200]
        )
        
        return result_str
    
    def _self_correct(self, user_query: str, error: str, schema: str) -> str:
        """Attempt self-correction after failure."""
        task = Task(
            description=f"""
            The previous query failed. Analyze and correct.
            
            Original Query: "{user_query}"
            
            Error:
            {error[:1000]}
            
            Schema:
            {schema[:1000]}
            
            Diagnose what went wrong and propose a corrected approach.
            """,
            expected_output="Diagnosis and corrected query plan",
            agent=self.agents["self_correction"]
        )
        
        crew = Crew(
            agents=[self.agents["self_correction"]],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        result_str = str(result)
        
        self.trace_collector.add_action(
            agent_name="SelfCorrection",
            action="Analyzed failure and proposed fix",
            input_summary=f"Error: {error[:100]}...",
            output_summary=result_str[:200],
            reasoning="Attempting recovery from query failure"
        )
        
        return result_str
    
    def _is_successful(self, execution_result: str) -> bool:
        """Check if execution was successful."""
        result_lower = execution_result.lower()
        has_error = "error" in result_lower or "failed" in result_lower
        has_success = "success" in result_lower or "rows returned" in result_lower or "executed" in result_lower
        return has_success and not has_error
    
    # ========================================
    # STEP 11: Result Validation
    # ========================================
    
    def _validate_results(self, user_query: str, sql: str, execution_result: str) -> str:
        """Validate that results make sense."""
        self._log("✅ Step 11: Validating results...")
        
        row_count = self._extract_row_count(execution_result)
        
        task = create_result_validation_task(
            self.agents["result_validator"],
            user_query,
            sql,
            execution_result,
            row_count
        )
        
        crew = Crew(
            agents=[self.agents["result_validator"]],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        result_str = str(result)
        
        self.trace_collector.add_action(
            agent_name="ResultValidator",
            action="Validated result sanity",
            input_summary=f"Row count: {row_count}",
            output_summary=result_str[:200]
        )
        
        return result_str
    
    def _extract_row_count(self, execution_result: str) -> int:
        """Extract row count from execution result."""
        match = re.search(r'(\d+)\s*rows?\s*(returned|found)?', execution_result.lower())
        if match:
            return int(match.group(1))
        return 0
    
    # ========================================
    # STEP 12: Response Synthesis
    # ========================================
    
    def _synthesize_response(self, user_query: str, sql: str, 
                              execution_result: str, validation_result: str,
                              correction_attempts: int) -> FinalResponse:
        """Create the final human-readable response."""
        self._log("💬 Step 12: Synthesizing response...")
        
        reasoning_summary = self.trace_collector.get_summary()
        
        task = Task(
            description=f"""
            Create a human-readable response for the user.
            
            Original Question: "{user_query}"
            
            Execution Result:
            {execution_result[:1500]}
            
            Validation Notes:
            {validation_result[:500]}
            
            Create a clear, natural language answer.
            """,
            expected_output="Human-readable answer",
            agent=self.agents["response_synthesizer"]
        )
        
        crew = Crew(
            agents=[self.agents["response_synthesizer"]],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        answer = str(result)
        
        self.trace_collector.add_action(
            agent_name="ResponseSynthesizer",
            action="Created human-readable response",
            input_summary=f"Execution: {execution_result[:100]}...",
            output_summary=answer[:200]
        )
        
        # Determine final status
        if self._is_successful(execution_result):
            status = ExecutionStatus.SUCCESS
        elif "empty" in execution_result.lower() or "0 rows" in execution_result.lower():
            status = ExecutionStatus.EMPTY
        else:
            status = ExecutionStatus.ERROR
        
        return FinalResponse(
            answer=answer,
            sql_used=sql,
            reasoning_trace=ReasoningTrace(
                user_query=user_query,
                actions=self.trace_collector.actions,
                total_time_ms=self.trace_collector.get_elapsed_time(),
                correction_attempts=correction_attempts,
                final_status=status
            ),
            row_count=self._extract_row_count(execution_result),
            warnings=[f"Required {correction_attempts} correction attempts"] if correction_attempts > 0 else []
        )


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def run_query(query: str, verbose: bool = True) -> FinalResponse:
    """
    Convenience function to run a single query.
    
    Args:
        query: Natural language question
        verbose: Whether to print progress
        
    Returns:
        FinalResponse with answer and reasoning trace
    """
    orchestrator = EnhancedReasonSQLOrchestrator(verbose=verbose)
    return orchestrator.process_query(query)


# Keep backward compatibility
ReasonSQLOrchestrator = EnhancedReasonSQLOrchestrator
