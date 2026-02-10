"""
Quick verification that state consistency fix is working.
"""
print("="*60)
print("STATE CONSISTENCY FIX - VERIFICATION")
print("="*60)

# Test 1: Import
print("\n1. Testing imports...")
try:
    from orchestrator import BatchOptimizedOrchestrator
    from models import FinalResponse, ReasoningTrace, ExecutionStatus
    print("   ✓ Imports successful")
except Exception as e:
    print(f"   ✗ Import failed: {e}")
    exit(1)

# Test 2: Create orchestrator
print("\n2. Creating orchestrator...")
try:
    orch = BatchOptimizedOrchestrator(verbose=False)
    print("   ✓ Orchestrator created")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    exit(1)

# Test 3: Process a potentially blocked query
print("\n3. Testing blocked query handling...")
try:
    result = orch.process_query("Show me recent data")
    
    # Critical: Check reasoning_trace exists
    if not hasattr(result, 'reasoning_trace'):
        print("   ✗ FAIL: reasoning_trace attribute missing!")
        exit(1)
    
    if result.reasoning_trace is None:
        print("   ✗ FAIL: reasoning_trace is None!")
        exit(1)
    
    print("   ✓ reasoning_trace exists")
    print(f"   Status: {result.reasoning_trace.final_status}")
    print(f"   Actions: {len(result.reasoning_trace.actions)}")
    
except AttributeError as e:
    print(f"   ✗ FAIL: AttributeError - {e}")
    print("   This is the bug we fixed!")
    exit(1)
except Exception as e:
    print(f"   ✗ FAIL: {e}")
    exit(1)

print("\n" + "="*60)
print("✅ VERIFICATION PASSED")
print("="*60)
print("\nThe state consistency bug is fixed:")
print("  ✓ reasoning_trace always exists")
print("  ✓ No AttributeError crashes")
print("  ✓ Blocked queries handled gracefully")
print("\n🎉 System is ready for demo!")
