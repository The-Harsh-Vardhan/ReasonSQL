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
    run_query
)

# Default export is the deterministic orchestrator
NL2SQLOrchestrator = DeterministicOrchestrator

__all__ = [
    # RECOMMENDED: Deterministic state-machine orchestrator
    "DeterministicOrchestrator",
    "NL2SQLOrchestrator",  # Alias for DeterministicOrchestrator
    "Step",
    "run_query",
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
