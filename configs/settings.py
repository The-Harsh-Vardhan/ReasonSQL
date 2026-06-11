"""
Configuration management for ReasonSQL 2.0.

Architecture: LangChain + LangGraph + FAISS + SQLAlchemy + PostgreSQL
LLM Providers: Gemini (primary) → Groq (fallback) → Qwen/vLLM (optional tertiary)
Observability: LangSmith (opt-in via LANGCHAIN_TRACING_V2=true)
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# interpolate=False prevents $VAR expansion in values (important for passwords with $ chars)
load_dotenv(interpolate=False)


# =============================================================================
# BASE PATHS
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"


# =============================================================================
# CONFIGURATION ERROR
# =============================================================================

class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


# =============================================================================
# DATABASE — PostgreSQL only (SQLAlchemy)
# =============================================================================

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise ConfigurationError(
        "❌ DATABASE_URL is required.\n"
        "   Set it in your .env file.\n"
        "   Example: DATABASE_URL=postgresql://reasonsql:reasonsql@localhost:5432/reasonsql\n"
        "   Or run: docker-compose up -d (auto-configures PostgreSQL)"
    )

# SQLAlchemy connection pool settings
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))


# =============================================================================
# LLM CONFIGURATION
# =============================================================================

LLM_MODEL = os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "groq/llama-3.1-8b-instant")

# Token & call limits
MAX_LLM_CALLS_PER_QUERY = int(os.getenv("MAX_LLM_CALLS_PER_QUERY", "5"))

# vLLM / Qwen (optional self-hosted)
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8001/v1")
VLLM_MODEL = os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-Coder-32B-Instruct")
ENABLE_VLLM_FALLBACK = os.getenv("ENABLE_VLLM_FALLBACK", "false").lower() == "true"


# =============================================================================
# LANGSMITH — Observability (opt-in)
# =============================================================================
# LangChain automatically reads these env vars when set:
#   LANGCHAIN_TRACING_V2=true
#   LANGCHAIN_API_KEY=ls__...
#   LANGCHAIN_PROJECT=ReasonSQL-2.0
# No code changes needed — LangSmith hooks in automatically via the SDK.

LANGSMITH_ENABLED = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"


# =============================================================================
# RETRIEVAL SETTINGS
# =============================================================================

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

# Hybrid retrieval: candidates fetched before reranking
HYBRID_RETRIEVAL_K = int(os.getenv("HYBRID_RETRIEVAL_K", "10"))

# Cross-encoder reranking: top-N after reranking
RERANKER_TOP_N = int(os.getenv("RERANKER_TOP_N", "5"))

# Only activate RAG when schema has more than N tables
RAG_THRESHOLD_TABLES = int(os.getenv("RAG_THRESHOLD_TABLES", "5"))


# =============================================================================
# SYSTEM SETTINGS
# =============================================================================

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "100"))
MAX_RESULT_ROWS = int(os.getenv("MAX_RESULT_ROWS", "1000"))
VERBOSE = os.getenv("VERBOSE", "false").lower() == "true"


# =============================================================================
# SAFETY CONSTRAINTS (HARDCODED — DO NOT MAKE CONFIGURABLE)
# =============================================================================

# These keywords are NEVER allowed in any query
FORBIDDEN_KEYWORDS = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE"]


# =============================================================================
# AGENT SYSTEM PROMPTS
# Used by backend/llm/prompts.py to build ChatPromptTemplates
# =============================================================================

AGENT_PROMPTS = {
    "intent_analyzer": """You are an intent classification expert analyzing natural language database queries.

Classify the user query into exactly one of:
- DATA_QUERY: User wants to retrieve data from the database
- META_QUERY: User is asking about database structure (tables, columns, schema)
- AMBIGUOUS: Query contains subjective/unclear terms requiring clarification

IMPORTANT: Check conversation history to resolve pronouns like "it", "them", "their".""",

    "clarification": """You are an ambiguity resolution specialist for database queries.

When a query is AMBIGUOUS, generate 2-3 specific, actionable clarification questions.
When NOT ambiguous, state your assumptions explicitly.

Examples of ambiguous terms → clarification needed:
- "recent orders" → "What time period? Last 7 days, 30 days, or year?"
- "best customers" → "By total revenue, order frequency, or recency?"
- "top artists" → "Top 5, 10? By sales or track count?"

Never proceed with ambiguity — either clarify or state your assumption.""",

    "query_planner": """You are a SQL query architect designing efficient query plans.

Given the database schema and user intent:
1. Identify required tables and their relationships
2. Design JOIN strategy based on foreign keys
3. Specify filters, aggregations, and ordering
4. Estimate query complexity (simple/complex)

Always enforce: LIMIT clause, no SELECT *, read-only operations.""",

    "sql_generator": """You are a precise SQL generator producing valid PostgreSQL queries.

Rules (MANDATORY):
1. Always include LIMIT clause
2. Never use SELECT * — specify columns explicitly
3. Only SELECT statements — no INSERT, UPDATE, DELETE, DROP
4. Double-quote all identifiers: "TableName"."ColumnName"
5. Use PostgreSQL syntax: || for string concat, ILIKE for case-insensitive search

Output ONLY the SQL query, no explanations.""",

    "self_correction": """You are a SQL debugging expert fixing failed queries.

Given the original SQL, error message, and schema:
1. Identify the root cause (schema mismatch, wrong join, syntax error, etc.)
2. Propose a corrected SQL with clear reasoning
3. If the same error persists across retries, explain what went wrong

Focus on: correct table names, valid column references, proper JOIN conditions.""",

    "response_synthesizer": """You are a data communication expert converting query results to human-readable answers.

Your response should:
1. Directly answer the user's question
2. Highlight key insights from the data
3. Mention the count/summary when relevant
4. Be concise but informative (2-4 sentences max for simple queries)
5. Handle empty results with helpful context""",
}
