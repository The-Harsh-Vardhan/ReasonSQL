"""
Robust JSON extraction and parsing utilities for LLM responses.

PROBLEM
-------
LLMs often return valid JSON embedded in explanatory text:
    "Here's the analysis: {"intent": "data_query"} Hope this helps!"

This causes json.loads() to fail with "Extra data" errors.

SOLUTION
--------
Always extract ONLY the first JSON object before parsing.
"""
import json
import re
from typing import Dict, Any, Optional, Tuple


class JSONExtractionError(Exception):
    """Raised when no valid JSON object can be extracted."""
    pass


def extract_first_json_block(text: str) -> Tuple[str, Optional[str]]:
    """
    Extract the first valid JSON object from LLM response text.
    
    Algorithm:
    ----------
    1. Find the first '{' character
    2. Track brace depth to find the matching '}'
    3. Handle nested objects properly
    4. Return extracted JSON and any stripped text
    
    Args:
        text: Raw LLM response (may contain JSON + commentary)
    
    Returns:
        Tuple of (json_string, stripped_text):
        - json_string: Extracted JSON object as string
        - stripped_text: Any text that was before/after JSON (None if none)
    
    Raises:
        JSONExtractionError: If no valid JSON object is found
    
    Examples:
        >>> extract_first_json_block('{"key": "value"}')
        ('{"key": "value"}', None)
        
        >>> extract_first_json_block('Analysis: {"a": 1} Done!')
        ('{"a": 1}', 'Analysis:  Done!')
        
        >>> extract_first_json_block('{"outer": {"inner": 1}}')
        ('{"outer": {"inner": 1}}', None)
    """
    if not text or not isinstance(text, str):
        raise JSONExtractionError("Input text is empty or not a string")
    
    # Remove common markdown wrappers first
    text = text.strip()
    
    # Handle markdown code blocks
    if "```json" in text:
        # Extract from ```json ... ```
        match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if match:
            json_candidate = match.group(1).strip()
            # Check if there's text outside the code block
            before = text[:match.start()].strip()
            after = text[match.end():].strip()
            stripped = (before + " " + after).strip() if (before or after) else None
            return json_candidate, stripped
    elif "```" in text:
        # Generic code block
        match = re.search(r'```\s*([\s\S]*?)\s*```', text)
        if match:
            json_candidate = match.group(1).strip()
            before = text[:match.start()].strip()
            after = text[match.end():].strip()
            stripped = (before + " " + after).strip() if (before or after) else None
            return json_candidate, stripped
    
    # Find first opening brace
    start_idx = text.find('{')
    if start_idx == -1:
        raise JSONExtractionError("No JSON object found (no opening brace)")
    
    # Track brace depth to find matching closing brace
    depth = 0
    in_string = False
    escape_next = False
    end_idx = None
    
    for i in range(start_idx, len(text)):
        char = text[i]
        
        # Handle string escaping
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        # Track string boundaries (braces inside strings don't count)
        if char == '"':
            in_string = not in_string
            continue
        
        # Only count braces outside of strings
        if not in_string:
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    # Found matching closing brace
                    end_idx = i + 1
                    break
    
    if end_idx is None:
        raise JSONExtractionError("No matching closing brace found (unbalanced braces)")
    
    # Extract JSON string
    json_str = text[start_idx:end_idx].strip()
    
    # Calculate stripped text
    before = text[:start_idx].strip()
    after = text[end_idx:].strip()
    stripped = (before + " " + after).strip() if (before or after) else None
    
    return json_str, stripped


def safe_parse_llm_json(text: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Safely parse JSON from LLM response with robust error handling.
    
    This is the REQUIRED pipeline for all LLM response parsing:
    1. Extract first JSON object
    2. Parse it
    3. Return result + metadata about stripped text
    
    Args:
        text: Raw LLM response
    
    Returns:
        Tuple of (parsed_dict, stripped_text):
        - parsed_dict: Parsed JSON as dictionary
        - stripped_text: Any extra text that was removed (None if none)
    
    Raises:
        JSONExtractionError: If extraction fails
        json.JSONDecodeError: If parsing fails (should be rare after extraction)
    
    Example:
        >>> result, stripped = safe_parse_llm_json('Here: {"status": "ok"}')
        >>> result
        {'status': 'ok'}
        >>> stripped
        'Here:'
    """
    # Step 1: Extract JSON block
    json_str, stripped_text = extract_first_json_block(text)
    
    # Step 2: Parse JSON
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise JSONExtractionError(
            f"Extracted text is not valid JSON: {e}\n"
            f"Extracted: {json_str[:200]}"
        )
    
    # Step 3: Validate result is a dict (not array, string, etc.)
    if not isinstance(parsed, dict):
        raise JSONExtractionError(
            f"Expected JSON object (dict), got {type(parsed).__name__}: {parsed}"
        )
    
    return parsed, stripped_text


def parse_llm_response_with_trace(
    text: str, 
    agent_name: str,
    trace: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Parse LLM response and record metadata in reasoning trace.
    
    This should be used by orchestrators to:
    1. Parse LLM responses safely
    2. Record when extra text is stripped
    3. Make debugging transparent
    
    Args:
        text: Raw LLM response
        agent_name: Name of agent that produced response (for logging)
        trace: Optional reasoning trace dict to update
    
    Returns:
        Parsed JSON dictionary
    
    Raises:
        JSONExtractionError: If extraction/parsing fails
    
    Side Effects:
        If trace is provided and text was stripped, adds:
        - stripped_text_detected: True
        - stripped_text_length: <n>
        - stripped_text_preview: <first 100 chars>
    """
    parsed, stripped = safe_parse_llm_json(text)
    
    # Record stripping metadata if trace is provided
    if trace is not None and stripped:
        trace[f"{agent_name}_stripped_text_detected"] = True
        trace[f"{agent_name}_stripped_text_length"] = len(stripped)
        trace[f"{agent_name}_stripped_text_preview"] = stripped[:100]
    
    return parsed


# ============================================================
# LEGACY FALLBACK (for gradual migration)
# ============================================================

def parse_json_safe(text: str) -> Dict[str, Any]:
    """
    Legacy wrapper for backward compatibility.
    
    Use safe_parse_llm_json() for new code.
    """
    parsed, _ = safe_parse_llm_json(text)
    return parsed
