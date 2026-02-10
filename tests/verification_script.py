import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from backend.orchestrator import ReasonSQLOrchestrator
from backend.models import ExecutionStatus

async def run_tests():
    print("🚀 Starting ReasonSQL System Verification...")
    orchestrator = ReasonSQLOrchestrator(verbose=False)
    
    # TEST 1: Safety Validation
    print("\n[1/3] Testing Safety Validator (DROP TABLE)...")
    try:
        response = orchestrator.run_query("DROP TABLE customers")
        if response.reasoning_trace.final_status == ExecutionStatus.BLOCKED:
            print("✅ PASS: Dangerous query successfully BLOCKED.")
        else:
            print(f"❌ FAIL: Query was not blocked. Status: {response.reasoning_trace.final_status}")
    except Exception as e:
        print(f"❌ FAIL: Exception occurred: {e}")

    # TEST 2: Meta Query
    print("\n[2/3] Testing Meta Query (Schema Introspection)...")
    try:
        response = orchestrator.run_query("What tables are in the database?")
        if response.is_meta_query:
            print("✅ PASS: Correctly identified as META_QUERY.")
        else:
            print("❌ FAIL: Failed to identify as META_QUERY.")
    except Exception as e:
        print(f"❌ FAIL: Exception occurred: {e}")

    # TEST 3: Simple Data Query
    print("\n[3/3] Testing Data Query (SELECT)...")
    try:
        response = orchestrator.run_query("How many customers are there?")
        if response.reasoning_trace.final_status == ExecutionStatus.SUCCESS:
            print(f"✅ PASS: Query successful. Answer: {response.answer}")
        else:
            print(f"❌ FAIL: Query failed. Status: {response.reasoning_trace.final_status}")
    except Exception as e:
        print(f"❌ FAIL: Exception occurred: {e}")

if __name__ == "__main__":
    asyncio.run(run_tests())
