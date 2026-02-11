"""
Configuration management for NL2SQL Multi-Agent System.

This module handles all configuration loading and validation.
It fails fast on missing required configuration to prevent
runtime errors and provide clear error messages.
"""
import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
try:
    from crewai import LLM
except ImportError:
    LLM = None

# Load environment variables from .env file
# interpolate=False prevents $VAR expansion in values (important for passwords with $ characters)
load_dotenv(interpolate=False)


# =============================================================================
# CONFIGURATION VALIDATION
# =============================================================================

class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


def _get_required_env(key: str, error_message: str) -> str:
    """Get required environment variable or raise ConfigurationError."""
    value = os.getenv(key)
    if not value:
        raise ConfigurationError(f"❌ {error_message}\n   Set {key} in your .env file.")
    return value


def _validate_api_key(provider: str) -> str:
    """
    Validate that an API key is configured for the specified provider.
    Returns the API key if valid, raises ConfigurationError otherwise.
    """
    placeholder_values = [
        "your_groq_api_key_here",
        "your_google_api_key_here",
        "gsk_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        "AIzaSy_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        "",
        None
    ]
    
    if provider == "groq":
        key = os.getenv("GROQ_API_KEY")
        if key in placeholder_values:
            raise ConfigurationError(
                "❌ GROQ_API_KEY is not configured!\n"
                "   1. Get your free API key at: https://console.groq.com/keys\n"
                "   2. Add it to your .env file: GROQ_API_KEY=gsk_your_actual_key"
            )
        return key
    elif provider == "gemini":
        key = os.getenv("GOOGLE_API_KEY")
        if key in placeholder_values:
            raise ConfigurationError(
                "❌ GOOGLE_API_KEY is not configured!\n"
                "   1. Get your API key at: https://makersuite.google.com/app/apikey\n"
                "   2. Add it to your .env file: GOOGLE_API_KEY=AIzaSy_your_actual_key"
            )
        return key
    else:
        raise ConfigurationError(f"❌ Unknown LLM provider: {provider}")


def validate_configuration(skip_api_check: bool = False) -> dict:
    """
    Validate all configuration and return validated config dict.
    
    Args:
        skip_api_check: If True, skip API key validation (useful for setup.py)
    
    Returns:
        Dictionary with validated configuration values
    
    Raises:
        ConfigurationError: If any required configuration is missing
    """
    errors = []
    config = {}
    
    # Check LLM provider
    config['llm_provider'] = os.getenv("LLM_PROVIDER", "gemini").lower()
    if config['llm_provider'] not in ["groq", "gemini"]:
        errors.append(f"LLM_PROVIDER must be 'groq' or 'gemini', got: {config['llm_provider']}")
    
    # Check API key (unless skipped)
    if not skip_api_check:
        try:
            config['api_key'] = _validate_api_key(config['llm_provider'])
        except ConfigurationError as e:
            errors.append(str(e))
    
    # Check database path
    db_path = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "chinook.db"))
    config['database_path'] = db_path
    if not Path(db_path).exists():
        errors.append(
            f"❌ Database not found at: {db_path}\n"
            "   Run 'python setup.py' to download the Chinook database."
        )
    
    # Collect all errors
    if errors:
        error_msg = "\n\nConfiguration Errors:\n" + "\n".join(f"  • {e}" for e in errors)
        error_msg += "\n\nRun 'python setup.py' to fix these issues."
        raise ConfigurationError(error_msg)
    
    return config


# =============================================================================
# BASE PATHS
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

# PostgreSQL connection string (for Supabase/cloud deployments)
# Format: postgresql://user:password@host:port/database
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# SQLite database path (for local development)
DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "chinook.db"))

# Auto-detect database type
def get_db_type() -> str:
    """Detect database type from environment variables."""
    if DATABASE_URL and (DATABASE_URL.startswith("postgres") or DATABASE_URL.startswith("postgresql")):
        return "postgresql"
    return "sqlite"

DATABASE_TYPE = get_db_type()

# =============================================================================
# LLM CONFIGURATION
# =============================================================================

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash")

# Token & call limits (prevents quota exhaustion)
MAX_LLM_TOKENS = int(os.getenv("MAX_LLM_TOKENS", "1024"))
MAX_LLM_CALLS_PER_QUERY = int(os.getenv("MAX_LLM_CALLS_PER_QUERY", "5"))

# Provider fallback chain configuration
PRIMARY_PROVIDER = os.getenv("PRIMARY_PROVIDER", "gemini").lower()
SECONDARY_PROVIDER = os.getenv("SECONDARY_PROVIDER", "groq").lower()
TERTIARY_PROVIDER = os.getenv("TERTIARY_PROVIDER", "qwen").lower()
ENABLE_QWEN_FALLBACK = os.getenv("ENABLE_QWEN_FALLBACK", "false").lower() == "true"

# Groq safety settings (prevent accidental use of quota-hungry models)
GROQ_ALLOWED_MODELS = os.getenv("GROQ_ALLOWED_MODELS", "groq/llama-3.1-8b-instant,groq/llama3-8b-8192").split(",")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "groq/llama-3.1-8b-instant")

# =============================================================================
# SYSTEM SETTINGS
# =============================================================================

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "100"))
VERBOSE = os.getenv("VERBOSE", "false").lower() == "true"

# =============================================================================
# SAFETY CONSTRAINTS (HARDCODED - DO NOT MAKE CONFIGURABLE)
# =============================================================================

# These keywords are NEVER allowed in any query
FORBIDDEN_KEYWORDS = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE"]

# Maximum rows that can be returned
MAX_RESULT_ROWS = 1000


# =============================================================================
# LLM FACTORY
# =============================================================================

def get_llm(validate: bool = True) -> LLM:
    """
    Initialize and return the configured LLM instance.
    
    This function validates the API key before creating the LLM instance
    to provide clear error messages if misconfigured.
    
    Args:
        validate: If True, validate API key first (set False for testing)
    
    Returns:
        Configured LLM instance
    
    Raises:
        ConfigurationError: If API key is missing or invalid
    """
    # Validate API key exists and is not a placeholder
    if validate:
        api_key = _validate_api_key(LLM_PROVIDER)
    else:
        api_key = os.getenv("GROQ_API_KEY") if LLM_PROVIDER == "groq" else os.getenv("GOOGLE_API_KEY")
    
    if LLM_PROVIDER == "groq":
        if LLM is None:
            raise ConfigurationError("CrewAI not installed! Cannot use Groq provider.")
        return LLM(
            model=LLM_MODEL,
            temperature=0.1,  # Low temperature for consistent SQL generation
            api_key=api_key
        )
    elif LLM_PROVIDER == "gemini":
        # For Gemini, CrewAI's LiteLLM reads from GEMINI_API_KEY env var
        if not os.getenv("GEMINI_API_KEY"):
            os.environ["GEMINI_API_KEY"] = api_key
            
        if LLM is None:
             # Fallback: if CrewAI is missing, we can't return an LLM object
             # But BatchOptimizedOrchestrator doesn't Use this get_llm function!
             # It uses LLMClient directly.
             # This function is only for legacy agents.
             raise ConfigurationError("CrewAI not installed! Legacy agents cannot run.")
             
        return LLM(
            model=LLM_MODEL,  # Should be gemini/gemini-2.5-flash format
            temperature=0.1
        )
    else:
        raise ConfigurationError(f"Unsupported LLM provider: {LLM_PROVIDER}. Use 'groq' or 'gemini'.")


def get_database_uri() -> str:
    """Get SQLite database URI."""
    return f"sqlite:///{DATABASE_PATH}"


def get_gemini_key_count() -> int:
    """Count number of configured Gemini API keys (GEMINI_API_KEY_1..9 + fallback)."""
    count = 0
    # Check numbered keys
    for i in range(1, 10):
        if os.getenv(f"GEMINI_API_KEY_{i}"):
            count += 1
            
    # Check standard keys if no numbered keys found
    if count == 0 and (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        count = 1
        
    # If numbered keys exist AND standard key exists, standard key is usually 
    # included as fallback in GeminiClient, so total is effectively count.
    # But GeminiClient logic is: numbered keys FIRST, then standard key if no numbered keys.
    # Wait, looking at llm_client.py lines 140-150:
    # It adds numbered keys. If NONE, it adds standard key.
    # So effective count is exactly as calculated above.
    
    return max(1, count)


# Agent-specific prompts
AGENT_PROMPTS = {
    # ============================================================
    # CORE AGENTS (7)
    # ============================================================
    "schema_explorer": """You are a database schema expert. Your role is to:
1. Inspect and understand database structures
2. Identify tables, columns, data types, and relationships
3. Detect foreign key relationships and primary keys
4. Provide clear, structured summaries of the schema
Never make assumptions about table contents - only report what exists.""",

    "intent_analyzer": """You are an intent classification expert. Your role is to:
1. Analyze user queries to determine their intent
2. Classify queries as: DATA_QUERY, META_QUERY, or AMBIGUOUS
3. Identify which tables and columns might be relevant
4. Flag queries that need clarification
Be conservative - if unsure, mark as AMBIGUOUS.""",

    "query_planner": """You are a SQL query architect. Your role is to:
1. Design efficient query plans based on schema and intent
2. Identify required tables, joins, and filters
3. ALWAYS enforce these safety rules:
   - Never use SELECT * - specify exact columns
   - Always include LIMIT clause (default: 100)
   - Use appropriate JOIN types
4. Consider query performance and readability
5. Document your reasoning for each decision""",

    "sql_generator": """You are a precise SQL generator. Your role is to:
1. Convert query plans into valid SQLite SQL
2. Output ONLY the SQL query - no explanations
3. Ensure proper syntax and escaping
4. Follow the exact specifications from the query plan
5. Never add SELECT * or remove LIMIT clauses""",

    "sql_executor": """You are a safe SQL executor. Your role is to:
1. Validate SQL before execution (read-only, has LIMIT, no SELECT *)
2. Execute queries and capture results
3. Report errors clearly with context
4. Handle empty results gracefully
5. Never execute dangerous operations""",

    "self_correction": """You are a query debugging expert. Your role is to:
1. Analyze why a query failed or returned unexpected results
2. Identify the root cause (schema mismatch, wrong join, typo, etc.)
3. Propose a corrected query plan with clear reasoning
4. Learn from the error to prevent similar issues
5. If stuck after multiple attempts, explain what went wrong""",

    "response_synthesizer": """You are a data communication expert. Your role is to:
1. Convert query results into human-readable explanations
2. Summarize large result sets meaningfully
3. Explain what was queried and why
4. Handle empty results with helpful context
5. Make technical data accessible to non-technical users""",

    # ============================================================
    # NEW AGENTS (5)
    # ============================================================
    "clarification": """You are an ambiguity resolution specialist. Your role is to:
1. Detect vague or ambiguous terms in user queries
2. Identify terms that need clarification:
   - Temporal: "recent", "latest", "old", "new"
   - Quantitative: "best", "top", "most popular", "high-value"
   - Scope: "some", "few", "many", "all"
3. Generate specific, actionable clarification questions
4. If clarification isn't possible, provide reasonable defaults
5. ALWAYS state your assumptions explicitly

Examples:
- "recent orders" → "What time period? Last 7 days, 30 days, or year?"
- "best customers" → "By total revenue, order frequency, or recency?"
- "top artists" → "Top 5, 10, or another number? By sales or track count?"

Never proceed with ambiguity - either clarify or state your assumption.""",

    "safety_validator": """You are the SQL security gatekeeper. Your role is to:
1. Act as the FINAL checkpoint before any SQL execution
2. Inspect every query for security violations
3. Produce an explicit APPROVED or REJECTED decision

MANDATORY CHECKS:
✓ Read-only: Must be SELECT or WITH...SELECT only
✓ No SELECT *: All columns must be explicitly named
✓ Has LIMIT: Every query must have a LIMIT clause
✓ No forbidden keywords: INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE

REJECTION PROTOCOL:
- State which rule was violated
- Quote the violating portion of the SQL
- Explain how to fix it

You are the last line of defense. Be strict. No exceptions.""",

    "query_decomposer": """You are a complex query decomposition expert. Your role is to:
1. Analyze complex, multi-step natural language queries
2. Break them into atomic sub-problems that can be solved individually
3. Identify when advanced SQL constructs are needed:
   - CTEs (WITH clauses) for reusable subqueries
   - Subqueries for nested conditions
   - Set operations (UNION, INTERSECT, EXCEPT)
   - Window functions for rankings

DECOMPOSITION PATTERNS:
- "A AND B" → Intersection: customers who bought BOTH genres
- "A OR B" → Union: customers who bought EITHER genre
- "A NOT B" → Except/Left Anti-join: customers who bought A but not B
- "most/least/top" → Aggregation + ORDER BY + LIMIT
- "compare X to Y" → Two queries, then comparison

Output a numbered step-by-step plan.""",

    "data_explorer": """You are a data exploration analyst. Your role is to:
1. Sample actual data BEFORE making query decisions
2. Explore value distributions to inform queries
3. Identify date ranges, numerical ranges, categorical values

KEY EXPLORATIONS:
- Date columns: What's the min/max date range?
- Numerical columns: What's the value distribution?
- Categorical columns: What distinct values exist?
- Foreign keys: Are there orphan records?

USE CASES:
- "recent orders" → First check: What date range exists in data?
- "high-value customers" → First check: What's the revenue distribution?
- "popular genres" → First check: What genres exist and their frequencies?

Always provide concrete numbers: "Data spans 2009-01-01 to 2013-12-31".""",

    "result_validator": """You are a result sanity checker. Your role is to:
1. Validate that query results make logical sense
2. Detect anomalies that indicate errors
3. Verify results align with the original question

ANOMALY DETECTION:
✗ Negative counts (COUNT should never be negative)
✗ Negative revenue/prices where they shouldn't exist
✗ NULL values in columns that shouldn't have them
✗ Result count seems impossibly large or small
✗ Results don't match the question's intent

VALIDATION PROCESS:
1. Check data types are as expected
2. Verify aggregations are sensible
3. Cross-check against known constraints
4. Flag suspicious patterns

If anomalies found, recommend re-running or investigating."""
}
