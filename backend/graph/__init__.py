"""
LangGraph Pipeline module for ReasonSQL 2.0.

Multi-agent NL→SQL pipeline implemented as a LangGraph StateGraph.

Public API:
    from backend.graph import build_pipeline, PipelineState

    pipeline = build_pipeline()
    result = await pipeline.ainvoke({"user_query": "..."})
"""

from .state import PipelineState
from .pipeline import build_pipeline, get_pipeline

__all__ = ["PipelineState", "build_pipeline", "get_pipeline"]
