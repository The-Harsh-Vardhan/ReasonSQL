"""
Integration test: Verify ambiguous queries no longer crash the system.

This simulates the exact scenario that was causing crashes:
1. User asks an ambiguous question
2. LLM returns JSON + explanatory text
3. System should extract JSON cleanly without crashing
"""
import sys
import json


def simulate_llm_response_with_extra_text():
    """
    Simulate what LLMs actually return for ambiguous queries.
    This is the EXACT pattern that was causing crashes.
    """
    return '''Sure! Let me analyze your query.

The term "recent" is ambiguous and needs clarification before I can generate SQL.

{
  "intent": "ambiguous",
  "reason": "The term 'recent' is vague - it could mean last 7 days, 30 days, or a custom range",
  "clarification_question": "How recent? Last 7 days, 30 days, or a custom date range?",
  "detected_ambiguous_terms": ["recent"],
  "suggested_interpretations": [
    "Last 7 days",
    "Last 30 days",
    "Last 90 days"
  ]
}

I'll wait for your clarification to proceed with SQL generation.
'''


def test_with_safe_parser():
    """Test using the new safe JSON parser."""
    print("\n" + "="*60)
    print("INTEGRATION TEST: Ambiguous Query Handling")
    print("="*60)
    
    from orchestrator.json_utils import safe_parse_llm_json, JSONExtractionError
    
    llm_response = simulate_llm_response_with_extra_text()
    
    print("\n📥 Simulated LLM Response:")
    print("-" * 60)
    print(llm_response[:200] + "...")
    print("-" * 60)
    
    try:
        # This should work now
        result, stripped = safe_parse_llm_json(llm_response)
        
        print("\n✅ SUCCESS: JSON extracted without crash!")
        print("\n📊 Extracted Data:")
        print(json.dumps(result, indent=2))
        
        print(f"\n🗑️  Stripped Text: {len(stripped)} characters")
        print(f"   Preview: {stripped[:100]}...")
        
        # Verify expected fields
        assert result["intent"] == "ambiguous", "Intent should be 'ambiguous'"
        assert "clarification_question" in result, "Should have clarification question"
        assert len(result["detected_ambiguous_terms"]) > 0, "Should detect ambiguous terms"
        
        print("\n✅ All assertions passed!")
        print("\n🎉 The system can now handle ambiguous queries without crashing!")
        return True
        
    except JSONExtractionError as e:
        print(f"\n❌ FAILED: {e}")
        return False
    except AssertionError as e:
        print(f"\n❌ FAILED: Assertion error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ FAILED: Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_with_old_parser():
    """Demonstrate what the old parser would do (for comparison)."""
    print("\n" + "="*60)
    print("COMPARISON: What Would Have Happened Before")
    print("="*60)
    
    llm_response = simulate_llm_response_with_extra_text()
    
    try:
        # This is what the old code was doing
        result = json.loads(llm_response)
        print("✅ Old parser succeeded (shouldn't happen)")
        return True
    except json.JSONDecodeError as e:
        print(f"\n❌ Old parser FAILED (as expected):")
        print(f"   Error: {e}")
        print(f"   This is the crash that users were experiencing!")
        return False


def main():
    """Run integration tests."""
    print("\n" + "="*70)
    print("JSON PARSING FIX - INTEGRATION TEST")
    print("Scenario: User asks 'Show me recent orders'")
    print("="*70)
    
    # Show what would have happened before
    old_result = test_with_old_parser()
    
    # Show what happens now
    new_result = test_with_safe_parser()
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Old parser (without fix): {'✅ PASS' if old_result else '❌ CRASH (expected)'}")
    print(f"New parser (with fix):    {'✅ PASS' if new_result else '❌ FAIL (unexpected!)'}")
    
    if not old_result and new_result:
        print("\n🎉 FIX VERIFIED:")
        print("   - Old approach: Crashes on ambiguous queries ❌")
        print("   - New approach: Handles them gracefully ✅")
        print("   - System is now production-ready! 🚀")
        return 0
    else:
        print("\n⚠️  WARNING: Unexpected results. Review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
