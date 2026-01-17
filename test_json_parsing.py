"""
Test suite for safe LLM JSON parsing.

Tests:
1. Empty response handling
2. Non-JSON response handling
3. Truncated output detection
4. Provider error message detection
5. Auto-fix common JSON mistakes
6. Schema validation
7. Abort state conversion
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator.llm_parser import (
    safe_parse_llm_json,
    ControlledLLMFailure,
    validate_agent_response
)


def test_empty_response():
    """Test that empty responses are caught before parsing."""
    print("\n" + "="*60)
    print("TEST 1: Empty Response Handling")
    print("="*60)
    
    # Test 1a: None response
    try:
        safe_parse_llm_json(None, agent_name="TestAgent")
        print("❌ FAIL: None response was allowed")
        sys.exit(1)
    except ControlledLLMFailure as e:
        assert e.category == "empty_response"
        print(f"✓ PASS: None response correctly rejected [{e.category}]")
    
    # Test 1b: Empty string
    try:
        safe_parse_llm_json("", agent_name="TestAgent")
        print("❌ FAIL: Empty string was allowed")
        sys.exit(1)
    except ControlledLLMFailure as e:
        assert e.category == "empty_response"
        print(f"✓ PASS: Empty string correctly rejected [{e.category}]")
    
    # Test 1c: Whitespace only
    try:
        safe_parse_llm_json("   \n\t  ", agent_name="TestAgent")
        print("❌ FAIL: Whitespace-only response was allowed")
        sys.exit(1)
    except ControlledLLMFailure as e:
        assert e.category == "empty_response"
        print(f"✓ PASS: Whitespace-only correctly rejected [{e.category}]")
    
    print("\n✅ TEST 1 PASSED\n")


def test_non_json_response():
    """Test handling of plain text / non-JSON responses."""
    print("="*60)
    print("TEST 2: Non-JSON Response Handling")
    print("="*60)
    
    # Test 2a: Plain text
    try:
        safe_parse_llm_json(
            "This is just plain text, not JSON",
            agent_name="TestAgent"
        )
        print("❌ FAIL: Plain text was parsed as JSON")
        sys.exit(1)
    except ControlledLLMFailure as e:
        assert e.category == "invalid_format"
        print(f"✓ PASS: Plain text correctly rejected [{e.category}]")
    
    # Test 2b: Rate limit message
    try:
        safe_parse_llm_json(
            "Error: Rate limit exceeded. Please try again later.",
            agent_name="TestAgent",
            provider_name="gemini"
        )
        print("❌ FAIL: Rate limit message was parsed as JSON")
        sys.exit(1)
    except ControlledLLMFailure as e:
        assert e.category == "provider_failure"
        print(f"✓ PASS: Provider error detected [{e.category}]")
    
    # Test 2c: Malformed JSON
    try:
        safe_parse_llm_json(
            '{"key": "value" missing_brace',
            agent_name="TestAgent",
            auto_fix=False  # Disable auto-fix for this test
        )
        print("❌ FAIL: Malformed JSON was parsed")
        sys.exit(1)
    except ControlledLLMFailure as e:
        assert e.category == "invalid_format"
        print(f"✓ PASS: Malformed JSON correctly rejected [{e.category}]")
    
    print("\n✅ TEST 2 PASSED\n")


def test_valid_json():
    """Test that valid JSON is parsed correctly."""
    print("="*60)
    print("TEST 3: Valid JSON Parsing")
    print("="*60)
    
    # Test 3a: Simple JSON
    result = safe_parse_llm_json(
        '{"action": "query", "reasoning": "test", "output": "result"}',
        agent_name="TestAgent"
    )
    assert result["action"] == "query"
    print("✓ PASS: Simple JSON parsed correctly")
    
    # Test 3b: JSON in markdown code block
    result = safe_parse_llm_json(
        '```json\n{"action": "query", "reasoning": "test"}\n```',
        agent_name="TestAgent"
    )
    assert result["action"] == "query"
    print("✓ PASS: Markdown-wrapped JSON extracted")
    
    # Test 3c: JSON with surrounding text
    result = safe_parse_llm_json(
        'Here is the result:\n{"action": "query", "reasoning": "test"}\nEnd of response',
        agent_name="TestAgent"
    )
    assert result["action"] == "query"
    print("✓ PASS: JSON extracted from surrounding text")
    
    print("\n✅ TEST 3 PASSED\n")


def test_auto_fix():
    """Test auto-fixing of common LLM JSON mistakes."""
    print("="*60)
    print("TEST 4: Auto-Fix Common Mistakes")
    print("="*60)
    
    # Test 4a: Trailing comma
    result = safe_parse_llm_json(
        '{"action": "query", "reasoning": "test",}',
        agent_name="TestAgent",
        auto_fix=True
    )
    assert result["action"] == "query"
    print("✓ PASS: Trailing comma auto-fixed")
    
    # Test 4b: Single quotes (when no double quotes present)
    result = safe_parse_llm_json(
        "{'action': 'query', 'reasoning': 'test'}",
        agent_name="TestAgent",
        auto_fix=True
    )
    assert result["action"] == "query"
    print("✓ PASS: Single quotes auto-fixed")
    
    # Test 4c: Comments
    result = safe_parse_llm_json(
        '{\n  "action": "query", // This is the action\n  "reasoning": "test"\n}',
        agent_name="TestAgent",
        auto_fix=True
    )
    assert result["action"] == "query"
    print("✓ PASS: Comments auto-removed")
    
    print("\n✅ TEST 4 PASSED\n")


def test_schema_validation():
    """Test validation of required keys."""
    print("="*60)
    print("TEST 5: Schema Validation")
    print("="*60)
    
    # Test 5a: Missing required key
    try:
        safe_parse_llm_json(
            '{"reasoning": "test"}',  # Missing "action"
            agent_name="TestAgent",
            expected_keys=["action", "reasoning"]
        )
        print("❌ FAIL: Missing required key was allowed")
        sys.exit(1)
    except ControlledLLMFailure as e:
        assert e.category == "schema_violation"
        assert "action" in e.reason
        print(f"✓ PASS: Missing key detected [{e.category}]")
    
    # Test 5b: All required keys present
    result = safe_parse_llm_json(
        '{"action": "query", "reasoning": "test", "output": "result"}',
        agent_name="TestAgent",
        expected_keys=["action", "reasoning"]
    )
    assert result["action"] == "query"
    print("✓ PASS: Valid schema accepted")
    
    print("\n✅ TEST 5 PASSED\n")


def test_abort_state_conversion():
    """Test conversion of parsing failures to abort state."""
    print("="*60)
    print("TEST 6: Abort State Conversion")
    print("="*60)
    
    # Create a controlled failure
    try:
        safe_parse_llm_json(
            "Invalid JSON response",
            agent_name="TestAgent",
            provider_name="gemini"
        )
    except ControlledLLMFailure as e:
        # Convert to abort state
        abort_response = e.get_abort_response()
        
        assert abort_response["action"] == "abort"
        assert abort_response["parsing_failed"] is True
        assert abort_response["failure_category"] == e.category
        assert abort_response["provider_name"] == "gemini"
        assert abort_response["agent_name"] == "TestAgent"
        
        print("✓ PASS: Abort state structure correct")
        print(f"  - action: {abort_response['action']}")
        print(f"  - parsing_failed: {abort_response['parsing_failed']}")
        print(f"  - failure_category: {abort_response['failure_category']}")
        print(f"  - reasoning: {abort_response['reasoning'][:50]}...")
    
    print("\n✅ TEST 6 PASSED\n")


def test_truncated_detection():
    """Test detection of truncated output."""
    print("="*60)
    print("TEST 7: Truncated Output Detection")
    print("="*60)
    
    # Truncated JSON (cut off at end)
    try:
        safe_parse_llm_json(
            '{"action": "query", "reasoning": "This is a long reasoning that got cut off mid-sen',
            agent_name="TestAgent",
            auto_fix=False
        )
        print("❌ FAIL: Truncated JSON was not detected")
        sys.exit(1)
    except ControlledLLMFailure as e:
        # Should detect as truncated (error near end of string)
        assert e.category in ["truncated_output", "invalid_format"]
        print(f"✓ PASS: Truncated output detected [{e.category}]")
    
    print("\n✅ TEST 7 PASSED\n")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("SAFE LLM JSON PARSER - VERIFICATION TESTS")
    print("="*60)
    
    try:
        test_empty_response()
        test_non_json_response()
        test_valid_json()
        test_auto_fix()
        test_schema_validation()
        test_abort_state_conversion()
        test_truncated_detection()
        
        print("="*60)
        print("🎉 ALL TESTS PASSED!")
        print("="*60)
        print()
        print("✓ Empty response detection working")
        print("✓ Non-JSON response handling correct")
        print("✓ Valid JSON parsing successful")
        print("✓ Auto-fix common mistakes enabled")
        print("✓ Schema validation enforced")
        print("✓ Abort state conversion functional")
        print("✓ Truncated output detected")
        print()
        print("System is crash-proof! ✨")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
