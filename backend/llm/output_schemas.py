"""
Pydantic output schemas for LangChain structured output — ReasonSQL 2.0

Used with llm.with_structured_output() to replace brittle JSON parsing.
Each class maps to one agent's expected output format.

Why Pydantic over JSON parsing:
    - Type-safe at the call site (no dict.get() chains)
    - Validation built-in (Field constraints, validators)
    - LangChain injects the schema as function-calling / tool spec
    - Automatic fallback to JSON parsing if provider doesn't support it
"""

from pydantic import BaseModel, Field
from typing import List, Optional


# =============================================================================
# SQL GENERATOR
# =============================================================================

class SQLGeneratorOutput(BaseModel):
    """Structured output from the SQLGenerator agent."""
    sql: str = Field(
        description=(
            "Valid PostgreSQL SQL query. MUST double-quote ALL identifiers: "
            '\"Artist\".\"Name\", \"Album\".\"Title\". Always include LIMIT clause.'
        )
    )
    explanation: str = Field(
        description="One-sentence explanation of what the SQL does"
    )


# =============================================================================
# RESPONSE SYNTHESIZER
# =============================================================================

class ResponseSynthesizerOutput(BaseModel):
    """Structured output from the ResponseSynthesizer agent."""
    answer: str = Field(
        description=(
            "Human-readable answer to the user's question. "
            "Directly addresses the query with specific numbers/names from results."
        )
    )
    key_insights: List[str] = Field(
        default_factory=list,
        description="2-3 key data insights extracted from the results"
    )


# =============================================================================
# SELF-CORRECTION AGENT
# =============================================================================

class SelfCorrectionOutput(BaseModel):
    """Structured output from the SelfCorrectionAgent."""
    root_cause: str = Field(
        description="Root cause of the SQL error (e.g., wrong table name, missing quote)"
    )
    corrected_sql: str = Field(
        description="Fixed PostgreSQL SQL query with all identifiers double-quoted"
    )
    changes_made: List[str] = Field(
        default_factory=list,
        description="List of specific changes made to fix the SQL"
    )


# =============================================================================
# META-QUERY RESPONSE
# =============================================================================

class MetaQueryOutput(BaseModel):
    """Structured output from the MetaQueryAgent."""
    answer: str = Field(
        description="Explanation of the database schema answering the user's question"
    )
    tables_mentioned: List[str] = Field(
        default_factory=list,
        description="Table names discussed in the answer"
    )
