"""
Naive NL→SQL Generator (Baseline for Comparison)

PURPOSE:
========
This module provides a DELIBERATELY SIMPLE single-shot NL→SQL approach
to demonstrate WHERE AND WHY explicit multi-agent reasoning is needed.

THIS IS NOT THE MAIN SYSTEM. It exists only for comparison purposes.

WHAT "NAIVE" MEANS:
==================
- ONE single LLM call
- Input: User question + Raw schema (tables + columns)
- Output: SQL query only
- NO schema exploration
- NO clarification of ambiguous terms
- NO validation or safety checks
- NO self-correction or retries

WHY THIS EXISTS:
================
To show judges/users that naive "prompt → SQL" approaches fail on:
- Ambiguous queries ("recent", "best", "popular")
- Complex joins (wrong table relationships)
- Schema hallucinations (inventing table/column names)
- Multi-step logic
- Edge cases

The multi-agent system handles all of these correctly.
"""

import sqlite3
import re
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from litellm import completion
from configs import DATABASE_PATH


# ============================================================
# DATA MODELS
# ============================================================

class NaiveStatus(Enum):
    """Status of naive SQL generation/execution."""
    SUCCESS = "success"
    GENERATION_ERROR = "generation_error"
    EXECUTION_ERROR = "execution_error"
    BLOCKED_UNSAFE = "blocked_unsafe"


@dataclass
class NaiveResult:
    """Result from naive SQL generation and execution."""
    status: NaiveStatus
    generated_sql: str
    result_data: Optional[list] = None
    row_count: int = 0
    error_message: Optional[str] = None
    column_names: Optional[list] = None
    
    @property
    def is_success(self) -> bool:
        return self.status == NaiveStatus.SUCCESS


# ============================================================
# FORBIDDEN KEYWORDS FOR SAFETY
# ============================================================

# These keywords indicate destructive operations - NEVER execute
UNSAFE_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", 
    "CREATE", "TRUNCATE", "REPLACE", "GRANT", "REVOKE",
    "EXECUTE", "EXEC", "CALL"
]


# ============================================================
# SCHEMA EXTRACTION (RAW, NO REASONING)
# ============================================================

def get_raw_schema() -> str:
    """
    Get raw database schema as plain text.
    
    This is intentionally simple - just table names and columns.
    NO relationship analysis, NO data sampling, NO context.
    
    This mimics what a naive approach would have access to.
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        
        schema_lines = ["DATABASE SCHEMA:", ""]
        
        for (table_name,) in tables:
            if table_name.startswith('sqlite_'):
                continue
            
            # Get columns (just names and types)
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            col_list = [f"{col[1]} ({col[2]})" for col in columns]
            schema_lines.append(f"Table: {table_name}")
            schema_lines.append(f"  Columns: {', '.join(col_list)}")
            schema_lines.append("")
        
        conn.close()
        return "\n".join(schema_lines)
        
    except Exception as e:
        return f"Error reading schema: {str(e)}"


# ============================================================
# NAIVE SQL GENERATION (SINGLE LLM CALL)
# ============================================================

def generate_naive_sql(question: str, schema: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """
    Generate SQL using a SINGLE LLM call with NO reasoning.
    
    This is the "naive baseline" approach:
    - No schema exploration
    - No clarification
    - No validation
    - No retries
    
    Args:
        question: The user's natural language question
        schema: Optional schema string (if None, will be fetched)
    
    Returns:
        Tuple of (generated_sql, error_message)
        If successful: (sql_string, None)
        If failed: ("", error_message)
    """
    if schema is None:
        schema = get_raw_schema()
    
    # Single-shot prompt (intentionally simple)
    prompt = f"""You are a SQL generator. Convert the question to SQL.

{schema}

Question: {question}

Generate a valid SQLite query. Return ONLY the SQL, nothing else.
Do not explain. Do not add comments. Just the SQL query."""

    try:
        # Single LLM call - no retries
        response = completion(
            model="groq/llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1  # Low temperature for consistency
        )
        
        sql = response.choices[0].message.content.strip()
        
        # Basic cleanup (remove markdown if present)
        sql = sql.replace("```sql", "").replace("```", "").strip()
        
        # Remove any explanation text that might have leaked through
        if "SELECT" in sql.upper():
            # Find the first SELECT and take from there
            start_idx = sql.upper().find("SELECT")
            sql = sql[start_idx:]
            
            # Remove trailing explanation
            for end_marker in ["\n\n", "\nNote:", "\nExplanation:", "\n--"]:
                if end_marker in sql:
                    sql = sql[:sql.find(end_marker)]
        
        return sql.strip(), None
        
    except Exception as e:
        return "", f"LLM generation failed: {str(e)}"


# ============================================================
# SAFETY CHECK (PRE-EXECUTION)
# ============================================================

def is_sql_safe(sql: str) -> Tuple[bool, str]:
    """
    Check if SQL is safe to execute.
    
    Blocks any query containing destructive keywords.
    This is the ONLY safety measure in the naive approach.
    
    Returns:
        Tuple of (is_safe, reason)
    """
    sql_upper = sql.upper()
    
    for keyword in UNSAFE_KEYWORDS:
        # Check for keyword as a word (not part of another word)
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, sql_upper):
            return False, f"Blocked: Query contains '{keyword}' (destructive operation)"
    
    return True, ""


# ============================================================
# SAFE EXECUTION
# ============================================================

def execute_naive_sql(sql: str, validate_safety: bool = True) -> NaiveResult:
    """
    Execute naive-generated SQL with safety checks.
    
    This wraps execution in try/except and blocks unsafe queries.
    
    Args:
        sql: The SQL query to execute
        validate_safety: Whether to check for unsafe keywords
    
    Returns:
        NaiveResult with status, data, or error
    """
    # Safety check
    if validate_safety:
        is_safe, reason = is_sql_safe(sql)
        if not is_safe:
            return NaiveResult(
                status=NaiveStatus.BLOCKED_UNSAFE,
                generated_sql=sql,
                error_message=reason
            )
    
    # Execute with protection
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        column_names = [desc[0] for desc in cursor.description] if cursor.description else []
        data = [dict(row) for row in rows]
        
        conn.close()
        
        return NaiveResult(
            status=NaiveStatus.SUCCESS,
            generated_sql=sql,
            result_data=data,
            row_count=len(data),
            column_names=column_names
        )
        
    except sqlite3.Error as e:
        return NaiveResult(
            status=NaiveStatus.EXECUTION_ERROR,
            generated_sql=sql,
            error_message=f"SQL Error: {str(e)}"
        )
    except Exception as e:
        return NaiveResult(
            status=NaiveStatus.EXECUTION_ERROR,
            generated_sql=sql,
            error_message=f"Execution Error: {str(e)}"
        )


# ============================================================
# MAIN INTERFACE
# ============================================================

def run_naive_query(question: str) -> NaiveResult:
    """
    Run a complete naive NL→SQL pipeline.
    
    Steps:
    1. Get raw schema
    2. Single LLM call to generate SQL
    3. Safety check
    4. Execute (if safe)
    
    This is the BASELINE for comparison with the multi-agent system.
    
    Args:
        question: User's natural language question
    
    Returns:
        NaiveResult with generation/execution outcome
    """
    # Step 1: Get schema
    schema = get_raw_schema()
    
    # Step 2: Generate SQL (single shot)
    sql, gen_error = generate_naive_sql(question, schema)
    
    if gen_error:
        return NaiveResult(
            status=NaiveStatus.GENERATION_ERROR,
            generated_sql="",
            error_message=gen_error
        )
    
    if not sql:
        return NaiveResult(
            status=NaiveStatus.GENERATION_ERROR,
            generated_sql="",
            error_message="LLM returned empty response"
        )
    
    # Step 3 & 4: Safety check and execute
    return execute_naive_sql(sql)


# ============================================================
# COMPARISON HELPER
# ============================================================

def format_naive_result_for_display(result: NaiveResult) -> Dict[str, Any]:
    """
    Format naive result for UI display.
    
    Returns a dictionary suitable for Streamlit/CLI rendering.
    """
    status_labels = {
        NaiveStatus.SUCCESS: ("✅ Success", "success"),
        NaiveStatus.GENERATION_ERROR: ("❌ Generation Failed", "error"),
        NaiveStatus.EXECUTION_ERROR: ("❌ Execution Error", "error"),
        NaiveStatus.BLOCKED_UNSAFE: ("🛡️ Blocked (Unsafe)", "blocked"),
    }
    
    label, badge_type = status_labels.get(result.status, ("❓ Unknown", "unknown"))
    
    return {
        "status_label": label,
        "badge_type": badge_type,
        "sql": result.generated_sql or "No SQL generated",
        "error": result.error_message,
        "row_count": result.row_count,
        "columns": result.column_names or [],
        "data_preview": result.result_data[:5] if result.result_data else [],
        "is_success": result.is_success
    }


# ============================================================
# DISCLAIMER TEXT
# ============================================================

NAIVE_DISCLAIMER = """
**⚠️ Baseline: Single-shot NL→SQL (for comparison only)**

This naive approach uses:
- ONE LLM call with raw schema
- NO schema reasoning or exploration
- NO clarification of ambiguous terms  
- NO validation or safety checks (except blocking destructive SQL)
- NO self-correction or retries

It exists to demonstrate WHERE the multi-agent approach provides value.
"""

NAIVE_COMPARISON_LABEL = "Baseline: Single-shot NL→SQL (no reasoning, no correction)"
