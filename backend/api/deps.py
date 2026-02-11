"""
Shared dependencies for ReasonSQL API.

Provides:
- Structured logging (replaces print statements)
- Singleton orchestrator (created once, reused per request)
- Database registry (in-memory for MVP)
- Configuration constants for API behavior
"""

import os
import logging
from typing import Dict, Any, Optional

from backend.orchestrator import BatchOptimizedOrchestrator
from configs import VERBOSE


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


# =============================================================================
# CONFIGURATION
# =============================================================================

# Query timeout in seconds (default: 120s)
QUERY_TIMEOUT_SECONDS = int(os.getenv("QUERY_TIMEOUT_SECONDS", "120"))

# Debug endpoints (disabled by default in production)
ENABLE_DEBUG_ENDPOINTS = os.getenv("ENABLE_DEBUG_ENDPOINTS", "false").lower() == "true"


# =============================================================================
# DATABASE REGISTRY (In-Memory for MVP)
# =============================================================================

database_registry: Dict[str, Dict[str, Any]] = {}


# =============================================================================
# SINGLETON ORCHESTRATOR
# =============================================================================

_orchestrator: Optional[BatchOptimizedOrchestrator] = None


def get_orchestrator() -> BatchOptimizedOrchestrator:
    """
    Get or create the singleton orchestrator instance.
    
    The orchestrator is created once and reused across all requests,
    avoiding the overhead of re-initializing on every query.
    """
    global _orchestrator
    if _orchestrator is None:
        logger.info("Creating singleton BatchOptimizedOrchestrator")
        _orchestrator = BatchOptimizedOrchestrator(verbose=VERBOSE)
    return _orchestrator


def reset_orchestrator() -> None:
    """Reset the orchestrator (useful for testing)."""
    global _orchestrator
    _orchestrator = None
