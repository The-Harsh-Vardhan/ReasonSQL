"""Config module initialization."""
from .settings import (
    # Core configuration
    get_llm,
    get_database_uri,
    get_gemini_key_count,
    DATABASE_PATH,
    DATABASE_URL,
    DATABASE_TYPE,
    MAX_RETRIES,
    DEFAULT_LIMIT,
    VERBOSE,
    FORBIDDEN_KEYWORDS,
    MAX_RESULT_ROWS,
    AGENT_PROMPTS,
    # LLM configuration
    LLM_PROVIDER,
    LLM_MODEL,
    MAX_LLM_TOKENS,
    MAX_LLM_CALLS_PER_QUERY,
    # Provider configuration
    PRIMARY_PROVIDER,
    SECONDARY_PROVIDER,
    TERTIARY_PROVIDER,
    ENABLE_QWEN_FALLBACK,
    GROQ_ALLOWED_MODELS,
    GROQ_FALLBACK_MODEL,
    # Validation
    ConfigurationError,
    validate_configuration,
)

__all__ = [
    # Core configuration
    "get_llm",
    "get_database_uri",
    "get_gemini_key_count",
    "DATABASE_PATH",
    "DATABASE_URL",
    "DATABASE_TYPE",
    "MAX_RETRIES",
    "DEFAULT_LIMIT",
    "VERBOSE",
    "FORBIDDEN_KEYWORDS",
    "MAX_RESULT_ROWS",
    "AGENT_PROMPTS",
    # LLM configuration
    "LLM_PROVIDER",
    "LLM_MODEL",
    "MAX_LLM_TOKENS",
    "MAX_LLM_CALLS_PER_QUERY",
    # Provider configuration
    "PRIMARY_PROVIDER",
    "SECONDARY_PROVIDER",
    "TERTIARY_PROVIDER",
    "ENABLE_QWEN_FALLBACK",
    "GROQ_ALLOWED_MODELS",
    "GROQ_FALLBACK_MODEL",
    # Validation
    "ConfigurationError",
    "validate_configuration",
]
