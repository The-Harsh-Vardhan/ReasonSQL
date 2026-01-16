"""Orchestrator module initialization."""
from .crew_orchestrator import NL2SQLOrchestrator as LegacyOrchestrator, ReasoningTraceCollector, run_query as legacy_run_query
from .enhanced_orchestrator import (
    EnhancedNL2SQLOrchestrator,
    ReasoningTraceCollector as EnhancedTraceCollector,
    run_query as enhanced_run_query,
    detect_ambiguous_terms,
    is_complex_query
)
from .deterministic_orchestrator import (
    DeterministicOrchestrator,
    Step,
    run_query as deterministic_run_query
)
from .quota_optimized_orchestrator import (
    QuotaOptimizedOrchestrator,
    LLMBudget,
    LLMStage,
    BudgetExceededError,
    create_quota_optimized_orchestrator,
    run_query  # Default run_query uses quota-optimized
)

# Default export: Use quota-optimized for Gemini API sustainability
NL2SQLOrchestrator = QuotaOptimizedOrchestrator

__all__ = [
    # RECOMMENDED: Quota-optimized orchestrator (4-6 LLM calls vs 12)
    "QuotaOptimizedOrchestrator",
    "NL2SQLOrchestrator",  # Alias for QuotaOptimizedOrchestrator
    "LLMBudget",
    "LLMStage",
    "BudgetExceededError",
    "create_quota_optimized_orchestrator",
    "run_query",  # Default uses quota-optimized
    # Deterministic orchestrator (full 12 agents, higher LLM usage)
    "DeterministicOrchestrator",
    "Step",
    "deterministic_run_query",
    # Legacy orchestrators (for reference)
    "LegacyOrchestrator",
    "legacy_run_query",
    "EnhancedNL2SQLOrchestrator",
    "EnhancedTraceCollector",
    "enhanced_run_query",
    # Utility functions
    "ReasoningTraceCollector",
    "detect_ambiguous_terms",
    "is_complex_query"
]
