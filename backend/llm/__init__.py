"""
LLM module for ReasonSQL 2.0.

Provides LangChain-based LLM providers with automatic fallback:
    Gemini → Groq → Qwen (vLLM, optional)

Public API:
    from backend.llm import get_llm, get_llm_with_fallback
    from backend.llm.prompts import REASONING_PROMPT, SQL_GENERATION_PROMPT
"""

from .providers import get_llm_with_fallback, get_primary_llm, get_fallback_llm, get_vllm_llm
from .prompts import (
    REASONING_PROMPT,
    SQL_GENERATION_PROMPT,
    SELF_CORRECTION_PROMPT,
    RESPONSE_SYNTHESIS_PROMPT,
)

__all__ = [
    "get_llm_with_fallback",
    "get_primary_llm",
    "get_fallback_llm",
    "get_vllm_llm",
    "REASONING_PROMPT",
    "SQL_GENERATION_PROMPT",
    "SELF_CORRECTION_PROMPT",
    "RESPONSE_SYNTHESIS_PROMPT",
]
