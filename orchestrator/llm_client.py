"""
LLM Client Abstraction with Automatic Fallback.

PURPOSE:
========
Provides a unified interface for multiple LLM providers (Gemini, Groq)
with automatic fallback when the primary provider fails.

WHY THIS EXISTS:
================
Gemini free-tier has strict rate limits (RPM/RPD) that can be exhausted
during live demos. This module ensures the system continues working by
automatically falling back to Groq when Gemini quota is exceeded.

ARCHITECTURE:
=============
- LLMClient: Abstract base class defining the interface
- GeminiClient: Gemini-specific implementation
- GroqClient: Groq-specific implementation
- MultiProviderLLM: Orchestrates fallback logic

USAGE:
======
    llm = MultiProviderLLM(
        primary="gemini",
        fallback="groq",
        verbose=True
    )
    
    response = llm.generate(prompt, metadata={...})
    # Automatically tries Gemini, falls back to Groq if needed
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import time

from litellm import completion
from config import VERBOSE


# ============================================================
# DATA MODELS
# ============================================================

class LLMProvider(Enum):
    """Supported LLM providers."""
    GEMINI = "gemini"
    GROQ = "groq"


@dataclass
class LLMResponse:
    """Standardized LLM response."""
    content: str
    provider: LLMProvider
    model: str
    tokens_used: int = 0
    fallback_occurred: bool = False
    fallback_reason: Optional[str] = None


class LLMError(Exception):
    """Base exception for LLM errors."""
    pass


class RateLimitError(LLMError):
    """Raised when rate limit is exceeded."""
    pass


class QuotaExceededError(LLMError):
    """Raised when quota is exhausted."""
    pass


# ============================================================
# ABSTRACT LLM CLIENT
# ============================================================

class LLMClient(ABC):
    """
    Abstract base class for LLM providers.
    
    All providers must implement this interface to ensure
    compatibility with the fallback system.
    """
    
    def __init__(self, model: str, verbose: bool = VERBOSE):
        self.model = model
        self.verbose = verbose
        self.call_count = 0
    
    @abstractmethod
    def generate(self, prompt: str, metadata: Dict[str, Any] = None) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: The prompt to send to the LLM
            metadata: Optional metadata about the request
        
        Returns:
            LLMResponse with content and provider info
        
        Raises:
            RateLimitError: When rate limit is exceeded
            QuotaExceededError: When quota is exhausted
            LLMError: For other errors
        """
        pass
    
    def _log(self, message: str):
        """Log if verbose mode is on."""
        if self.verbose:
            print(f"[{self.__class__.__name__}] {message}")


# ============================================================
# GEMINI CLIENT
# ============================================================

class GeminiClient(LLMClient):
    """
    Gemini LLM provider implementation with automatic key rotation.
    
    Uses LiteLLM for Gemini API calls.
    Automatically rotates through multiple API keys when quota is exhausted.
    """
    
    def __init__(self, model: str = "gemini/gemini-2.0-flash-exp", verbose: bool = VERBOSE):
        super().__init__(model, verbose)
        self.provider = LLMProvider.GEMINI
        
        # Load all available Gemini API keys
        import os
        self.api_keys = []
        for i in range(1, 10):  # Support up to 9 keys
            key = os.getenv(f"GEMINI_API_KEY_{i}")
            if key:
                self.api_keys.append(key)
        
        # Fallback to GOOGLE_API_KEY/GEMINI_API_KEY if no numbered keys
        if not self.api_keys:
            main_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if main_key:
                self.api_keys.append(main_key)
        
        if not self.api_keys:
            raise ValueError("No Gemini API keys configured")
        
        self.current_key_index = 0
        self.exhausted_keys = set()
        self._log(f"Loaded {len(self.api_keys)} Gemini API key(s)")
    
    def generate(self, prompt: str, metadata: Dict[str, Any] = None) -> LLMResponse:
        """Generate response from Gemini with automatic key rotation."""
        import os
        
        # Try all available keys
        attempts = 0
        max_attempts = len(self.api_keys)
        
        while attempts < max_attempts:
            # Skip exhausted keys
            if self.current_key_index in self.exhausted_keys:
                self._rotate_key()
                attempts += 1
                continue
            
            current_key = self.api_keys[self.current_key_index]
            key_num = self.current_key_index + 1
            
            self._log(f"Calling Gemini ({self.model}) with key #{key_num}...")
            
            # Set the API key for this attempt
            os.environ["GEMINI_API_KEY"] = current_key
            
            try:
                response = completion(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3
                )
                
                self.call_count += 1
                content = response.choices[0].message.content
                
                self._log(f"✓ Gemini call successful with key #{key_num} (Total: {self.call_count})")
                
                return LLMResponse(
                    content=content,
                    provider=self.provider,
                    model=self.model,
                    tokens_used=response.usage.total_tokens if hasattr(response, 'usage') else 0
                )
            
            except Exception as e:
                error_str = str(e).lower()
                
                # Detect quota/rate limit errors - rotate key
                if "429" in error_str or "rate limit" in error_str or "quota" in error_str or "403" in error_str or "forbidden" in error_str:
                    if "quota" in error_str or "exceeded your current quota" in error_str or "403" in error_str:
                        self._log(f"✗ Gemini key #{key_num} quota exhausted, rotating...")
                        self.exhausted_keys.add(self.current_key_index)
                        self._rotate_key()
                        attempts += 1
                        continue
                    else:
                        self._log(f"✗ Gemini key #{key_num} rate limit hit, rotating...")
                        self.exhausted_keys.add(self.current_key_index)
                        self._rotate_key()
                        attempts += 1
                        continue
                
                # Other errors - don't rotate, just fail
                else:
                    self._log(f"✗ Gemini error with key #{key_num}: {e}")
                    raise LLMError(f"Gemini API error: {e}")
        
        # All keys exhausted
        self._log(f"✗ All {len(self.api_keys)} Gemini API keys exhausted")
        raise QuotaExceededError(f"All {len(self.api_keys)} Gemini API keys exhausted")
    
    def _rotate_key(self):
        """Rotate to next available key."""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)


# ============================================================
# GROQ CLIENT
# ============================================================

class GroqClient(LLMClient):
    """
    Groq LLM provider implementation.
    
    Uses LiteLLM for Groq API calls.
    Serves as fallback when Gemini fails.
    """
    
    def __init__(self, model: str = "groq/llama-3.3-70b-versatile", verbose: bool = VERBOSE):
        super().__init__(model, verbose)
        self.provider = LLMProvider.GROQ
    
    def generate(self, prompt: str, metadata: Dict[str, Any] = None) -> LLMResponse:
        """Generate response from Groq."""
        self._log(f"Calling Groq ({self.model})...")
        
        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            self.call_count += 1
            content = response.choices[0].message.content
            
            self._log(f"✓ Groq call successful (Total: {self.call_count})")
            
            return LLMResponse(
                content=content,
                provider=self.provider,
                model=self.model,
                tokens_used=response.usage.total_tokens if hasattr(response, 'usage') else 0
            )
        
        except Exception as e:
            self._log(f"✗ Groq error: {e}")
            raise LLMError(f"Groq API error: {e}")


# ============================================================
# MULTI-PROVIDER LLM (FALLBACK ORCHESTRATOR)
# ============================================================

class MultiProviderLLM:
    """
    LLM client with automatic fallback.
    
    FALLBACK LOGIC:
    ===============
    1. Try primary provider (Gemini)
    2. If RateLimitError or QuotaExceededError:
       - Log the failure
       - Switch to fallback provider (Groq)
       - Retry ONCE
    3. If fallback also fails:
       - Abort gracefully
       - Return clear error
    
    RATE LIMIT AWARENESS:
    ====================
    - Tracks whether Gemini quota is known to be exhausted
    - If exhausted, skips Gemini entirely and uses Groq
    - Resets on new session
    
    MAX ATTEMPTS:
    =============
    - 2 attempts per request (Primary → Fallback)
    - No infinite loops
    """
    
    def __init__(
        self,
        primary: str = "gemini",
        fallback: str = "groq",
        gemini_model: str = "gemini/gemini-2.0-flash-exp",
        groq_model: str = "groq/llama-3.1-8b-instant",
        verbose: bool = VERBOSE
    ):
        self.verbose = verbose
        
        # Initialize clients
        self.gemini = GeminiClient(model=gemini_model, verbose=verbose)
        self.groq = GroqClient(model=groq_model, verbose=verbose)
        
        # Set primary and fallback
        self.primary_name = primary
        self.fallback_name = fallback
        
        self.primary = self.gemini if primary == "gemini" else self.groq
        self.fallback = self.groq if fallback == "groq" else self.gemini
        
        # Track quota status
        self.gemini_quota_exhausted = False
        
        # Statistics
        self.stats = {
            "total_calls": 0,
            "gemini_calls": 0,
            "groq_calls": 0,
            "fallbacks": 0
        }
    
    def generate(self, prompt: str, metadata: Dict[str, Any] = None) -> LLMResponse:
        """
        Generate response with automatic fallback.
        
        Flow:
        1. Check if Gemini quota is known to be exhausted
           - If yes, skip directly to Groq
        2. Try primary provider (Gemini)
        3. If rate limit/quota error, fallback to Groq
        4. Return response with fallback metadata
        """
        metadata = metadata or {}
        self.stats["total_calls"] += 1
        
        # If Gemini quota is known to be exhausted, skip directly to Groq
        if self.gemini_quota_exhausted and self.primary_name == "gemini":
            self._log("⚠️ Gemini quota exhausted (known), using Groq directly")
            return self._call_fallback(prompt, metadata, "Gemini quota known to be exhausted")
        
        # Try primary provider
        try:
            self._log(f"→ Attempting primary provider: {self.primary_name.upper()}")
            response = self.primary.generate(prompt, metadata)
            
            # Track successful call
            if self.primary_name == "gemini":
                self.stats["gemini_calls"] += 1
            else:
                self.stats["groq_calls"] += 1
            
            return response
        
        except (RateLimitError, QuotaExceededError) as e:
            # Mark Gemini as exhausted if it's the primary
            if self.primary_name == "gemini":
                self.gemini_quota_exhausted = True
            
            reason = str(e)
            self._log(f"⚠️ Primary provider failed: {reason}")
            self._log(f"→ Falling back to {self.fallback_name.upper()}...")
            
            # Attempt fallback
            return self._call_fallback(prompt, metadata, reason)
        
        except LLMError as e:
            # For non-quota errors, still try fallback once
            self._log(f"⚠️ Primary provider error: {e}")
            self._log(f"→ Attempting fallback to {self.fallback_name.upper()}...")
            
            return self._call_fallback(prompt, metadata, str(e))
    
    def _call_fallback(self, prompt: str, metadata: Dict[str, Any], reason: str) -> LLMResponse:
        """
        Call fallback provider.
        
        Only attempts ONCE - no retries on fallback.
        """
        self.stats["fallbacks"] += 1
        
        try:
            response = self.fallback.generate(prompt, metadata)
            
            # Track fallback call
            if self.fallback_name == "gemini":
                self.stats["gemini_calls"] += 1
            else:
                self.stats["groq_calls"] += 1
            
            # Mark response as fallback
            response.fallback_occurred = True
            response.fallback_reason = reason
            
            self._log(f"✓ Fallback successful using {self.fallback_name.upper()}")
            return response
        
        except Exception as e:
            # Both providers failed
            self._log(f"✗ Fallback also failed: {e}")
            raise LLMError(f"Both providers failed. Primary: {reason}, Fallback: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            **self.stats,
            "gemini_quota_exhausted": self.gemini_quota_exhausted
        }
    
    def reset_quota_status(self):
        """Reset quota exhausted flag (useful for new sessions)."""
        self.gemini_quota_exhausted = False
    
    def _log(self, message: str):
        """Log if verbose mode is on."""
        if self.verbose:
            print(f"[MultiProviderLLM] {message}")


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def create_llm_client(
    primary: str = "gemini",
    fallback: str = "groq",
    verbose: bool = VERBOSE
) -> MultiProviderLLM:
    """
    Create a multi-provider LLM client with fallback.
    
    Args:
        primary: Primary provider ("gemini" or "groq")
        fallback: Fallback provider ("groq" or "gemini")
        verbose: Enable verbose logging
    
    Returns:
        MultiProviderLLM instance
    """
    return MultiProviderLLM(
        primary=primary,
        fallback=fallback,
        verbose=verbose
    )
