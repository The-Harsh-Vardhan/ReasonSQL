"""Orchestrator module initialization."""

# Legacy orchestrators — optional (crewai may not be installed)
try:
    from .crew_orchestrator import ReasonSQLOrchestrator as LegacyOrchestrator, ReasoningTraceCollector, run_query as legacy_run_query
except ImportError:
    LegacyOrchestrator = None
    ReasoningTraceCollector = None
    legacy_run_query = None

try:
    from .enhanced_orchestrator import (
        EnhancedReasonSQLOrchestrator,
        ReasoningTraceCollector as EnhancedTraceCollector,
        run_query as enhanced_run_query,
        detect_ambiguous_terms,
        is_complex_query
    )
except ImportError:
    EnhancedReasonSQLOrchestrator = None
    EnhancedTraceCollector = None
    enhanced_run_query = None
    detect_ambiguous_terms = None
    is_complex_query = None

try:
    from .deterministic_orchestrator import (
        DeterministicOrchestrator,
        Step,
        run_query as deterministic_run_query
    )
except ImportError:
    DeterministicOrchestrator = None
    Step = None
    deterministic_run_query = None

try:
    from .quota_optimized_orchestrator import (
        QuotaOptimizedOrchestrator,
        LLMBudget,
        LLMStage,
        BudgetExceededError,
        create_quota_optimized_orchestrator,
        run_query as quota_run_query
    )
except ImportError:
    QuotaOptimizedOrchestrator = None
    LLMBudget = None
    LLMStage = None
    BudgetExceededError = None
    create_quota_optimized_orchestrator = None
    quota_run_query = None

# Primary orchestrator — must succeed
from .batch_optimized_orchestrator import (
    BatchOptimizedOrchestrator,
    RateLimiter,
    RateLimitExceeded,
    run_query  # Default run_query uses batch-optimized (5 req/min hard limit)
)

# Default export: Use batch-optimized for HARD rate limiting and agent batching
ReasonSQLOrchestrator = BatchOptimizedOrchestrator
NL2SQLOrchestrator = ReasonSQLOrchestrator

__all__ = [
    "BatchOptimizedOrchestrator",
    "ReasonSQLOrchestrator",
    "NL2SQLOrchestrator",
    "RateLimiter",
    "RateLimitExceeded",
    "run_query",
]
