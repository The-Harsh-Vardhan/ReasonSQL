"""
Safe LLM Response Parser with Graceful Failure Handling.

PURPOSE:
========
Provides robust JSON parsing for LLM outputs with comprehensive error handling.
Prevents system crashes from invalid/empty/non-JSON responses.

ARCHITECTURE:
=============
- ControlledLLMFailure: Exception for intentional parsing failures
- safe_parse_llm_json(): Single safe parser (MANDATORY for all LLM responses)
- Response validation and structure checking
- Graceful degradation to abort state

USAGE:
======
    from orchestrator.llm_parser import safe_parse_llm_json
    
    try:
        result = safe_parse_llm_json(
            raw_response=llm_output,
            agent_name="IntentAnalyzer",
            provider_name="gemini",
            expected_keys=["action", "reasoning", "output"]
        )
    except ControlledLLMFailure as e:
        # Handle gracefully - convert to abort state
        result = e.get_abort_response()
"""

import json
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


# ============================================================
# CONTROLLED FAILURE EXCEPTION
# ============================================================

@dataclass
class ControlledLLMFailure(Exception):
    """
    Raised when LLM response parsing fails in a controlled manner.
    
    This is NOT a system crash - it's an intentional, visible failure
    that can be converted to a structured agent result.
    
    Categories:
    - empty_response: LLM returned nothing
    - invalid_format: Response is not valid JSON
    - schema_violation: JSON is valid but missing required keys
    - truncated_output: Response was cut off mid-stream
    - provider_failure: Provider returned error message instead of JSON
    """
    reason: str
    category: str
    agent_name: Optional[str] = None
    provider_name: Optional[str] = None
    raw_response_preview: Optional[str] = None
    
    def __str__(self):
        parts = [f"LLM Parsing Failed: {self.reason}"]
        if self.category:
            parts.append(f"[{self.category}]")
        if self.agent_name:
            parts.append(f"(agent={self.agent_name})")
        if self.provider_name:
            parts.append(f"(provider={self.provider_name})")
        if self.raw_response_preview:
            parts.append(f"\nPreview: {self.raw_response_preview}")
        return " ".join(parts)
    
    def get_abort_response(self) -> Dict[str, Any]:
        """
        Convert failure to a structured agent result (abort state).
        
        This allows downstream agents to continue or terminate cleanly
        instead of crashing the entire pipeline.
        """
        return {
            "action": "abort",
            "reasoning": f"LLM response parsing failed: {self.reason} ({self.category})",
            "output": None,
            "parsing_failed": True,
            "failure_category": self.category,
            "provider_name": self.provider_name,
            "agent_name": self.agent_name
        }


# ============================================================
# SAFE JSON PARSER (MANDATORY FOR ALL LLM OUTPUTS)
# ============================================================

def safe_parse_llm_json(
    raw_response: str,
    agent_name: str = "Unknown",
    provider_name: str = "Unknown",
    expected_keys: Optional[List[str]] = None,
    auto_fix: bool = True
) -> Dict[str, Any]:
    """
    Parse LLM JSON response with comprehensive safety checks.
    
    THIS IS THE ONLY FUNCTION THAT SHOULD PARSE LLM JSON.
    Direct json.loads() calls on LLM outputs are FORBIDDEN.
    
    Safety guarantees:
    1. Empty response detection (before parsing)
    2. Non-JSON response handling (with preview)
    3. Structure validation (required keys)
    4. Auto-fixing common LLM mistakes (optional)
    5. Controlled failures (no crashes)
    
    Args:
        raw_response: Raw LLM output string
        agent_name: Name of agent requesting parse (for tracing)
        provider_name: LLM provider name (gemini/groq/qwen)
        expected_keys: Required keys in JSON (e.g., ["action", "reasoning"])
        auto_fix: Attempt to fix common JSON errors (trailing commas, etc.)
    
    Returns:
        Parsed JSON dict with validated structure
    
    Raises:
        ControlledLLMFailure: When parsing fails (NOT a crash - intentional)
    
    Examples:
        >>> result = safe_parse_llm_json(
        ...     raw_response='{"action": "query", "reasoning": "..."}',
        ...     agent_name="SQLGenerator",
        ...     provider_name="gemini",
        ...     expected_keys=["action", "reasoning", "output"]
        ... )
    """
    # ===== STEP 1: EMPTY RESPONSE CHECK (CRITICAL) =====
    if raw_response is None:
        raise ControlledLLMFailure(
            reason="LLM returned None",
            category="empty_response",
            agent_name=agent_name,
            provider_name=provider_name
        )
    
    if not isinstance(raw_response, str):
        raise ControlledLLMFailure(
            reason=f"LLM response is not a string (type={type(raw_response).__name__})",
            category="invalid_format",
            agent_name=agent_name,
            provider_name=provider_name,
            raw_response_preview=str(raw_response)[:200]
        )
    
    if not raw_response.strip():
        raise ControlledLLMFailure(
            reason="LLM returned empty or whitespace-only response",
            category="empty_response",
            agent_name=agent_name,
            provider_name=provider_name,
            raw_response_preview=f"'{raw_response}'"
        )
    
    # ===== STEP 2: EXTRACT JSON FROM RESPONSE =====
    # Some LLMs wrap JSON in markdown code blocks or add preamble
    content = raw_response.strip()
    original_content = content
    
    # Remove markdown code blocks if present
    if content.startswith("```"):
        # Extract content between ```json and ```
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if match:
            content = match.group(1).strip()
        else:
            # Malformed markdown - try to extract anyway
            content = content.replace("```json", "").replace("```", "").strip()
    
    # Extract JSON object if embedded in text
    if "{" in content and "}" in content:
        # Find first { and last }
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1
        content = content[start_idx:end_idx].strip()
    
    # Final empty check after extraction
    if not content:
        raise ControlledLLMFailure(
            reason="No JSON object found in response after extraction",
            category="invalid_format",
            agent_name=agent_name,
            provider_name=provider_name,
            raw_response_preview=original_content[:500]
        )
    
    # ===== STEP 3: ATTEMPT JSON PARSING WITH AUTO-FIX =====
    parsed_json = None
    parse_error = None
    
    try:
        parsed_json = json.loads(content)
    except json.JSONDecodeError as e:
        parse_error = e
        
        if auto_fix:
            # Try to fix common LLM JSON mistakes
            fixed_content = _auto_fix_json(content)
            
            if fixed_content != content:
                try:
                    parsed_json = json.loads(fixed_content)
                    parse_error = None  # Fixed successfully!
                except json.JSONDecodeError:
                    pass  # Auto-fix didn't work
    
    # If parsing still failed, raise controlled error
    if parsed_json is None:
        # Detect specific failure patterns
        category = _detect_failure_category(content, parse_error)
        
        # Create helpful error preview
        error_context = ""
        if parse_error:
            pos = getattr(parse_error, 'pos', 0)
            error_context = f" at position {pos}: {parse_error.msg}"
            if pos > 0:
                # Show context around error
                preview_start = max(0, pos - 50)
                preview_end = min(len(content), pos + 50)
                error_context += f"\nContext: '...{content[preview_start:preview_end]}...'"
        
        raise ControlledLLMFailure(
            reason=f"Invalid JSON{error_context}",
            category=category,
            agent_name=agent_name,
            provider_name=provider_name,
            raw_response_preview=content[:500]
        )
    
    # ===== STEP 4: STRUCTURE VALIDATION =====
    if expected_keys:
        missing_keys = [key for key in expected_keys if key not in parsed_json]
        
        if missing_keys:
            raise ControlledLLMFailure(
                reason=f"Missing required keys: {missing_keys}",
                category="schema_violation",
                agent_name=agent_name,
                provider_name=provider_name,
                raw_response_preview=json.dumps(parsed_json, indent=2)[:500]
            )
    
    # ===== SUCCESS =====
    return parsed_json


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _auto_fix_json(content: str) -> str:
    """
    Attempt to fix common LLM JSON formatting mistakes.
    
    Common issues:
    - Trailing commas: {"key": "value",}
    - Single quotes: {'key': 'value'}
    - Comments: {"key": "value"} // comment
    - Unescaped newlines in strings
    """
    fixed = content
    
    # Fix 1: Remove trailing commas before ] or }
    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
    
    # Fix 2: Replace single quotes with double quotes
    # (only if no double quotes present - avoid breaking escaped quotes)
    if "'" in fixed and '"' not in fixed:
        fixed = fixed.replace("'", '"')
    
    # Fix 3: Remove // comments
    fixed = re.sub(r'//.*?$', '', fixed, flags=re.MULTILINE)
    
    # Fix 4: Remove /* */ comments
    fixed = re.sub(r'/\*.*?\*/', '', fixed, flags=re.DOTALL)
    
    return fixed.strip()


def _detect_failure_category(content: str, parse_error: Optional[json.JSONDecodeError]) -> str:
    """
    Detect the category of JSON parsing failure.
    
    Categories:
    - truncated_output: Response appears cut off
    - provider_failure: Looks like error message from provider
    - invalid_format: General JSON syntax error
    """
    content_lower = content.lower()
    
    # Detect truncated output
    if parse_error and hasattr(parse_error, 'pos'):
        # If error is near the end of content, likely truncated
        if parse_error.pos > len(content) * 0.9:
            return "truncated_output"
    
    # Detect provider error messages
    provider_error_patterns = [
        "rate limit",
        "quota exceeded",
        "api error",
        "authentication failed",
        "invalid api key",
        "service unavailable",
        "request failed"
    ]
    
    if any(pattern in content_lower for pattern in provider_error_patterns):
        return "provider_failure"
    
    # Default to invalid format
    return "invalid_format"


# ============================================================
# VALIDATION HELPERS
# ============================================================

def validate_agent_response(
    parsed_json: Dict[str, Any],
    agent_name: str = "Unknown"
) -> Dict[str, Any]:
    """
    Validate that parsed JSON has standard agent response structure.
    
    Standard structure:
    - action: str (required)
    - reasoning: str (optional but recommended)
    - output: Any (optional)
    
    Args:
        parsed_json: Already parsed JSON dict
        agent_name: Agent name for error messages
    
    Returns:
        Validated JSON (may add defaults for optional fields)
    
    Raises:
        ControlledLLMFailure: If critical fields missing
    """
    if "action" not in parsed_json:
        raise ControlledLLMFailure(
            reason="Missing required field 'action' in agent response",
            category="schema_violation",
            agent_name=agent_name,
            raw_response_preview=json.dumps(parsed_json, indent=2)[:500]
        )
    
    # Add defaults for optional fields
    if "reasoning" not in parsed_json:
        parsed_json["reasoning"] = f"No reasoning provided by {agent_name}"
    
    if "output" not in parsed_json:
        parsed_json["output"] = None
    
    return parsed_json
