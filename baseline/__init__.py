"""
Baseline module for NL→SQL comparison.

This module provides a DELIBERATELY SIMPLE naive approach
for comparison with the multi-agent system.

NOT for production use - demonstration only.
"""

from .naive_sql_generator import (
    run_naive_query,
    generate_naive_sql,
    execute_naive_sql,
    get_raw_schema,
    is_sql_safe,
    NaiveResult,
    NaiveStatus,
    format_naive_result_for_display,
    NAIVE_DISCLAIMER,
    NAIVE_COMPARISON_LABEL
)

__all__ = [
    "run_naive_query",
    "generate_naive_sql",
    "execute_naive_sql",
    "get_raw_schema",
    "is_sql_safe",
    "NaiveResult",
    "NaiveStatus",
    "format_naive_result_for_display",
    "NAIVE_DISCLAIMER",
    "NAIVE_COMPARISON_LABEL"
]
