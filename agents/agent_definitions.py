"""
Agent definitions for the NL2SQL Multi-Agent System.
Each agent has a clearly defined responsibility and uses specific tools.

AGENT INVENTORY (12 Total):
==========================
CORE AGENTS (7):
1. SchemaExplorerAgent - Database structure inspection
2. IntentAnalyzerAgent - Query classification
3. QueryPlannerAgent - SQL plan design
4. SQLGeneratorAgent - SQL code generation
5. SQLExecutorAgent - Safe execution
6. SelfCorrectionAgent - Error recovery
7. ResponseSynthesizerAgent - Human-readable output

NEW AGENTS (5):
8. ClarificationAgent - Ambiguity resolution
9. SafetyValidatorAgent - Pre-execution safety gate
10. QueryDecomposerAgent - Complex query breakdown
11. DataExplorerAgent - Data sampling for informed decisions
12. ResultValidatorAgent - Output sanity checking
"""
from crewai import Agent
from typing import Optional

from config import get_llm, AGENT_PROMPTS, VERBOSE
from tools import (
    SchemaInspectorTool, SQLValidatorTool, SQLExecutorTool, 
    GetSchemaContextTool, DataSamplerTool
)


# ============================================================
# CORE AGENTS (Original 7)
# ============================================================

def create_schema_explorer_agent() -> Agent:
    """
    Creates the Schema Explorer Agent.
    
    Responsibility:
    - Inspects database schema
    - Retrieves tables, columns, foreign keys
    - Answers meta-queries about the database
    - Produces structured schema summaries
    """
    return Agent(
        role="Database Schema Explorer",
        goal="Thoroughly explore and understand the database schema, including all tables, "
             "columns, data types, primary keys, and foreign key relationships. "
             "Provide accurate, structured information about the database structure.",
        backstory=AGENT_PROMPTS["schema_explorer"],
        tools=[SchemaInspectorTool(), GetSchemaContextTool()],
        llm=get_llm(),
        verbose=VERBOSE,
        allow_delegation=False,
        max_iter=5
    )


def create_intent_analyzer_agent() -> Agent:
    """
    Creates the Intent Analyzer Agent.
    
    Responsibility:
    - Determines if input is a data query, schema query, or ambiguous
    - Identifies relevant tables and columns
    - Decides if clarification is needed
    - Flags ambiguous queries with specific clarification questions
    """
    return Agent(
        role="Query Intent Analyzer",
        goal="Accurately classify user queries into categories (DATA_QUERY, META_QUERY, AMBIGUOUS) "
             "and identify which database tables and columns are relevant to answering the query. "
             "When queries are ambiguous, formulate specific clarification questions.",
        backstory=AGENT_PROMPTS["intent_analyzer"],
        tools=[],  # No tools needed - works with schema context from previous agent
        llm=get_llm(),
        verbose=VERBOSE,
        allow_delegation=False,
        max_iter=3
    )


def create_query_planner_agent() -> Agent:
    """
    Creates the Query Planner Agent.
    
    Responsibility:
    - Designs query execution plans
    - Identifies required tables, joins, and filters
    - Enforces safety rules (no SELECT *, LIMIT required)
    - Documents reasoning for each decision
    """
    return Agent(
        role="SQL Query Planner",
        goal="Design efficient, safe SQL query plans based on the database schema and user intent. "
             "Plans must: (1) specify exact columns to select (never SELECT *), "
             "(2) include appropriate LIMIT clauses, (3) use correct JOIN types and conditions, "
             "(4) document reasoning for each decision.",
        backstory=AGENT_PROMPTS["query_planner"],
        tools=[SchemaInspectorTool()],  # Can verify schema details
        llm=get_llm(),
        verbose=VERBOSE,
        allow_delegation=False,
        max_iter=5
    )


def create_sql_generator_agent() -> Agent:
    """
    Creates the SQL Generator Agent.
    
    Responsibility:
    - Converts query plans into valid SQLite SQL
    - Outputs ONLY SQL (no explanations)
    - Ensures proper syntax and escaping
    - Never adds SELECT * or removes LIMIT
    """
    return Agent(
        role="SQL Query Generator",
        goal="Generate precise, valid SQLite SQL queries from query plans. "
             "Output ONLY the SQL query with no additional text. "
             "Ensure proper syntax, correct table/column names, and maintain all safety constraints "
             "from the query plan (LIMIT clauses, explicit column selection).",
        backstory=AGENT_PROMPTS["sql_generator"],
        tools=[SQLValidatorTool()],  # Can validate its own output
        llm=get_llm(),
        verbose=VERBOSE,
        allow_delegation=False,
        max_iter=5
    )


def create_sql_executor_agent() -> Agent:
    """
    Creates the SQL Executor Agent.
    
    Responsibility:
    - Validates SQL before execution
    - Executes queries safely
    - Captures results, errors, and empty outputs
    - Never executes dangerous operations
    """
    return Agent(
        role="Safe SQL Executor",
        goal="Safely execute SQL queries after thorough validation. "
             "Capture and report results accurately, including handling errors and empty results. "
             "Never execute queries with forbidden operations (INSERT, UPDATE, DELETE, DROP).",
        backstory=AGENT_PROMPTS["sql_executor"],
        tools=[SQLValidatorTool(), SQLExecutorTool()],
        llm=get_llm(),
        verbose=VERBOSE,
        allow_delegation=False,
        max_iter=3
    )


def create_self_correction_agent() -> Agent:
    """
    Creates the Self-Correction Agent.
    
    Responsibility:
    - Analyzes why queries failed or returned unexpected results
    - Identifies root causes (schema mismatch, wrong join, typo, etc.)
    - Proposes corrected query plans with clear reasoning
    - Learns from errors to prevent similar issues
    """
    return Agent(
        role="Query Debugging Expert",
        goal="Analyze failed queries or unexpected results to identify root causes. "
             "Propose corrected query plans with clear explanations of what went wrong "
             "and how the fix addresses the issue. If a query returns empty results when "
             "data was expected, investigate possible causes.",
        backstory=AGENT_PROMPTS["self_correction"],
        tools=[SchemaInspectorTool(), SQLValidatorTool()],
        llm=get_llm(),
        verbose=VERBOSE,
        allow_delegation=False,
        max_iter=5
    )


def create_response_synthesizer_agent() -> Agent:
    """
    Creates the Response Synthesizer Agent.
    
    Responsibility:
    - Converts query results into human-readable explanations
    - Summarizes large result sets meaningfully
    - Explains what was queried and why
    - Handles empty results with helpful context
    """
    return Agent(
        role="Data Communication Expert",
        goal="Transform SQL query results into clear, human-readable explanations. "
             "Summarize data meaningfully, explain the query approach, and provide context. "
             "For empty results, explain why no data was found and suggest alternatives if applicable.",
        backstory=AGENT_PROMPTS["response_synthesizer"],
        tools=[],  # No tools needed - works with execution results
        llm=get_llm(),
        verbose=VERBOSE,
        allow_delegation=False,
        max_iter=3
    )


# ============================================================
# NEW AGENTS (5 Additional)
# ============================================================

def create_clarification_agent() -> Agent:
    """
    Creates the Clarification Agent.
    
    Responsibility:
    - Detects unresolved ambiguity (e.g., "recent", "best customers", "top")
    - Generates specific clarification questions
    - Provides safe default assumptions when clarification isn't possible
    - Pauses execution flow until ambiguity is resolved
    - Outputs structured clarification state
    
    Triggers on:
    - Temporal ambiguity: "recent", "latest", "old"
    - Quantitative ambiguity: "best", "top", "most popular"
    - Scope ambiguity: "some", "few", "many"
    """
    return Agent(
        role="Ambiguity Resolution Specialist",
        goal="Detect and resolve ambiguous terms in user queries. "
             "For terms like 'recent', 'best', 'top', generate specific clarification questions. "
             "If clarification cannot be obtained, provide reasonable default assumptions "
             "and EXPLICITLY state what assumption was made.",
        backstory=AGENT_PROMPTS["clarification"],
        tools=[],  # Pure reasoning agent
        llm=get_llm(),
        verbose=VERBOSE,
        allow_delegation=False,
        max_iter=3
    )


def create_safety_validator_agent() -> Agent:
    """
    Creates the Safety Validator Agent.
    
    Responsibility:
    - FINAL safety gate before SQL execution
    - Inspects generated SQL for violations
    - Enforces read-only operations
    - Ensures no SELECT * anywhere in query
    - Verifies LIMIT clause exists
    - Blocks forbidden keywords (INSERT, UPDATE, DELETE, DROP, etc.)
    - Produces explicit APPROVED/REJECTED decision with reasoning
    
    This agent acts as a security checkpoint that cannot be bypassed.
    """
    return Agent(
        role="SQL Security Gatekeeper",
        goal="Act as the FINAL security checkpoint for all SQL queries. "
             "Inspect every query and produce an explicit APPROVED or REJECTED decision. "
             "Enforce: (1) read-only operations only, (2) no SELECT *, (3) mandatory LIMIT, "
             "(4) no forbidden keywords. If rejected, explain exactly what violated policy "
             "and how to fix it.",
        backstory=AGENT_PROMPTS["safety_validator"],
        tools=[SQLValidatorTool()],
        llm=get_llm(),
        verbose=VERBOSE,
        allow_delegation=False,
        max_iter=2  # Quick decision - approve or reject
    )


def create_query_decomposer_agent() -> Agent:
    """
    Creates the Query Decomposer Agent.
    
    Responsibility:
    - Handles complex multi-step queries
    - Breaks down queries requiring multiple operations
    - Identifies when CTEs or subqueries are needed
    - Sequences operations logically
    
    Examples that need decomposition:
    - "Customers who purchased BOTH Rock AND Jazz" → intersection query
    - "Artist with tracks in most playlists" → aggregation + ranking
    - "Revenue difference between this year and last" → two queries + comparison
    """
    return Agent(
        role="Complex Query Decomposition Expert",
        goal="Break down complex, multi-step queries into manageable sub-problems. "
             "Identify when a query requires: (1) multiple separate queries, "
             "(2) CTEs (WITH clauses), (3) subqueries, (4) set operations (UNION, INTERSECT, EXCEPT). "
             "Produce a step-by-step execution plan that the QueryPlanner can implement.",
        backstory=AGENT_PROMPTS["query_decomposer"],
        tools=[SchemaInspectorTool()],
        llm=get_llm(),
        verbose=VERBOSE,
        allow_delegation=False,
        max_iter=5
    )


def create_data_explorer_agent() -> Agent:
    """
    Creates the Data Explorer Agent.
    
    Responsibility:
    - Samples data before making query decisions
    - Explores column value distributions
    - Identifies date ranges, value ranges
    - Answers "what values exist?" questions
    - Informs query planning with actual data context
    
    Use cases:
    - "Show recent orders" → First check: what's the date range?
    - "Popular genres" → First check: what genres exist?
    - "High-value customers" → First check: what's the revenue distribution?
    """
    return Agent(
        role="Data Exploration Analyst",
        goal="Explore actual data in the database to inform query decisions. "
             "Sample column values, identify date ranges, check value distributions. "
             "Provide concrete data context like 'dates range from 2009-01-01 to 2013-12-31' "
             "or 'revenue ranges from $0.99 to $25.86'. This helps resolve ambiguity "
             "and ensures queries make sense for the actual data.",
        backstory=AGENT_PROMPTS["data_explorer"],
        tools=[SchemaInspectorTool(), DataSamplerTool()],
        llm=get_llm(),
        verbose=VERBOSE,
        allow_delegation=False,
        max_iter=5
    )


def create_result_validator_agent() -> Agent:
    """
    Creates the Result Validator Agent.
    
    Responsibility:
    - Validates that query results make sense
    - Detects anomalies (negative counts, impossible values)
    - Checks for suspiciously large/small results
    - Verifies results align with the original question
    - Flags potential issues before response synthesis
    
    Checks:
    - Negative counts where they shouldn't exist
    - NULL values in unexpected places
    - Results that seem too large or too small
    - Results that don't match the question's intent
    """
    return Agent(
        role="Result Sanity Checker",
        goal="Validate that query results are sensible and correct. "
             "Check for: (1) negative values where they shouldn't exist, "
             "(2) unexpected NULLs, (3) suspiciously large/small result sets, "
             "(4) results that don't match the original question. "
             "Flag any anomalies with clear explanations.",
        backstory=AGENT_PROMPTS["result_validator"],
        tools=[],  # Pure analysis agent
        llm=get_llm(),
        verbose=VERBOSE,
        allow_delegation=False,
        max_iter=3
    )


# ============================================================
# AGENT FACTORY
# ============================================================

# Convenience function to create all agents
def create_all_agents() -> dict:
    """Create and return all agents as a dictionary."""
    return {
        # Core agents (7)
        "schema_explorer": create_schema_explorer_agent(),
        "intent_analyzer": create_intent_analyzer_agent(),
        "query_planner": create_query_planner_agent(),
        "sql_generator": create_sql_generator_agent(),
        "sql_executor": create_sql_executor_agent(),
        "self_correction": create_self_correction_agent(),
        "response_synthesizer": create_response_synthesizer_agent(),
        # New agents (5)
        "clarification": create_clarification_agent(),
        "safety_validator": create_safety_validator_agent(),
        "query_decomposer": create_query_decomposer_agent(),
        "data_explorer": create_data_explorer_agent(),
        "result_validator": create_result_validator_agent(),
    }


def create_core_agents() -> dict:
    """Create only the core 7 agents (for simpler flows)."""
    return {
        "schema_explorer": create_schema_explorer_agent(),
        "intent_analyzer": create_intent_analyzer_agent(),
        "query_planner": create_query_planner_agent(),
        "sql_generator": create_sql_generator_agent(),
        "sql_executor": create_sql_executor_agent(),
        "self_correction": create_self_correction_agent(),
        "response_synthesizer": create_response_synthesizer_agent(),
    }
