"""
LLM Providers — ReasonSQL 2.0

Provides LangChain-based LLM clients with automatic fallback chain.

Fallback chain (deterministic):
    1. PRIMARY:   Gemini 2.0 Flash (via LiteLLM)
    2. SECONDARY: Groq Llama-3.1-8B (via LiteLLM)
    3. TERTIARY:  Qwen2.5-Coder-32B (via vLLM, optional — requires GPU)

Why LangChain over custom MultiProviderLLM:
    - `.with_fallbacks()` handles provider switching natively
    - LangSmith tracing is automatic (no code changes needed)
    - Structured output parsing via `.with_structured_output()`
    - Chain composition with LCEL (LangChain Expression Language)
    - Built-in retry logic via `langchain_core.runnables`

Why vLLM for Qwen:
    - OpenAI-compatible API endpoint → zero code changes for provider switch
    - GPU-accelerated inference at low latency
    - Self-hosted = zero API cost at inference time
    - Supports PagedAttention for high-throughput serving
"""

import os
import logging
from typing import Optional

from langchain_community.chat_models import ChatLiteLLM
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableWithFallbacks

from configs import (
    LLM_MODEL,
    GROQ_MODEL,
    VLLM_BASE_URL,
    VLLM_MODEL,
    ENABLE_VLLM_FALLBACK,
    VERBOSE,
)

logger = logging.getLogger("reasonsql.llm.providers")


# =============================================================================
# INDIVIDUAL PROVIDER FACTORIES
# =============================================================================

def get_primary_llm(temperature: float = 0.1) -> BaseChatModel:
    """
    Primary LLM: Google Gemini via LiteLLM.

    Model: gemini/gemini-2.0-flash (fast, 15 RPM free tier)
    Temperature: Low for consistent SQL generation

    Returns:
        ChatLiteLLM instance configured for Gemini
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not set. Get one at https://makersuite.google.com/app/apikey"
        )
    return ChatLiteLLM(
        model=LLM_MODEL,
        temperature=temperature,
        verbose=VERBOSE,
    )


def get_fallback_llm(temperature: float = 0.1) -> BaseChatModel:
    """
    Secondary fallback LLM: Groq Llama-3.1-8B via LiteLLM.

    Model: groq/llama-3.1-8b-instant
    Note: 8B model only — 70B models exhaust Groq TPD quota.

    Returns:
        ChatLiteLLM instance configured for Groq
    """
    return ChatLiteLLM(
        model=GROQ_MODEL,
        temperature=temperature,
        max_tokens=1024,
        verbose=VERBOSE,
    )


def get_vllm_llm(temperature: float = 0.1) -> BaseChatModel:
    """
    Tertiary fallback LLM: Qwen2.5-Coder-32B via vLLM.

    Qwen2.5-Coder-32B-Instruct is a state-of-the-art code-focused LLM
    with strong SQL generation capabilities. Served via vLLM which provides
    an OpenAI-compatible REST API endpoint.

    Requirements:
        - vLLM server running (see docker-compose.yml vllm service)
        - ENABLE_VLLM_FALLBACK=true in .env
        - GPU with sufficient VRAM (or CPU with >32GB RAM)

    Returns:
        ChatOpenAI instance pointing at the vLLM endpoint
    """
    return ChatOpenAI(
        base_url=VLLM_BASE_URL,
        api_key="not-needed",          # vLLM doesn't require auth by default
        model=VLLM_MODEL,              # Qwen/Qwen2.5-Coder-32B-Instruct
        temperature=temperature,
        max_tokens=512,                # Conservative limit for tertiary fallback
        verbose=VERBOSE,
    )


# =============================================================================
# FALLBACK CHAIN
# =============================================================================

def get_llm_with_fallback(temperature: float = 0.1) -> BaseChatModel | RunnableWithFallbacks:
    """
    Build a LangChain fallback chain: Gemini → Groq → Qwen (vLLM, optional).

    LangChain's `.with_fallbacks()` automatically:
    - Catches exceptions from the primary provider
    - Retries with the next provider in the chain
    - Preserves full LangSmith traces for each attempt

    The chain is:
        Gemini (primary) →
        Groq 8B (secondary, always enabled) →
        Qwen/vLLM (tertiary, opt-in via ENABLE_VLLM_FALLBACK)

    Args:
        temperature: LLM temperature (default: 0.1 for consistent SQL)

    Returns:
        LangChain runnable with automatic provider fallback
    """
    primary = get_primary_llm(temperature=temperature)
    fallbacks = [get_fallback_llm(temperature=temperature)]

    if ENABLE_VLLM_FALLBACK:
        logger.info(
            "vLLM fallback ENABLED — Qwen (%s @ %s) added to chain",
            VLLM_MODEL,
            VLLM_BASE_URL,
        )
        fallbacks.append(get_vllm_llm(temperature=temperature))
    else:
        logger.debug("vLLM fallback DISABLED (ENABLE_VLLM_FALLBACK=false)")

    if len(fallbacks) == 1:
        logger.info("LLM chain: %s → %s → [abort]", LLM_MODEL, GROQ_MODEL)
    else:
        logger.info("LLM chain: %s → %s → %s", LLM_MODEL, GROQ_MODEL, VLLM_MODEL)

    return primary.with_fallbacks(fallbacks)
