"""
Task definitions for the NL2SQL Multi-Agent System.
Tasks define what each agent should do and how their outputs connect.
"""
from crewai import Task
from typing import List, Optional

from backend.models import QueryPlan, IntentClassification, SchemaContext


def create_schema_exploration_task(agent, user_query: str) -> Task:
    """
    Task for exploring the database schema.
    This is always the first task to provide context for subsequent tasks.
    """
    return Task(
        description=f"""
        Explore the database schema to understand its structure.
        
        User Query: "{user_query}"
        
        Your job:
        1. Use the schema_inspector tool to get the full database schema
        2. Identify ALL tables, their columns, and data types
        3. Map out foreign key relationships between tables
        4. Note which tables/columns might be relevant to the user's query
        
        Provide a comprehensive schema summary that will help other agents 
        understand the database structure.
        """,
        expected_output="""
        A detailed schema summary including:
        - List of all tables with their columns and data types
        - Primary keys for each table
        - Foreign key relationships
        - Relevant tables for the current query
        - Any observations about the schema structure
        """,
        agent=agent
    )


def create_intent_analysis_task(agent, user_query: str, schema_task: Task) -> Task:
    """
    Task for analyzing user intent.
    Uses schema context from the previous task.
    """
    return Task(
        description=f"""
        Analyze the user's query to determine their intent.
        
        User Query: "{user_query}"
        
        Using the schema context provided, classify this query:
        
        1. DATA_QUERY - User wants to retrieve specific data from the database
           Examples: "How many customers are from Brazil?", "List albums by AC/DC"
        
        2. META_QUERY - User wants information about the database structure
           Examples: "What tables exist?", "Show me the schema of Invoice table"
        
        3. AMBIGUOUS - Query is unclear and needs clarification
           Examples: "Show me recent orders" (how recent?), "Who are our best customers?" (by what metric?)
        
        Your job:
        - Classify the query intent
        - Identify which tables and columns are needed
        - If AMBIGUOUS, formulate a specific clarification question
        - List any assumptions you're making
        - Provide confidence score (0-1)
        
        Be conservative - if there's any ambiguity, flag it.
        """,
        expected_output="""
        Intent classification with:
        - Intent type: DATA_QUERY, META_QUERY, or AMBIGUOUS
        - Confidence score (0.0 to 1.0)
        - Relevant tables identified
        - Relevant columns identified
        - Whether clarification is needed (true/false)
        - Clarification question (if needed)
        - Assumptions being made
        - Reasoning for the classification
        """,
        agent=agent,
        context=[schema_task]  # Uses schema exploration output
    )


def create_query_planning_task(agent, user_query: str, schema_task: Task, intent_task: Task) -> Task:
    """
    Task for planning the SQL query.
    Uses schema context and intent analysis.
    """
    return Task(
        description=f"""
        Create a detailed query plan for the user's request.
        
        User Query: "{user_query}"
        
        Using the schema context and intent analysis, design a query plan.
        
        CRITICAL SAFETY RULES:
        1. NEVER use SELECT * - always specify exact columns needed
        2. ALWAYS include a LIMIT clause (default: 100, adjust if needed)
        3. Use appropriate JOIN types (INNER, LEFT, etc.)
        4. Only query tables/columns that exist in the schema
        
        Your query plan must include:
        1. Base table - the primary table for the query
        2. Select columns - exact columns to retrieve (with table aliases)
        3. Joins - any tables that need to be joined, with conditions
        4. Filters - WHERE conditions needed
        5. Aggregations - any COUNT, SUM, AVG, etc.
        6. Grouping - GROUP BY if needed
        7. Ordering - ORDER BY if needed
        8. Limit - how many rows to return
        
        Document your reasoning for each decision.
        """,
        expected_output="""
        Detailed query plan with:
        - base_table: Primary table name
        - select_columns: List of "table.column" or "aggregate(column) AS alias"
        - joins: List of {{table, join_type, on_condition}}
        - filters: List of {{column, operator, value}}
        - aggregations: List of {{function, column, alias}}
        - group_by: List of columns
        - order_by: List of "column ASC/DESC"
        - limit: Number (required!)
        - reasoning: Why this plan is optimal
        """,
        agent=agent,
        context=[schema_task, intent_task]
    )


def create_sql_generation_task(agent, user_query: str, plan_task: Task) -> Task:
    """
    Task for generating the actual SQL.
    Uses the query plan from the planner.
    """
    return Task(
        description=f"""
        Generate a valid SQLite SQL query from the query plan.
        
        User Query: "{user_query}"
        
        IMPORTANT:
        - Output ONLY the SQL query - no explanations, no markdown
        - Follow the query plan exactly
        - Ensure proper SQLite syntax
        - Maintain all safety constraints (LIMIT, no SELECT *)
        - Use proper escaping for string values
        
        After generating, use the sql_validator tool to verify the query.
        If validation fails, fix the issues and regenerate.
        """,
        expected_output="""
        A single, valid SQLite SQL query.
        No explanations, no markdown code blocks, just the raw SQL.
        The query must pass validation (has LIMIT, no SELECT *, read-only).
        """,
        agent=agent,
        context=[plan_task]
    )


def create_sql_execution_task(agent, sql_task: Task) -> Task:
    """
    Task for executing the SQL query.
    Validates and executes, capturing all results.
    """
    return Task(
        description="""
        Execute the generated SQL query safely.
        
        Steps:
        1. First, use sql_validator to check the query
        2. If validation passes, use sql_executor to run it
        3. Capture the results completely:
           - Number of rows returned
           - Column names
           - Actual data (or error message)
           - Execution time
        
        If the query fails or returns empty:
        - Report the exact error or "empty result set"
        - Do NOT make up data
        """,
        expected_output="""
        Execution report with:
        - Status: SUCCESS, ERROR, or EMPTY
        - SQL that was executed
        - Row count
        - Column names
        - Data preview (first 10 rows)
        - Error message (if failed)
        - Execution time in milliseconds
        """,
        agent=agent,
        context=[sql_task]
    )


def create_self_correction_task(agent, original_query: str, error_context: str, 
                                 schema_task: Task, attempt_number: int) -> Task:
    """
    Task for self-correction when query fails.
    Analyzes the error and proposes a fix.
    """
    return Task(
        description=f"""
        The previous query failed or returned unexpected results.
        
        Original User Query: "{original_query}"
        
        Error/Issue:
        {error_context}
        
        This is correction attempt #{attempt_number}.
        
        Your job:
        1. Analyze what went wrong:
           - SQL syntax error?
           - Wrong table/column name?
           - Incorrect join condition?
           - Missing filter?
           - Logic error?
        
        2. Use schema_inspector to verify correct table/column names
        
        3. Propose a REVISED query plan that fixes the issue
        
        4. Explain clearly:
           - What was wrong
           - How your fix addresses it
           - Why this should work
        
        Be specific about what you're changing and why.
        """,
        expected_output="""
        Correction analysis with:
        - Diagnosis: What went wrong
        - Root cause: Why it happened
        - Correction strategy: How to fix it
        - Revised query plan: New plan with the fix
        - Confidence: How sure you are this will work
        """,
        agent=agent,
        context=[schema_task]
    )


def create_response_synthesis_task(agent, user_query: str, execution_task: Task,
                                    reasoning_summary: str) -> Task:
    """
    Task for creating the final human-readable response.
    """
    return Task(
        description=f"""
        Create a clear, human-readable response for the user.
        
        Original Question: "{user_query}"
        
        Reasoning Summary:
        {reasoning_summary}
        
        Your job:
        1. Interpret the query results (or lack thereof)
        2. Create a natural language answer that:
           - Directly answers the user's question
           - Summarizes the data meaningfully
           - Notes any limitations or caveats
        
        3. For empty results:
           - Explain why no data was found
           - Suggest what this means
           - Offer alternative queries if appropriate
        
        4. For large result sets:
           - Summarize the key findings
           - Highlight interesting patterns
           - Note that more data exists if relevant
        
        Keep the response concise but complete.
        """,
        expected_output="""
        A clear, natural language response that:
        - Directly answers the user's question
        - Provides relevant data summaries
        - Explains the approach taken
        - Notes any limitations
        - Is easy for non-technical users to understand
        """,
        agent=agent,
        context=[execution_task]
    )


def create_meta_query_task(agent, user_query: str) -> Task:
    """
    Special task for handling meta-queries about the database.
    """
    return Task(
        description=f"""
        Answer the user's meta-query about the database structure.
        
        User Query: "{user_query}"
        
        This is a META_QUERY - the user wants information about the database itself.
        
        Common meta-queries:
        - "What tables exist?" → List all tables with row counts
        - "What columns does X have?" → Describe table X
        - "How are tables related?" → Explain relationships
        - "Which table has the most rows?" → Query and compare
        
        Use the schema inspection tools to get accurate information.
        Provide a clear, complete answer.
        """,
        expected_output="""
        A clear answer to the meta-query with:
        - The specific information requested
        - Relevant context (e.g., data types, relationships)
        - Examples if helpful
        """,
        agent=agent
    )


# ============================================================
# NEW TASK DEFINITIONS FOR ADDITIONAL AGENTS
# ============================================================

def create_clarification_task(agent, user_query: str, ambiguous_terms: List[str]) -> Task:
    """
    Task for resolving ambiguity in user queries.
    """
    terms_str = ", ".join(f"'{t}'" for t in ambiguous_terms)
    return Task(
        description=f"""
        The user query contains ambiguous terms that need clarification.
        
        User Query: "{user_query}"
        Ambiguous Terms: {terms_str}
        
        Your job:
        1. For each ambiguous term, generate a specific clarification question
        2. Provide reasonable default values if clarification cannot be obtained
        3. EXPLICITLY state any assumptions you're making
        
        AMBIGUITY PATTERNS:
        - "recent" → What time period? (7 days, 30 days, this year?)
        - "best" → By what metric? (revenue, quantity, frequency?)
        - "top" → Top how many? (5, 10, 100?)
        - "popular" → Measured how? (sales, plays, ratings?)
        - "old/new" → Relative to what date?
        
        FORMAT YOUR OUTPUT AS:
        1. Clarification Questions: [list specific questions]
        2. Default Assumptions: [what you'll assume if not clarified]
        3. Recommendation: [proceed with defaults OR wait for clarification]
        """,
        expected_output="""
        Structured clarification output:
        - List of specific clarification questions
        - Default values for each ambiguous term
        - Explicit statement of assumptions
        - Recommendation on whether to proceed or wait
        """,
        agent=agent
    )


def create_safety_validation_task(agent, sql: str) -> Task:
    """
    Task for final safety validation before SQL execution.
    """
    return Task(
        description=f"""
        Perform FINAL safety validation on this SQL query before execution.
        
        SQL to validate:
        ```
        {sql}
        ```
        
        MANDATORY CHECKS:
        1. ✓ Read-only: Must be SELECT or WITH...SELECT only
        2. ✓ No SELECT *: All columns must be explicitly specified
        3. ✓ Has LIMIT: Query must include a LIMIT clause
        4. ✓ No forbidden keywords: INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE
        5. ✓ No dangerous patterns: Multiple statements, injection patterns
        
        DECISION REQUIRED:
        You MUST output one of:
        - APPROVED: Query is safe to execute
        - REJECTED: Query violates safety rules (explain which ones)
        
        If REJECTED, explain:
        1. Which rule(s) were violated
        2. The specific part of SQL that violates it
        3. How to fix the violation
        
        You are the FINAL security checkpoint. Be strict.
        """,
        expected_output="""
        Safety decision:
        - Decision: APPROVED or REJECTED
        - Violations (if any): List of rules violated
        - Fix suggestions (if rejected): How to make the query safe
        - Final SQL (if approved): The validated query
        """,
        agent=agent
    )


def create_query_decomposition_task(agent, user_query: str, schema_context: str) -> Task:
    """
    Task for breaking down complex queries into steps.
    """
    return Task(
        description=f"""
        Analyze this complex query and break it into manageable steps.
        
        User Query: "{user_query}"
        
        Schema Context:
        {schema_context[:1000]}
        
        DECOMPOSITION ANALYSIS:
        1. Identify if this query requires multiple steps
        2. Determine which SQL constructs are needed:
           - CTEs (WITH clauses) for reusable subqueries
           - Subqueries for nested conditions
           - Set operations (UNION, INTERSECT, EXCEPT)
           - Window functions for rankings
        
        COMMON PATTERNS:
        - "both X and Y" → INTERSECT or double JOIN with conditions
        - "either X or Y" → UNION or OR conditions
        - "X but not Y" → EXCEPT or LEFT JOIN with NULL check
        - "most/highest/top N" → Aggregation + ORDER BY + LIMIT
        - "compare A to B" → Two subqueries or CTEs + comparison
        
        OUTPUT:
        A numbered step-by-step execution plan that the QueryPlanner can implement.
        Each step should be atomic and clearly defined.
        """,
        expected_output="""
        Query decomposition plan:
        - Complexity level: SIMPLE, MODERATE, COMPLEX, MULTI-STEP
        - Required constructs: List of SQL constructs needed
        - Step-by-step plan:
          1. [First step]
          2. [Second step]
          ...
        - Final assembly: How steps combine into final query
        """,
        agent=agent
    )


def create_data_exploration_task(agent, user_query: str, tables: List[str], 
                                  columns: List[str]) -> Task:
    """
    Task for exploring data before query planning.
    """
    tables_str = ", ".join(tables) if tables else "relevant tables"
    columns_str = ", ".join(columns) if columns else "relevant columns"
    
    return Task(
        description=f"""
        Explore the database to inform query decisions.
        
        User Query: "{user_query}"
        Tables to explore: {tables_str}
        Columns of interest: {columns_str}
        
        EXPLORATION GOALS:
        1. Date columns: Find the min/max date range
        2. Numerical columns: Find min/max/avg values
        3. Categorical columns: Find distinct values and frequencies
        4. Check for NULL values and data quality
        
        USE CASES:
        - "recent orders" → What's the actual date range in Invoice?
        - "high revenue" → What's the revenue distribution?
        - "popular genres" → What genres exist and how many tracks each?
        
        Use the data_sampler tool to explore each relevant column.
        
        OUTPUT:
        Concrete findings with numbers, not vague descriptions.
        Example: "InvoiceDate ranges from 2009-01-01 to 2013-12-22"
        """,
        expected_output="""
        Data exploration findings:
        - Date ranges: [min to max for date columns]
        - Value distributions: [ranges for numerical columns]
        - Categorical values: [distinct values with counts]
        - Data quality notes: [NULL counts, anomalies]
        - Query implications: [how this affects the query]
        """,
        agent=agent
    )


def create_result_validation_task(agent, user_query: str, sql: str, 
                                   results: str, row_count: int) -> Task:
    """
    Task for validating query results make sense.
    """
    return Task(
        description=f"""
        Validate that the query results are sensible and correct.
        
        Original Question: "{user_query}"
        
        SQL Executed:
        {sql}
        
        Results ({row_count} rows):
        {results[:1000]}
        
        VALIDATION CHECKS:
        1. Do the results answer the original question?
        2. Are there unexpected NULL values?
        3. Are numerical values sensible (no negative counts, etc.)?
        4. Is the row count reasonable for this query?
        5. Do the column names match what was asked?
        
        ANOMALY DETECTION:
        - Negative COUNT values → ERROR
        - Negative prices/revenue where shouldn't be → WARNING
        - Too few results when expecting more → INVESTIGATE
        - Too many results → May need stricter filters
        
        OUTPUT:
        - VALID: Results look correct
        - WARNING: Results have minor issues (explain)
        - INVALID: Results are definitely wrong (explain why)
        """,
        expected_output="""
        Validation result:
        - Status: VALID, WARNING, or INVALID
        - Issues found: [list any problems]
        - Recommendations: [what to do about issues]
        - Confidence: [how confident in the results]
        """,
        agent=agent
    )
