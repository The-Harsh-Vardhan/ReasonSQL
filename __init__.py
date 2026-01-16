# NL2SQL Multi-Agent System Package
"""
A sophisticated Natural Language to SQL system using CrewAI multi-agent architecture.
"""

__version__ = "1.0.0"
__author__ = "NL2SQL Team"

from orchestrator import NL2SQLOrchestrator, run_query
from models import (
    QueryIntent, ExecutionStatus, SchemaContext, IntentClassification,
    QueryPlan, ExecutionResult, FinalResponse, ReasoningTrace
)

__all__ = [
    "NL2SQLOrchestrator",
    "run_query",
    "QueryIntent",
    "ExecutionStatus", 
    "SchemaContext",
    "IntentClassification",
    "QueryPlan",
    "ExecutionResult",
    "FinalResponse",
    "ReasoningTrace"
]
