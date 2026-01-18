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
    run_query as quota_run_query
)
from .batch_optimized_orchestrator import (
    BatchOptimizedOrchestrator,
    RateLimiter,
    RateLimitExceeded,
    run_query  # Default run_query uses batch-optimized (5 req/min hard limit)
)
from .json_utils import (
    safe_parse_llm_json,
    extract_first_json_block,
    JSONExtractionError,
    parse_llm_response_with_trace
)

# Default export: Use batch-optimized for HARD rate limiting and agent batching
NL2SQLOrchestrator = BatchOptimizedOrchestrator

__all__ = [
    # RECOMMENDED: Batch-optimized orchestrator (2-5 LLM calls, 5 req/min hard limit)
    "BatchOptimizedOrchestrator",
    "NL2SQLOrchestrator",  # Alias for BatchOptimizedOrchestrator
    "RateLimiter",
    "RateLimitExceeded",
    "run_query",  # Default uses batch-optimized
    # Previous quota-optimized orchestrator (4-6 LLM calls, soft limit)
    "QuotaOptimizedOrchestrator",
    "LLMBudget",
    "LLMStage",
    "BudgetExceededError",
    "create_quota_optimized_orchestrator",
    "quota_run_query",
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
    "is_complex_query",
    # JSON parsing utilities (for extension development)
    "safe_parse_llm_json",
    "extract_first_json_block",
    "JSONExtractionError",
    "parse_llm_response_with_trace"
]
