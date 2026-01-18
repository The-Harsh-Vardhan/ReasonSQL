"""
Main orchestration logic for the ReasonSQL Multi-Agent System.
Coordinates agents and tasks to process natural language queries.
"""
import time
from datetime import datetime
from typing import Optional, Tuple, List
from crewai import Crew, Process

from backend.agents import create_all_agents
from backend.tasks import (
    create_schema_exploration_task,
    create_intent_analysis_task,
    create_query_planning_task,
    create_sql_generation_task,
    create_sql_execution_task,
    create_self_correction_task,
    create_response_synthesis_task,
    create_meta_query_task
)
from backend.models import (
    QueryIntent, ExecutionStatus, AgentAction, ReasoningTrace, FinalResponse
)
from configs import MAX_RETRIES, VERBOSE


class ReasoningTraceCollector:
    """Collects and formats the reasoning trace from agent actions."""
    
    def __init__(self):
        self.actions: List[AgentAction] = []
        self.start_time: Optional[float] = None
    
    def start(self):
        """Mark the start of processing."""
        self.start_time = time.time()
        self.actions = []
    
    def add_action(self, agent_name: str, action: str, 
                   input_summary: str, output_summary: str, 
                   reasoning: Optional[str] = None):
        """Add an agent action to the trace."""
        self.actions.append(AgentAction(
            agent_name=agent_name,
            action=action,
            input_summary=input_summary,
            output_summary=output_summary,
            reasoning=reasoning,
            timestamp=datetime.now().strftime("%H:%M:%S")
        ))
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time in milliseconds."""
        if self.start_time:
            return (time.time() - self.start_time) * 1000
        return 0
    
    def get_summary(self) -> str:
        """Get a formatted summary of the reasoning trace."""
        lines = ["=== REASONING TRACE ===\n"]
        for i, action in enumerate(self.actions, 1):
            lines.append(f"Step {i}: {action.agent_name}")
            lines.append(f"  Action: {action.action}")
            lines.append(f"  Input: {action.input_summary[:100]}...")
            lines.append(f"  Output: {action.output_summary[:100]}...")
            if action.reasoning:
                lines.append(f"  Reasoning: {action.reasoning[:100]}...")
            lines.append("")
        return "\n".join(lines)


class ReasonSQLOrchestrator:
    """
    Main orchestrator for the ReasonSQL Multi-Agent System.
    
    Coordinates the flow between agents:
    1. Schema exploration
    2. Intent analysis
    3. Query planning (or meta-query handling)
    4. SQL generation
    5. SQL execution
    6. Self-correction (if needed)
    7. Response synthesis
    """
    
    def __init__(self, verbose: bool = VERBOSE):
        self.verbose = verbose
        self.agents = create_all_agents()
        self.trace_collector = ReasoningTraceCollector()
    
    def process_query(self, user_query: str) -> FinalResponse:
        """
        Process a natural language query and return the response.
        
        Args:
            user_query: The natural language question from the user
            
        Returns:
            FinalResponse with answer, SQL, and reasoning trace
        """
        self.trace_collector.start()
        
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"Processing: {user_query}")
            print(f"{'='*60}\n")
        
        # Step 1: Schema Exploration
        schema_result, schema_task = self._explore_schema(user_query)
        
        # Step 2: Intent Analysis
        intent_result, intent_task = self._analyze_intent(user_query, schema_task)
        
        # Check if this is a meta-query
        if self._is_meta_query(intent_result):
            return self._handle_meta_query(user_query, schema_result)
        
        # Check if clarification is needed
        if self._needs_clarification(intent_result):
            return self._request_clarification(user_query, intent_result)
        
        # Step 3-5: Query Planning, Generation, and Execution
        sql, execution_result, correction_attempts = self._execute_query_with_retry(
            user_query, schema_task, intent_task
        )
        
        # Step 6: Response Synthesis
        final_response = self._synthesize_response(
            user_query, sql, execution_result, correction_attempts
        )
        
        return final_response
    
    def _explore_schema(self, user_query: str) -> Tuple[str, any]:
        """Run schema exploration."""
        if self.verbose:
            print("📊 Step 1: Exploring database schema...")
        
        schema_task = create_schema_exploration_task(
            self.agents["schema_explorer"], 
            user_query
        )
        
        crew = Crew(
            agents=[self.agents["schema_explorer"]],
            tasks=[schema_task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        
        self.trace_collector.add_action(
            agent_name="SchemaExplorer",
            action="Explored database schema",
            input_summary=f"Query: {user_query}",
            output_summary=str(result)[:200]
        )
        
        return str(result), schema_task
    
    def _analyze_intent(self, user_query: str, schema_task) -> Tuple[str, any]:
        """Run intent analysis."""
        if self.verbose:
            print("\n🎯 Step 2: Analyzing query intent...")
        
        intent_task = create_intent_analysis_task(
            self.agents["intent_analyzer"],
            user_query,
            schema_task
        )
        
        crew = Crew(
            agents=[self.agents["intent_analyzer"]],
            tasks=[intent_task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        
        self.trace_collector.add_action(
            agent_name="IntentAnalyzer",
            action="Classified query intent",
            input_summary=f"Query: {user_query}",
            output_summary=str(result)[:200]
        )
        
        return str(result), intent_task
    
    def _is_meta_query(self, intent_result: str) -> bool:
        """Check if the query is a meta-query about database structure."""
        result_lower = intent_result.lower()
        return "meta_query" in result_lower or "meta query" in result_lower
    
    def _needs_clarification(self, intent_result: str) -> bool:
        """Check if the query needs clarification."""
        result_lower = intent_result.lower()
        return ("ambiguous" in result_lower and "clarification" in result_lower) or \
               "clarification_needed: true" in result_lower
    
    def _handle_meta_query(self, user_query: str, schema_result: str) -> FinalResponse:
        """Handle meta-queries about database structure."""
        if self.verbose:
            print("\n📋 Handling meta-query...")
        
        meta_task = create_meta_query_task(
            self.agents["schema_explorer"],
            user_query
        )
        
        crew = Crew(
            agents=[self.agents["schema_explorer"]],
            tasks=[meta_task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        
        self.trace_collector.add_action(
            agent_name="SchemaExplorer",
            action="Answered meta-query",
            input_summary=f"Query: {user_query}",
            output_summary=str(result)[:200]
        )
        
        return FinalResponse(
            answer=str(result),
            sql_used="N/A (meta-query)",
            reasoning_trace=ReasoningTrace(
                user_query=user_query,
                actions=self.trace_collector.actions,
                total_time_ms=self.trace_collector.get_elapsed_time(),
                correction_attempts=0,
                final_status=ExecutionStatus.SUCCESS
            ),
            row_count=0
        )
    
    def _request_clarification(self, user_query: str, intent_result: str) -> FinalResponse:
        """Request clarification for ambiguous queries."""
        # Extract clarification question from intent result
        clarification_msg = "I need some clarification to answer your question accurately:\n\n"
        
        # Try to extract the specific question
        if "clarification_question:" in intent_result.lower():
            # Parse out the clarification question
            lines = intent_result.split("\n")
            for line in lines:
                if "clarification" in line.lower() and "?" in line:
                    clarification_msg += line.strip()
                    break
        else:
            clarification_msg += f"Your query '{user_query}' is ambiguous. "
            clarification_msg += "Could you please be more specific?"
        
        return FinalResponse(
            answer=clarification_msg,
            sql_used="N/A (clarification needed)",
            reasoning_trace=ReasoningTrace(
                user_query=user_query,
                actions=self.trace_collector.actions,
                total_time_ms=self.trace_collector.get_elapsed_time(),
                correction_attempts=0,
                final_status=ExecutionStatus.VALIDATION_FAILED
            ),
            row_count=0,
            warnings=["Query was ambiguous and requires clarification"]
        )
    
    def _execute_query_with_retry(self, user_query: str, schema_task, intent_task) -> Tuple[str, str, int]:
        """
        Execute the query with self-correction retry logic.
        
        Returns:
            Tuple of (final_sql, execution_result, correction_attempts)
        """
        correction_attempts = 0
        last_error = ""
        
        while correction_attempts <= MAX_RETRIES:
            if correction_attempts == 0:
                # First attempt: normal flow
                sql, execution_result = self._plan_generate_execute(
                    user_query, schema_task, intent_task
                )
            else:
                # Retry: use self-correction
                if self.verbose:
                    print(f"\n🔄 Self-correction attempt {correction_attempts}...")
                
                sql, execution_result = self._self_correct_and_retry(
                    user_query, last_error, schema_task, correction_attempts
                )
            
            # Check if we succeeded
            if self._is_successful(execution_result):
                return sql, execution_result, correction_attempts
            
            # Prepare for retry
            last_error = execution_result
            correction_attempts += 1
        
        # Max retries exceeded
        return sql, execution_result, correction_attempts
    
    def _plan_generate_execute(self, user_query: str, schema_task, intent_task) -> Tuple[str, str]:
        """Run the planning, generation, and execution flow."""
        # Query Planning
        if self.verbose:
            print("\n📝 Step 3: Planning query...")
        
        plan_task = create_query_planning_task(
            self.agents["query_planner"],
            user_query,
            schema_task,
            intent_task
        )
        
        # SQL Generation
        if self.verbose:
            print("\n⚙️ Step 4: Generating SQL...")
        
        sql_task = create_sql_generation_task(
            self.agents["sql_generator"],
            user_query,
            plan_task
        )
        
        # SQL Execution
        if self.verbose:
            print("\n🚀 Step 5: Executing SQL...")
        
        exec_task = create_sql_execution_task(
            self.agents["sql_executor"],
            sql_task
        )
        
        # Run all three tasks
        crew = Crew(
            agents=[
                self.agents["query_planner"],
                self.agents["sql_generator"],
                self.agents["sql_executor"]
            ],
            tasks=[plan_task, sql_task, exec_task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        
        # Extract SQL from the flow (simplified - in practice parse from sql_task)
        sql = self._extract_sql_from_result(str(result))
        
        self.trace_collector.add_action(
            agent_name="QueryPlanner → SQLGenerator → SQLExecutor",
            action="Planned, generated, and executed SQL",
            input_summary=f"Query: {user_query}",
            output_summary=str(result)[:200]
        )
        
        return sql, str(result)
    
    def _self_correct_and_retry(self, user_query: str, error_context: str,
                                 schema_task, attempt_number: int) -> Tuple[str, str]:
        """Run self-correction and retry the query."""
        correction_task = create_self_correction_task(
            self.agents["self_correction"],
            user_query,
            error_context,
            schema_task,
            attempt_number
        )
        
        crew = Crew(
            agents=[self.agents["self_correction"]],
            tasks=[correction_task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        correction_result = crew.kickoff()
        
        self.trace_collector.add_action(
            agent_name="SelfCorrection",
            action=f"Correction attempt {attempt_number}",
            input_summary=f"Error: {error_context[:100]}",
            output_summary=str(correction_result)[:200]
        )
        
        # Now re-run with the corrected plan
        # For simplicity, we'll use the SQL generator directly
        sql_task = create_sql_generation_task(
            self.agents["sql_generator"],
            user_query + f"\n\nCorrected plan: {correction_result}",
            correction_task
        )
        
        exec_task = create_sql_execution_task(
            self.agents["sql_executor"],
            sql_task
        )
        
        crew = Crew(
            agents=[self.agents["sql_generator"], self.agents["sql_executor"]],
            tasks=[sql_task, exec_task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        sql = self._extract_sql_from_result(str(result))
        
        return sql, str(result)
    
    def _is_successful(self, execution_result: str) -> bool:
        """Check if execution was successful."""
        result_lower = execution_result.lower()
        return ("success" in result_lower and "error" not in result_lower) or \
               "rows returned" in result_lower or \
               "executed successfully" in result_lower
    
    def _extract_sql_from_result(self, result: str) -> str:
        """Extract the SQL query from the execution result."""
        # Look for SQL patterns
        import re
        
        # Try to find SELECT statement
        match = re.search(r'(SELECT\s+.+?;)', result, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1)
        
        # Try to find SQL between markers
        match = re.search(r'```sql\s*(.+?)\s*```', result, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1)
        
        # Return best guess
        lines = result.split('\n')
        for line in lines:
            if line.strip().upper().startswith('SELECT'):
                return line.strip()
        
        return "Unable to extract SQL"
    
    def _synthesize_response(self, user_query: str, sql: str, 
                             execution_result: str, correction_attempts: int) -> FinalResponse:
        """Create the final response using the response synthesizer."""
        if self.verbose:
            print("\n💬 Step 6: Synthesizing response...")
        
        reasoning_summary = self.trace_collector.get_summary()
        
        # Create a mock execution task for context
        from crewai import Task
        mock_exec_task = Task(
            description="Mock task for context",
            expected_output=execution_result,
            agent=self.agents["response_synthesizer"]
        )
        
        response_task = create_response_synthesis_task(
            self.agents["response_synthesizer"],
            user_query,
            mock_exec_task,
            reasoning_summary
        )
        
        crew = Crew(
            agents=[self.agents["response_synthesizer"]],
            tasks=[response_task],
            process=Process.sequential,
            verbose=self.verbose
        )
        
        result = crew.kickoff()
        
        self.trace_collector.add_action(
            agent_name="ResponseSynthesizer",
            action="Created human-readable response",
            input_summary=f"Execution result: {execution_result[:100]}",
            output_summary=str(result)[:200]
        )
        
        # Determine final status
        if self._is_successful(execution_result):
            status = ExecutionStatus.SUCCESS
        elif "empty" in execution_result.lower() or "0 rows" in execution_result.lower():
            status = ExecutionStatus.EMPTY
        else:
            status = ExecutionStatus.ERROR
        
        return FinalResponse(
            answer=str(result),
            sql_used=sql,
            reasoning_trace=ReasoningTrace(
                user_query=user_query,
                actions=self.trace_collector.actions,
                total_time_ms=self.trace_collector.get_elapsed_time(),
                correction_attempts=correction_attempts,
                final_status=status
            ),
            row_count=self._extract_row_count(execution_result),
            warnings=[] if status == ExecutionStatus.SUCCESS else 
                     [f"Query required {correction_attempts} correction attempts"]
        )
    
    def _extract_row_count(self, execution_result: str) -> int:
        """Extract row count from execution result."""
        import re
        match = re.search(r'(\d+)\s*rows?\s*(returned|found)', execution_result.lower())
        if match:
            return int(match.group(1))
        return 0


def run_query(query: str, verbose: bool = True) -> FinalResponse:
    """
    Convenience function to run a single query.
    
    Args:
        query: Natural language question
        verbose: Whether to print progress
        
    Returns:
        FinalResponse with answer and reasoning trace
    """
    orchestrator = ReasonSQLOrchestrator(verbose=verbose)
    return orchestrator.process_query(query)
