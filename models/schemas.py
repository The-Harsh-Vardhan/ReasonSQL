"""
Pydantic models for structured data flow between agents.
These models ensure type safety and enable reliable data passing.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class QueryIntent(str, Enum):
    """Classification of user query intent."""
    DATA_QUERY = "data_query"       # User wants to retrieve data
    META_QUERY = "meta_query"       # User wants schema information
    AMBIGUOUS = "ambiguous"         # Query needs clarification


class ExecutionStatus(str, Enum):
    """Status of SQL execution."""
    SUCCESS = "success"
    ERROR = "error"
    EMPTY = "empty"
    VALIDATION_FAILED = "validation_failed"
    BLOCKED = "blocked"  # Query blocked by safety validator


# ============================================================
# Schema Models
# ============================================================

class ColumnInfo(BaseModel):
    """Information about a database column."""
    name: str = Field(description="Column name")
    data_type: str = Field(description="SQL data type")
    nullable: bool = Field(default=True, description="Whether column allows NULL")
    primary_key: bool = Field(default=False, description="Whether column is primary key")
    foreign_key: Optional[str] = Field(default=None, description="Foreign key reference (table.column)")


class TableInfo(BaseModel):
    """Information about a database table."""
    name: str = Field(description="Table name")
    columns: List[ColumnInfo] = Field(description="List of columns in the table")
    row_count: Optional[int] = Field(default=None, description="Approximate row count")


class ForeignKeyRelation(BaseModel):
    """Foreign key relationship between tables."""
    from_table: str = Field(description="Source table name")
    from_column: str = Field(description="Source column name")
    to_table: str = Field(description="Target table name")
    to_column: str = Field(description="Target column name")


class SchemaContext(BaseModel):
    """Complete database schema context."""
    tables: List[TableInfo] = Field(description="All tables in the database")
    relationships: List[ForeignKeyRelation] = Field(description="Foreign key relationships")
    summary: str = Field(description="Human-readable schema summary")
    
    def get_table(self, name: str) -> Optional[TableInfo]:
        """Get table info by name (case-insensitive)."""
        for table in self.tables:
            if table.name.lower() == name.lower():
                return table
        return None
    
    def get_related_tables(self, table_name: str) -> List[str]:
        """Get all tables related to the given table via foreign keys."""
        related = set()
        for rel in self.relationships:
            if rel.from_table.lower() == table_name.lower():
                related.add(rel.to_table)
            elif rel.to_table.lower() == table_name.lower():
                related.add(rel.from_table)
        return list(related)


# ============================================================
# Intent Analysis Models
# ============================================================

class IntentClassification(BaseModel):
    """Result of intent analysis."""
    intent: QueryIntent = Field(description="Classified intent type")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score (0-1)")
    relevant_tables: List[str] = Field(default_factory=list, description="Tables likely needed")
    relevant_columns: List[str] = Field(default_factory=list, description="Columns likely needed")
    clarification_needed: bool = Field(default=False, description="Whether clarification is required")
    clarification_question: Optional[str] = Field(default=None, description="Question to ask user")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made about the query")
    reasoning: str = Field(description="Explanation of the classification")


# ============================================================
# Query Planning Models
# ============================================================

class JoinSpec(BaseModel):
    """Specification for a table join."""
    table: str = Field(description="Table to join")
    join_type: str = Field(default="INNER", description="JOIN type (INNER, LEFT, RIGHT)")
    on_condition: str = Field(description="JOIN ON condition")


class FilterSpec(BaseModel):
    """Specification for a WHERE filter."""
    column: str = Field(description="Column to filter on")
    operator: str = Field(description="Comparison operator (=, >, <, LIKE, IN, etc.)")
    value: Any = Field(description="Filter value")
    is_subquery: bool = Field(default=False, description="Whether value is a subquery")


class AggregationSpec(BaseModel):
    """Specification for aggregation."""
    function: str = Field(description="Aggregation function (COUNT, SUM, AVG, etc.)")
    column: str = Field(description="Column to aggregate")
    alias: Optional[str] = Field(default=None, description="Result column alias")


class QueryPlan(BaseModel):
    """Detailed query execution plan."""
    base_table: str = Field(description="Primary table for the query")
    select_columns: List[str] = Field(description="Columns to select (with table aliases)")
    joins: List[JoinSpec] = Field(default_factory=list, description="Tables to join")
    filters: List[FilterSpec] = Field(default_factory=list, description="WHERE conditions")
    aggregations: List[AggregationSpec] = Field(default_factory=list, description="Aggregation specs")
    group_by: List[str] = Field(default_factory=list, description="GROUP BY columns")
    order_by: List[str] = Field(default_factory=list, description="ORDER BY columns (with ASC/DESC)")
    limit: int = Field(default=100, ge=1, le=1000, description="Result limit")
    distinct: bool = Field(default=False, description="Whether to use DISTINCT")
    reasoning: str = Field(description="Explanation of the query plan")
    
    def validate_no_select_star(self) -> bool:
        """Ensure no SELECT * in columns."""
        return "*" not in self.select_columns


# ============================================================
# Execution Models
# ============================================================

class ExecutionResult(BaseModel):
    """Result of SQL execution."""
    status: ExecutionStatus = Field(description="Execution status")
    sql: str = Field(description="The SQL that was executed")
    data: List[Dict[str, Any]] = Field(default_factory=list, description="Query results as list of dicts")
    row_count: int = Field(default=0, description="Number of rows returned")
    column_names: List[str] = Field(default_factory=list, description="Column names in result")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    execution_time_ms: Optional[float] = Field(default=None, description="Query execution time in ms")


class ValidationResult(BaseModel):
    """Result of SQL validation."""
    is_valid: bool = Field(description="Whether SQL passed validation")
    errors: List[str] = Field(default_factory=list, description="List of validation errors")
    warnings: List[str] = Field(default_factory=list, description="List of warnings")
    has_limit: bool = Field(default=False, description="Whether SQL has LIMIT clause")
    has_select_star: bool = Field(default=False, description="Whether SQL has SELECT *")
    is_read_only: bool = Field(default=True, description="Whether SQL is read-only")


# ============================================================
# Self-Correction Models
# ============================================================

class CorrectionAttempt(BaseModel):
    """Record of a self-correction attempt."""
    attempt_number: int = Field(description="Which attempt this is (1, 2, 3...)")
    original_error: str = Field(description="The error that triggered correction")
    diagnosis: str = Field(description="Analysis of what went wrong")
    correction_strategy: str = Field(description="How we're fixing it")
    revised_plan: Optional[QueryPlan] = Field(default=None, description="New query plan")
    revised_sql: Optional[str] = Field(default=None, description="New SQL query")


# ============================================================
# Response Models
# ============================================================

class AgentAction(BaseModel):
    """Record of a single agent action for the reasoning trace."""
    agent_name: str = Field(description="Name of the agent")
    action: str = Field(description="What the agent did")
    input_summary: str = Field(description="Summary of input received")
    output_summary: str = Field(description="Summary of output produced")
    reasoning: Optional[str] = Field(default=None, description="Agent's reasoning")
    timestamp: Optional[str] = Field(default=None, description="When this action occurred")


class ReasoningTrace(BaseModel):
    """Complete reasoning trace for a query."""
    user_query: str = Field(description="Original user query")
    actions: List[AgentAction] = Field(default_factory=list, description="Sequence of agent actions")
    total_time_ms: Optional[float] = Field(default=None, description="Total processing time")
    correction_attempts: int = Field(default=0, description="Number of self-correction attempts")
    final_status: ExecutionStatus = Field(description="Final execution status")


class FinalResponse(BaseModel):
    """Final response to user."""
    answer: str = Field(description="Human-readable answer")
    sql_used: str = Field(description="The SQL query that was executed")
    reasoning_trace: ReasoningTrace = Field(description="Full reasoning trace")
    data_preview: Optional[List[Dict[str, Any]]] = Field(default=None, description="Preview of result data")
    row_count: int = Field(default=0, description="Total rows returned")
    warnings: List[str] = Field(default_factory=list, description="Any warnings to show user")
