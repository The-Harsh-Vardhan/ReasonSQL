"""
Orchestrator module — ReasonSQL 2.0 compatibility shim.

In v2.0, the orchestrator is replaced by the LangGraph pipeline in backend.graph.
This module exists for backwards compatibility with any code that imports from here.

For new code, import directly from backend.graph:
    from backend.graph import get_pipeline, PipelineState
"""

# Re-export from the new LangGraph pipeline module
from backend.graph import build_pipeline, get_pipeline, PipelineState

# Backwards-compatibility aliases (used by tests and CLI)
NL2SQLOrchestrator = None   # Deprecated — use get_pipeline()
ReasonSQLOrchestrator = None

__all__ = [
    "build_pipeline",
    "get_pipeline",
    "PipelineState",
]
