
import asyncio
from unittest.mock import MagicMock, AsyncMock
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.orchestrator.batch_optimized_orchestrator import BatchOptimizedOrchestrator, BatchPipelineState
from backend.orchestrator.llm_client import LLMResponse, LLMProvider

async def verify_json_mode():
    print("🧪 Verifying JSON Mode Implementation...")
    
    # 1. Mock the LLM Client
    mock_llm = MagicMock()
    mock_llm.generate.return_value = LLMResponse(
        content='{"test": "success"}',
        provider=LLMProvider.GEMINI,
        model="mock-model"
    )
    
    # 2. Initialize Orchestrator with mock LLM
    orchestrator = BatchOptimizedOrchestrator(verbose=True)
    orchestrator.llm = mock_llm  # Inject mock
    
    # 3. Create dummy state
    state = BatchPipelineState(user_query="test query")
    
    # 4. Call call_llm_batch
    print("→ Calling call_llm_batch...")
    try:
        await orchestrator.call_llm_batch(
            batch_name="TEST_BATCH",
            roles=["TestAgent"],
            prompt="Test Prompt",
            state=state
        )
    except Exception as e:
        print(f"⚠️ Error during call: {e}")
        # We don't care about the result, only the call arguments
        pass
        
    # 5. Verify Mock Call Arguments
    call_args = mock_llm.generate.call_args
    if not call_args:
        print("❌ FAILED: LLM generate was not called!")
        return
        
    args, kwargs = call_args
    response_format = kwargs.get("response_format")
    
    print(f"\n🔍 Call Arguments:\n   args: {args}\n   kwargs: {kwargs}")
    
    if response_format == {"type": "json_object"}:
        print("\n✅ SUCCESS: response_format={'type': 'json_object'} was passed correctly!")
    else:
        print(f"\n❌ FAILED: response_format mismatch. Expected {{'type': 'json_object'}}, got {response_format}")

if __name__ == "__main__":
    asyncio.run(verify_json_mode())
