"""Config module initialization — ReasonSQL 2.0."""
from .settings import (
    # Database
    DATABASE_URL,
    DB_POOL_SIZE,
    DB_MAX_OVERFLOW,

    # LLM
    LLM_MODEL,
    GROQ_MODEL,
    MAX_LLM_CALLS_PER_QUERY,
    VLLM_BASE_URL,
    VLLM_MODEL,
    ENABLE_VLLM_FALLBACK,

    # LangSmith
    LANGSMITH_ENABLED,

    # Retrieval
    EMBEDDING_MODEL,
    RERANKER_MODEL,
    HYBRID_RETRIEVAL_K,
    RERANKER_TOP_N,
    RAG_THRESHOLD_TABLES,

    # System
    MAX_RETRIES,
    DEFAULT_LIMIT,
    MAX_RESULT_ROWS,
    VERBOSE,

    # Safety
    FORBIDDEN_KEYWORDS,

    # Agent prompts
    AGENT_PROMPTS,

    # Errors
    ConfigurationError,
)

__all__ = [
    "DATABASE_URL",
    "DB_POOL_SIZE",
    "DB_MAX_OVERFLOW",
    "LLM_MODEL",
    "GROQ_MODEL",
    "MAX_LLM_CALLS_PER_QUERY",
    "VLLM_BASE_URL",
    "VLLM_MODEL",
    "ENABLE_VLLM_FALLBACK",
    "LANGSMITH_ENABLED",
    "EMBEDDING_MODEL",
    "RERANKER_MODEL",
    "HYBRID_RETRIEVAL_K",
    "RERANKER_TOP_N",
    "RAG_THRESHOLD_TABLES",
    "MAX_RETRIES",
    "DEFAULT_LIMIT",
    "MAX_RESULT_ROWS",
    "VERBOSE",
    "FORBIDDEN_KEYWORDS",
    "AGENT_PROMPTS",
    "ConfigurationError",
]
