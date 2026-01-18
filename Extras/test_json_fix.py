"""
Test script to verify JSON extraction fix for ambiguous queries.

This tests that the system can handle LLM responses that include
JSON + extra explanatory text without crashing.
"""
import sys
from orchestrator.json_utils import extract_first_json_block, safe_parse_llm_json, JSONExtractionError


def test_basic_extraction():
    """Test basic JSON extraction."""
    print("\n" + "="*60)
    print("TEST 1: Basic JSON Extraction")
    print("="*60)
    
    test_cases = [
        # Clean JSON
        ('{"status": "ok"}', True),
        
        # JSON with extra text before
        ('Here is the result: {"status": "ok"}', True),
        
        # JSON with extra text after
        ('{"status": "ok"} This is the analysis.', True),
        
        # JSON with text before and after
        ('Analysis: {"status": "ok"} Done!', True),
        
        # Nested JSON
        ('{"outer": {"inner": "value"}}', True),
        
        # Markdown code block
        ('```json\n{"status": "ok"}\n```', True),
        
        # JSON with newlines
        ('{\n  "status": "ok",\n  "reason": "test"\n}', True),
        
        # Ambiguous query response (the actual bug case)
        ('''Sure! Here's the classification:
        
        {"intent": "ambiguous", "clarification": "What do you mean by recent?"}
        
        Let me know if you need anything else!''', True),
        
        # Invalid: no JSON
        ('This is just text', False),
        
        # Invalid: empty
        ('', False),
    ]
    
    passed = 0
    failed = 0
    
    for i, (text, should_succeed) in enumerate(test_cases, 1):
        try:
            json_str, stripped = extract_first_json_block(text)
            if should_succeed:
                print(f"✓ Test {i}: PASS - Extracted: {json_str[:50]}...")
                if stripped:
                    print(f"  Stripped: {len(stripped)} chars")
                passed += 1
            else:
                print(f"✗ Test {i}: FAIL - Should have raised error")
                failed += 1
        except JSONExtractionError as e:
            if not should_succeed:
                print(f"✓ Test {i}: PASS - Correctly failed: {e}")
                passed += 1
            else:
                print(f"✗ Test {i}: FAIL - Unexpected error: {e}")
                failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_safe_parsing():
    """Test complete safe parsing pipeline."""
    print("\n" + "="*60)
    print("TEST 2: Safe Parsing Pipeline")
    print("="*60)
    
    test_cases = [
        # Valid JSON with extra text
        ('Result: {"status": "ok", "action": "clarify"}', 
         {"status": "ok", "action": "clarify"}),
        
        # Ambiguous query scenario
        ('''Here's my analysis of your query:

        {
          "intent": "ambiguous",
          "reason": "The term 'recent' is vague",
          "clarification_question": "Do you mean last 7 days or 30 days?"
        }

        Hope this helps!''',
         {"intent": "ambiguous", 
          "reason": "The term 'recent' is vague",
          "clarification_question": "Do you mean last 7 days or 30 days?"}),
    ]
    
    passed = 0
    failed = 0
    
    for i, (text, expected) in enumerate(test_cases, 1):
        try:
            result, stripped = safe_parse_llm_json(text)
            if result == expected:
                print(f"✓ Test {i}: PASS - Parsed correctly")
                if stripped:
                    print(f"  Stripped {len(stripped)} chars")
                passed += 1
            else:
                print(f"✗ Test {i}: FAIL - Wrong result")
                print(f"  Expected: {expected}")
                print(f"  Got: {result}")
                failed += 1
        except Exception as e:
            print(f"✗ Test {i}: FAIL - Error: {e}")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n" + "="*60)
    print("TEST 3: Edge Cases")
    print("="*60)
    
    test_cases = [
        # Multiple JSON objects (should extract first)
        ('{"first": 1} {"second": 2}', {"first": 1}),
        
        # JSON in string
        ('The JSON is: {"key": "value with \\"quotes\\""}\n', 
         {"key": 'value with "quotes"'}),
        
        # Deeply nested
        ('{"a": {"b": {"c": {"d": 1}}}}', 
         {"a": {"b": {"c": {"d": 1}}}}),
    ]
    
    passed = 0
    failed = 0
    
    for i, (text, expected) in enumerate(test_cases, 1):
        try:
            result, stripped = safe_parse_llm_json(text)
            if result == expected:
                print(f"✓ Test {i}: PASS")
                passed += 1
            else:
                print(f"✗ Test {i}: FAIL")
                print(f"  Expected: {expected}")
                print(f"  Got: {result}")
                failed += 1
        except Exception as e:
            print(f"✗ Test {i}: FAIL - Error: {e}")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("JSON EXTRACTION FIX - TEST SUITE")
    print("="*60)
    
    results = []
    results.append(("Basic Extraction", test_basic_extraction()))
    results.append(("Safe Parsing", test_safe_parsing()))
    results.append(("Edge Cases", test_edge_cases()))
    
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All tests passed! JSON extraction fix is working.")
        return 0
    else:
        print("\n❌ Some tests failed. Review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
