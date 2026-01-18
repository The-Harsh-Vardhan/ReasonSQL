"""
ReasonSQL Backend Package

This package contains the core NL→SQL reasoning engine:
- orchestrator: Multi-agent pipeline coordination
- agents: 12 specialized AI agents
- tools: Database introspection and execution tools
- adapters: External integrations (naive baseline, etc.)
- llm_router: LLM provider management with fallback
- models: Data models and schemas
"""

from backend.orchestrator import (
    NL2SQLOrchestrator,
    BatchOptimizedOrchestrator,
    run_query
)
from backend.models import (
    ExecutionStatus,
    FinalResponse,
    ReasoningTrace,
    AgentAction
)

__all__ = [
    "NL2SQLOrchestrator",
    "BatchOptimizedOrchestrator", 
    "run_query",
    "ExecutionStatus",
    "FinalResponse",
    "ReasoningTrace",
    "AgentAction"
]
