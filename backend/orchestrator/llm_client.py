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
from configs import VERBOSE, MAX_LLM_TOKENS, ENABLE_QWEN_FALLBACK


# ============================================================
# DATA MODELS
# ============================================================

class LLMProvider(Enum):
    """Supported LLM providers."""
    GEMINI = "gemini"
    GROQ = "groq"
    QWEN = "qwen"  # Tertiary fallback only


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
    def generate(self, prompt: str, metadata: Optional[Dict[str, Any]] = None, response_format: Optional[Dict[str, Any]] = None) -> LLMResponse:
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
    
    def __init__(self, model: str = "gemini/gemini-2.0-flash", verbose: bool = VERBOSE):
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
        self.exhausted_keys = {}  # key_index -> timestamp when exhausted
        self.key_cooldown_seconds = 60  # Reset exhausted keys after 60s
        self._log(f"Loaded {len(self.api_keys)} Gemini API key(s)")
    
    def generate(self, prompt: str, metadata: Dict[str, Any] = None, response_format: Optional[Dict[str, Any]] = None) -> LLMResponse:
        """Generate response from Gemini with automatic key rotation."""
        import os
        
        # Auto-reset keys that have cooled down
        now = time.time()
        cooled_keys = [k for k, t in self.exhausted_keys.items() if now - t > self.key_cooldown_seconds]
        for k in cooled_keys:
            self._log(f"🔄 Gemini key #{k+1} cooldown expired, marking as available")
            del self.exhausted_keys[k]
        
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
                    temperature=0.3,
                    response_format=response_format
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
                        self.exhausted_keys[self.current_key_index] = time.time()
                        self._rotate_key()
                        attempts += 1
                        continue
                    else:
                        self._log(f"✗ Gemini key #{key_num} rate limit hit, rotating...")
                        self.exhausted_keys[self.current_key_index] = time.time()
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
    
    CRITICAL: Only 8B models allowed to prevent TPD quota exhaustion.
    70B models will crash the demo with rate limits.
    
    ENFORCED MODELS:
    - llama-3.1-8b-instant (recommended)
    - llama-3.2-8b-instant
    - llama3-8b-8192
    
    FORBIDDEN: llama-3.1-70b-versatile, llama-3.3-70b-versatile
    """
    
    ALLOWED_MODELS = [
        "groq/llama-3.1-8b-instant",
        "groq/llama-3.2-8b-instant",
        "groq/llama3-8b-8192"
    ]
    
    def __init__(self, model: str = "groq/llama-3.1-8b-instant", verbose: bool = VERBOSE):
        # CRITICAL: Hard fail on 70B models
        if model not in self.ALLOWED_MODELS:
            raise ValueError(
                f"🛑 FORBIDDEN: Groq model '{model}' is not allowed!\n"
                f"   Only 8B models permitted: {self.ALLOWED_MODELS}\n"
                f"   70B models exhaust TPD quota and crash demos.\n"
                f"   Use: groq/llama-3.1-8b-instant"
            )
        
        super().__init__(model, verbose)
        self.provider = LLMProvider.GROQ
        self._log(f"✓ Groq initialized with SAFE model: {model}")
    
    def generate(self, prompt: str, metadata: Optional[Dict[str, Any]] = None, response_format: Optional[Dict[str, Any]] = None) -> LLMResponse:
        """Generate response from Groq with strict token limits."""
        self._log(f"Calling Groq ({self.model}) [max_tokens={MAX_LLM_TOKENS}]...")
        
        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,  # Low temperature for consistency
                max_tokens=MAX_LLM_TOKENS,  # HARD CAP - prevents quota exhaustion
                response_format=response_format
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
# QWEN CLIENT (TERTIARY FALLBACK ONLY)
# ============================================================

class QwenClient(LLMClient):
    """
    Qwen2.5-Coder-32B-Instruct LLM provider implementation.
    
    CRITICAL: This is a TERTIARY fallback ONLY.
    Only used when BOTH Gemini AND Groq have failed.
    
    SAFETY GUARDRAILS:
    - max_tokens capped at 512 (lower than standard 256 for safety)
    - temperature = 0.2 (deterministic)
    - streaming disabled
    - max_retries = 1 (no retry loops)
    - NO self-correction loops allowed
    """
    
    def __init__(self, model: str = "qwen/qwen2.5-coder-32b-instruct", verbose: bool = VERBOSE):
        super().__init__(model, verbose)
        self.provider = LLMProvider.QWEN
    
    def generate(self, prompt: str, metadata: Optional[Dict[str, Any]] = None, response_format: Optional[Dict[str, Any]] = None) -> LLMResponse:
        """Generate response from Qwen with STRICT safety limits."""
        # CRITICAL: Qwen has LOWER token limit for safety
        qwen_max_tokens = min(MAX_LLM_TOKENS, 512)  # Never exceed 512
        
        self._log(f"⚠️  Calling Qwen (TERTIARY FALLBACK) ({self.model}) [max_tokens={qwen_max_tokens}]...")
        self._log(f"⚠️  WARNING: Both Gemini and Groq unavailable - using last-resort fallback")
        
        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,  # Deterministic
                max_tokens=qwen_max_tokens,  # STRICT LIMIT
                stream=False,  # Disable streaming for safety
                response_format=response_format
            )
            
            self.call_count += 1
            content = response.choices[0].message.content
            
            self._log(f"✓ Qwen call successful (Total: {self.call_count})")
            
            return LLMResponse(
                content=content,
                provider=self.provider,
                model=self.model,
                tokens_used=response.usage.total_tokens if hasattr(response, 'usage') else 0
            )
        
        except Exception as e:
            self._log(f"✗ Qwen error (TERTIARY FALLBACK FAILED): {e}")
            raise LLMError(f"Qwen API error (all providers exhausted): {e}")


# ============================================================
# MULTI-PROVIDER LLM (FALLBACK ORCHESTRATOR)
# ============================================================

class MultiProviderLLM:
    """
    LLM client with automatic fallback and graceful quota exhaustion handling.
    
    FALLBACK CHAIN (DETERMINISTIC):
    ================================
    1. PRIMARY: Gemini (gemini-2.0-flash)
       - Fast, high quality, preferred
       - Auto-fallback on quota exhaustion
    
    2. SECONDARY: Groq (llama-3.1-8b-instant ONLY)
       - Used if Gemini hits quota/rate limits
       - 8B model enforced (70B forbidden)
       - No automatic retry if Groq fails
    
    3. TERTIARY: Qwen (DISABLED BY DEFAULT)
       - Controlled by ENABLE_QWEN_FALLBACK flag
       - If disabled: System aborts gracefully when Groq fails
       - If enabled: Last resort with strict limits
    
    GRACEFUL FAILURE:
    =================
    When all enabled providers fail:
    - Returns QuotaExhaustedError with clear message
    - Preserves reasoning trace with provider attempts
    - No hard crash, no partial SQL
    - User sees: "LLM quota exhausted. Please retry later."
    
    RATE LIMIT AWARENESS:
    ====================
    - Tracks which providers are exhausted
    - Skips known-exhausted providers automatically
    - Resets on new session
    """
    
    def __init__(
        self,
        primary: str = "gemini",
        fallback: str = "groq",
        tertiary: Optional[str] = None,  # DISABLED by default (controlled by feature flag)
        gemini_model: str = "gemini/gemini-2.0-flash",
        groq_model: str = "groq/llama-3.1-8b-instant",
        qwen_model: str = "qwen/qwen-2.5-72b-instruct",
        verbose: bool = VERBOSE
    ):
        self.verbose = verbose
        
        # Initialize primary and secondary clients (ALWAYS)
        self.gemini = GeminiClient(model=gemini_model, verbose=verbose)
        self.groq = GroqClient(model=groq_model, verbose=verbose)
        
        # Initialize tertiary client ONLY if enabled
        self.qwen = None
        self.tertiary_enabled = ENABLE_QWEN_FALLBACK and tertiary is not None
        
        if self.tertiary_enabled:
            self._log("⚠️  Qwen tertiary fallback ENABLED")
            self.qwen = QwenClient(model=qwen_model, verbose=verbose)
        else:
            self._log("✓ Qwen tertiary fallback DISABLED (graceful abort on Groq failure)")
        
        # Set fallback chain: Primary → Secondary → (Tertiary if enabled)
        self.primary_name = primary
        self.secondary_name = fallback
        self.tertiary_name = tertiary if self.tertiary_enabled else None
        
        # Map names to clients
        self.clients = {
            "gemini": self.gemini,
            "groq": self.groq,
        }
        if self.qwen:
            self.clients["qwen"] = self.qwen
        
        self.primary = self.clients[primary]
        self.secondary = self.clients[fallback]
        self.tertiary = self.clients[tertiary] if self.tertiary_enabled and tertiary in self.clients else None
        
        # Track quota status per provider
        self.provider_exhausted = {
            "gemini": False,
            "groq": False,
        }
        if self.tertiary_enabled:
            self.provider_exhausted["qwen"] = False
        
        # Statistics
        self.stats = {
            "total_calls": 0,
            "gemini_calls": 0,
            "groq_calls": 0,
            "qwen_calls": 0,
            "secondary_fallbacks": 0,
            "tertiary_fallbacks": 0,
            "graceful_aborts": 0
        }
        
        # Provider attempt tracking (for reasoning trace)
        self.last_provider_attempts = []
    
    def generate(self, prompt: str, metadata: Dict[str, Any] = None, response_format: Optional[Dict[str, Any]] = None) -> LLMResponse:
        """
        Generate response with automatic tertiary fallback.
        
        Flow:
        1. Check if primary is known to be exhausted → skip to secondary
        2. Try primary provider (Gemini)
        3. If fails → Try secondary (Groq)
        4. If fails → Try tertiary (Qwen) as LAST RESORT
        5. If all fail → Abort with clear error
        """
        metadata = metadata or {}
        self.stats["total_calls"] += 1
        
        # Auto-reset provider exhaustion after cooldown (60s)
        # This prevents permanently skipping Gemini after a transient quota hit
        if hasattr(self, '_exhaustion_timestamps'):
            now = time.time()
            for provider, ts in list(self._exhaustion_timestamps.items()):
                if now - ts > 60 and self.provider_exhausted.get(provider, False):
                    self._log(f"🔄 {provider.upper()} cooldown expired, re-enabling")
                    self.provider_exhausted[provider] = False
                    # Also reset GeminiClient's exhausted keys
                    if provider == "gemini" and hasattr(self.gemini, 'exhausted_keys'):
                        self.gemini.exhausted_keys.clear()
        else:
            self._exhaustion_timestamps = {}
        
        # Skip known-exhausted primary provider
        if self.provider_exhausted[self.primary_name]:
            self._log(f"⚠️ {self.primary_name.upper()} quota exhausted (known), skipping to secondary")
            return self._call_secondary(prompt, metadata, f"{self.primary_name} quota known to be exhausted")
            return self._call_secondary(prompt, metadata, f"{self.primary_name} quota known to be exhausted", response_format)
        
        # ATTEMPT 1: Try primary provider
        try:
            self._log(f"→ Attempting PRIMARY provider: {self.primary_name.upper()}")
            response = self.primary.generate(prompt, metadata, response_format)
            
            # Track successful call
            self.stats[f"{self.primary_name}_calls"] += 1
            self._log(f"✓ PRIMARY ({self.primary_name.upper()}) successful")
            
            return response
        
        except (RateLimitError, QuotaExceededError) as e:
            # Mark primary as exhausted with timestamp for auto-reset
            self.provider_exhausted[self.primary_name] = True
            if not hasattr(self, '_exhaustion_timestamps'):
                self._exhaustion_timestamps = {}
            self._exhaustion_timestamps[self.primary_name] = time.time()
            
            reason = str(e)
            self._log(f"⚠️ PRIMARY provider failed: {reason}")
            
            # ATTEMPT 2: Fallback to secondary
            return self._call_secondary(prompt, metadata, reason, response_format)
        
        except LLMError as e:
            # For non-quota errors, still try secondary
            self._log(f"⚠️ PRIMARY provider error: {e}")
            
            return self._call_secondary(prompt, metadata, str(e), response_format)
    
    def _call_secondary(self, prompt: str, metadata: Optional[Dict[str, Any]], primary_reason: str, response_format: Optional[Dict[str, Any]] = None) -> LLMResponse:
        """
        Call secondary fallback provider (Groq).
        
        If secondary fails:
        - If Qwen enabled: Attempt tertiary fallback
        - If Qwen disabled: Graceful abort with QuotaExhaustedError
        """
        self.stats["secondary_fallbacks"] += 1
        self.last_provider_attempts.append({"provider": self.primary_name, "status": "failed", "reason": primary_reason})
        
        # Skip if secondary is known to be exhausted
        if self.provider_exhausted[self.secondary_name]:
            self._log(f"⚠️ {self.secondary_name.upper()} also exhausted (known)")
            
            if self.tertiary_enabled:
                self._log(f"   → Skipping to tertiary fallback (Qwen)")
                return self._call_tertiary(prompt, metadata, primary_reason, f"{self.secondary_name} quota exhausted")
            else:
                self._log(f"   → Qwen disabled, initiating graceful abort")
                return self._graceful_abort(primary_reason, f"{self.secondary_name} quota exhausted")
        
        try:
            self._log(f"→ Attempting SECONDARY provider: {self.secondary_name.upper()}")
            response = self.secondary.generate(prompt, metadata, response_format)
            
            # Track secondary call
            self.stats[f"{self.secondary_name}_calls"] += 1
            self.last_provider_attempts.append({"provider": self.secondary_name, "status": "success"})
            
            # Mark response as fallback
            response.fallback_occurred = True
            response.fallback_reason = f"Primary ({self.primary_name}) failed: {primary_reason}"
            
            self._log(f"✓ SECONDARY ({self.secondary_name.upper()}) successful")
            return response
        
        except (RateLimitError, QuotaExceededError) as e:
            # Mark secondary as exhausted with timestamp for auto-reset
            self.provider_exhausted[self.secondary_name] = True
            if not hasattr(self, '_exhaustion_timestamps'):
                self._exhaustion_timestamps = {}
            self._exhaustion_timestamps[self.secondary_name] = time.time()
            secondary_reason = str(e)
            
            self._log(f"⚠️ SECONDARY provider also failed: {e}")
            self.last_provider_attempts.append({"provider": self.secondary_name, "status": "failed", "reason": secondary_reason})
            
            if self.tertiary_enabled:
                # ATTEMPT 3: Last resort - try tertiary
                self._log(f"   → Attempting tertiary fallback (Qwen)")
                return self._call_tertiary(prompt, metadata, primary_reason, secondary_reason, response_format)
            else:
                # Qwen disabled - graceful abort
                self._log(f"   → Qwen disabled, initiating graceful abort")
                return self._graceful_abort(primary_reason, secondary_reason)
        
        except LLMError as e:
            secondary_reason = str(e)
            self._log(f"⚠️ SECONDARY provider error: {e}")
            self.last_provider_attempts.append({"provider": self.secondary_name, "status": "failed", "reason": secondary_reason})
            
            if self.tertiary_enabled:
                # Try tertiary as last resort
                return self._call_tertiary(prompt, metadata, primary_reason, secondary_reason, response_format)
            else:
                # Qwen disabled - graceful abort
                return self._graceful_abort(primary_reason, secondary_reason)
    
    def _call_tertiary(self, prompt: str, metadata: Optional[Dict[str, Any]], 
                       primary_reason: str, secondary_reason: str, response_format: Optional[Dict[str, Any]] = None) -> LLMResponse:
        """
        Call tertiary fallback provider (Qwen) - LAST RESORT ONLY.
        
        CRITICAL: This is the final attempt. If Qwen fails, entire request fails.
        
        Safety guardrails:
        - max_tokens ≤ 512
        - No retries
        - No self-correction loops
        """
        self.stats["tertiary_fallbacks"] += 1
        
        # Safety check: This should never be called if tertiary is not enabled
        if not self.tertiary_enabled or not self.tertiary or not self.tertiary_name:
            self._log("✗ CRITICAL: _call_tertiary called but tertiary provider not enabled")
            return self._graceful_abort(primary_reason, secondary_reason)
        
        self._log("⚠️⚠️⚠️ CRITICAL: Attempting TERTIARY FALLBACK (LAST RESORT)")
        self._log(f"⚠️ Primary ({self.primary_name}) failed: {primary_reason}")
        self._log(f"⚠️ Secondary ({self.secondary_name}) failed: {secondary_reason}")
        
        try:
            response = self.tertiary.generate(prompt, metadata, response_format)
            
            # Track tertiary call
            self.stats[f"{self.tertiary_name}_calls"] += 1
            self.last_provider_attempts.append({"provider": self.tertiary_name, "status": "success"})
            
            # Mark response as tertiary fallback with WARNING
            response.fallback_occurred = True
            response.fallback_reason = (
                f"Primary ({self.primary_name}) and Secondary ({self.secondary_name}) unavailable. "
                f"Using tertiary fallback: {self.tertiary_name}"
            )
            
            self._log(f"✓ TERTIARY ({self.tertiary_name.upper()}) successful (LAST RESORT)")
            self._log("⚠️ WARNING: Tertiary fallback model used - quality may vary")
            
            return response
        
        except Exception as e:
            # ALL THREE providers failed - graceful abort
            tertiary_reason = str(e)
            self._log(f"✗ TERTIARY provider FAILED: {e}")
            self._log("✗✗✗ CRITICAL: ALL PROVIDERS EXHAUSTED")
            self.last_provider_attempts.append({"provider": self.tertiary_name, "status": "failed", "reason": tertiary_reason})
            
            return self._graceful_abort(primary_reason, secondary_reason, tertiary_reason)
    
    def _graceful_abort(self, primary_reason: str, secondary_reason: str, tertiary_reason: Optional[str] = None) -> LLMResponse:
        """
        Gracefully abort when all enabled providers are exhausted.
        
        Instead of crashing, returns a controlled error that:
        - Preserves reasoning trace with provider attempts
        - Shows clear user message
        - Allows system to fail safely
        """
        self.stats["graceful_aborts"] += 1
        
        # Build failure message
        if self.tertiary_enabled and tertiary_reason:
            error_msg = (
                f"LLM quota temporarily exhausted. All providers unavailable:\n"
                f"  • {self.primary_name.title()}: {primary_reason}\n"
                f"  • {self.secondary_name.title()}: {secondary_reason}\n"
                f"  • {self.tertiary_name.title()}: {tertiary_reason}\n\n"
                f"Please wait a few minutes and retry."
            )
        else:
            error_msg = (
                f"LLM quota temporarily exhausted. All enabled providers unavailable:\n"
                f"  • {self.primary_name.title()}: {primary_reason}\n"
                f"  • {self.secondary_name.title()}: {secondary_reason}\n\n"
                f"Please wait a few minutes and retry, or enable tertiary fallback (Qwen)."
            )
        
        self._log(f"✗ GRACEFUL ABORT: {error_msg}")
        
        # Raise QuotaExceededError instead of hard crash
        raise QuotaExceededError(error_msg)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics including all providers."""
        fallback_chain = f"{self.primary_name} → {self.secondary_name}"
        if self.tertiary_enabled:
            fallback_chain += f" → {self.tertiary_name}"
        else:
            fallback_chain += " → [Graceful Abort]"
        
        return {
            **self.stats,
            "providers_exhausted": self.provider_exhausted,
            "fallback_chain": fallback_chain,
            "last_provider_attempts": self.last_provider_attempts,
            "tertiary_enabled": self.tertiary_enabled
        }
    
    def reset_quota_status(self):
        """Reset quota exhausted flags for all enabled providers (useful for new sessions)."""
        self.provider_exhausted = {
            "gemini": False,
            "groq": False,
        }
        if self.tertiary_enabled:
            self.provider_exhausted["qwen"] = False
        
        self.last_provider_attempts = []
        self._log("✓ Provider quota status reset")
    
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
    tertiary: Optional[str] = None,
    verbose: bool = VERBOSE
) -> MultiProviderLLM:
    """
    Create a multi-provider LLM client with conditional tertiary fallback.
    
    Fallback chain (deterministic):
    - PRIMARY: Gemini (always)
    - SECONDARY: Groq 8B only (always)
    - TERTIARY: Qwen (only if ENABLE_QWEN_FALLBACK=true)
    
    If Qwen disabled:
    - System gracefully aborts when Groq fails
    - No hard crash, clear user message
    - Preserves reasoning trace
    
    Args:
        primary: Primary provider ("gemini")
        fallback: Secondary fallback provider ("groq")
        tertiary: Tertiary provider ("qwen" or None - controlled by ENABLE_QWEN_FALLBACK)
        verbose: Enable verbose logging
    
    Returns:
        MultiProviderLLM instance with safe fallback chain
    """
    # Use ENABLE_QWEN_FALLBACK flag to determine tertiary
    actual_tertiary = "qwen" if ENABLE_QWEN_FALLBACK else None
    
    return MultiProviderLLM(
        primary=primary,
        fallback=fallback,
        tertiary=actual_tertiary,
        verbose=verbose
    )
