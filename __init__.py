# NL2SQL Multi-Agent System Package
"""
A sophisticated Natural Language to SQL system using CrewAI multi-agent architecture.
"""

__version__ = "1.0.0"
__author__ = "NL2SQL Team"

try:
    from orchestrator import NL2SQLOrchestrator, run_query
    from models import (
        QueryIntent, ExecutionStatus, SchemaContext, IntentClassification,
        QueryPlan, ExecutionResult, FinalResponse, ReasoningTrace
    )
except ImportError:
    # When imported from outside the backend/ directory (e.g. by pytest or API server),
    # these bare imports won't resolve. The proper imports go through backend.orchestrator.
    pass

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
