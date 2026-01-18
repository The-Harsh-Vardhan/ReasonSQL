"""
Test to verify reasoning_trace always exists in FinalResponse.

This tests the fix for the state consistency bug where blocked/aborted
queries would crash with: 'BatchPipelineState' object has no attribute 'reasoning_trace'
"""
import sys


def test_blocked_query_has_reasoning_trace():
    """Test that blocked queries produce valid FinalResponse with reasoning_trace."""
    print("\n" + "="*60)
    print("TEST: Blocked Query State Consistency")
    print("="*60)
    
    try:
        from orchestrator import BatchOptimizedOrchestrator
        from models import ExecutionStatus
        
        print("\n1. Creating orchestrator...")
        orchestrator = BatchOptimizedOrchestrator(verbose=False)
        
        # Test 1: Ambiguous query (should be blocked)
        print("\n2. Testing ambiguous query (should trigger clarification)...")
        query = "Show me recent orders"
        
        try:
            result = orchestrator.process_query(query)
            
            # Verify FinalResponse structure
            print("\n✅ Query processed without crash!")
            print(f"   Status: {result.final_status if hasattr(result, 'final_status') else 'N/A'}")
            print(f"   Answer: {result.answer[:100]}...")
            
            # CRITICAL: Verify reasoning_trace exists
            if not hasattr(result, 'reasoning_trace'):
                print("\n❌ FAIL: FinalResponse missing reasoning_trace attribute!")
                return False
            
            if result.reasoning_trace is None:
                print("\n❌ FAIL: reasoning_trace is None!")
                return False
            
            print("\n✅ reasoning_trace exists")
            print(f"   Type: {type(result.reasoning_trace)}")
            print(f"   Actions: {len(result.reasoning_trace.actions)}")
            print(f"   Final Status: {result.reasoning_trace.final_status}")
            
            # Verify it has actions
            if len(result.reasoning_trace.actions) == 0:
                print("\n⚠️  WARNING: reasoning_trace has no actions (should have at least abort)")
            else:
                print(f"\n   First action: {result.reasoning_trace.actions[0].agent_name}")
                if len(result.reasoning_trace.actions) > 1:
                    print(f"   Last action: {result.reasoning_trace.actions[-1].agent_name}")
            
            return True
            
        except AttributeError as e:
            print(f"\n❌ FAIL: AttributeError - {e}")
            print("   This is the bug we're trying to fix!")
            return False
        except Exception as e:
            print(f"\n❌ FAIL: Unexpected error - {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except ImportError as e:
        print(f"\n❌ FAIL: Import error - {e}")
        return False


def test_safety_blocked_query():
    """Test that safety-blocked queries have reasoning_trace."""
    print("\n" + "="*60)
    print("TEST: Safety-Blocked Query")
    print("="*60)
    
    try:
        from orchestrator import BatchOptimizedOrchestrator
        
        print("\n1. Creating orchestrator...")
        orchestrator = BatchOptimizedOrchestrator(verbose=False)
        
        # This query might be blocked by safety validator (SELECT *)
        print("\n2. Testing potentially unsafe query...")
        query = "SELECT * FROM customers"
        
        try:
            result = orchestrator.process_query(query)
            
            print(f"\n✅ Query processed")
            print(f"   Answer: {result.answer[:100]}...")
            
            # Verify reasoning_trace
            if not hasattr(result, 'reasoning_trace') or result.reasoning_trace is None:
                print("\n❌ FAIL: reasoning_trace missing or None!")
                return False
            
            print("\n✅ reasoning_trace exists")
            print(f"   Actions: {len(result.reasoning_trace.actions)}")
            print(f"   Status: {result.reasoning_trace.final_status}")
            
            return True
            
        except AttributeError as e:
            print(f"\n❌ FAIL: AttributeError - {e}")
            return False
        except Exception as e:
            print(f"\n❌ FAIL: {e}")
            return False
            
    except ImportError as e:
        print(f"\n❌ FAIL: Import error - {e}")
        return False


def test_normal_query_still_works():
    """Verify normal queries still work correctly."""
    print("\n" + "="*60)
    print("TEST: Normal Query (Regression Test)")
    print("="*60)
    
    try:
        from orchestrator import BatchOptimizedOrchestrator
        
        print("\n1. Creating orchestrator...")
        orchestrator = BatchOptimizedOrchestrator(verbose=False)
        
        print("\n2. Testing normal query...")
        query = "How many customers are there?"
        
        try:
            result = orchestrator.process_query(query)
            
            print(f"\n✅ Query processed")
            print(f"   Answer: {result.answer[:100]}...")
            
            # Verify reasoning_trace
            if not hasattr(result, 'reasoning_trace') or result.reasoning_trace is None:
                print("\n❌ FAIL: reasoning_trace missing!")
                return False
            
            print("\n✅ reasoning_trace exists")
            print(f"   Actions: {len(result.reasoning_trace.actions)}")
            
            return True
            
        except Exception as e:
            print(f"\n❌ FAIL: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except ImportError as e:
        print(f"\n❌ FAIL: Import error - {e}")
        return False


def main():
    """Run all state consistency tests."""
    print("\n" + "="*70)
    print("STATE CONSISTENCY BUG FIX - TEST SUITE")
    print("Verifying reasoning_trace always exists in FinalResponse")
    print("="*70)
    
    results = []
    
    # Test 1: Blocked query
    results.append(("Blocked Query", test_blocked_query_has_reasoning_trace()))
    
    # Test 2: Safety-blocked query  
    results.append(("Safety Blocked", test_safety_blocked_query()))
    
    # Test 3: Normal query (regression)
    results.append(("Normal Query", test_normal_query_still_works()))
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All tests passed!")
        print("   reasoning_trace is always present in FinalResponse")
        print("   Blocked/aborted queries no longer crash")
        print("   UI can safely access reasoning_trace")
        return 0
    else:
        print("\n❌ Some tests failed - review output above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
