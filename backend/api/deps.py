"""
Shared dependencies for ReasonSQL API — v2.0

Provides:
- Structured logging
- LangGraph pipeline singleton (replaces BatchOptimizedOrchestrator)
- Database registry
- Configuration constants
"""

import os
import logging
from typing import Dict, Any, Optional

from configs import VERBOSE, LANGSMITH_ENABLED


# =============================================================================
# STRUCTURED LOGGING
# =============================================================================

def setup_logging() -> logging.Logger:
    """Configure structured logging for the API."""
    logger = logging.getLogger("reasonsql")

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    return logger


logger = setup_logging()

if LANGSMITH_ENABLED:
    logger.info("✅ LangSmith tracing ENABLED (project: %s)", os.getenv("LANGCHAIN_PROJECT", "default"))
else:
    logger.info("ℹ️  LangSmith tracing DISABLED (set LANGCHAIN_TRACING_V2=true to enable)")


# =============================================================================
# CONFIGURATION
# =============================================================================

QUERY_TIMEOUT_SECONDS = int(os.getenv("QUERY_TIMEOUT_SECONDS", "120"))
ENABLE_DEBUG_ENDPOINTS = os.getenv("ENABLE_DEBUG_ENDPOINTS", "false").lower() == "true"


# =============================================================================
# DATABASE REGISTRY (In-Memory)
# =============================================================================

database_registry: Dict[str, Dict[str, Any]] = {}


# =============================================================================
# LANGGRAPH PIPELINE SINGLETON
# =============================================================================

_pipeline = None


def get_orchestrator():
    """
    Get or create the singleton LangGraph pipeline.

    The compiled pipeline is thread-safe and reused across all requests.
    On first call, it compiles the StateGraph (fast, no model loading).

    Returns:
        Compiled LangGraph Runnable
    """
    global _pipeline
    if _pipeline is None:
        from backend.graph import get_pipeline
        logger.info("Initializing LangGraph NL→SQL pipeline...")
        _pipeline = get_pipeline()
        logger.info("LangGraph pipeline ready.")
    return _pipeline


def reset_orchestrator() -> None:
    """Reset the pipeline singleton (useful for testing)."""
    global _pipeline
    _pipeline = None
