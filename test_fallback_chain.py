"""
Verification test for LLM fallback chain fixes.

Tests:
1. ENABLE_QWEN_FALLBACK defaults to False
2. GROQ_FALLBACK_MODEL is 8B only
3. GroqClient rejects 70B models at initialization
4. MultiProviderLLM respects ENABLE_QWEN_FALLBACK flag
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

def test_config_defaults():
    """Test that configuration defaults are safe."""
    print("\n" + "="*60)
    print("TEST 1: Configuration Defaults")
    print("="*60)
    
    import config
    
    # Test ENABLE_QWEN_FALLBACK
    assert config.ENABLE_QWEN_FALLBACK == False, "ENABLE_QWEN_FALLBACK should default to False"
    print("✓ PASS: ENABLE_QWEN_FALLBACK = False (default)")
    
    # Test GROQ_FALLBACK_MODEL
    assert config.GROQ_FALLBACK_MODEL == "llama-3.1-8b-instant", "GROQ_FALLBACK_MODEL should be 8B"
    print(f"✓ PASS: GROQ_FALLBACK_MODEL = {config.GROQ_FALLBACK_MODEL}")
    
    # Test GROQ_ALLOWED_MODELS
    assert all("8b" in model.lower() for model in config.GROQ_ALLOWED_MODELS), "All Groq models should be 8B"
    print(f"✓ PASS: All allowed Groq models are 8B: {config.GROQ_ALLOWED_MODELS}")
    
    print("\n✅ TEST 1 PASSED\n")


def test_groq_70b_rejection():
    """Test that GroqClient rejects 70B models."""
    print("="*60)
    print("TEST 2: Groq 70B Model Rejection")
    print("="*60)
    
    from orchestrator.llm_client import GroqClient
    from config import ConfigurationError
    
    # Test 1: Reject 70B versatile
    try:
        client = GroqClient(model="groq/llama-3.1-70b-versatile")
        print("❌ FAIL: 70B versatile model was allowed!")
        sys.exit(1)
    except ConfigurationError as e:
        print("✓ PASS: 70B versatile correctly rejected")
        print(f"   Reason: {str(e)[:80]}...")
    
    # Test 2: Reject 70B specdec
    try:
        client = GroqClient(model="groq/llama-3.3-70b-specdec")
        print("❌ FAIL: 70B specdec model was allowed!")
        sys.exit(1)
    except ConfigurationError as e:
        print("✓ PASS: 70B specdec correctly rejected")
    
    # Test 3: Accept 8B instant
    try:
        client = GroqClient(model="groq/llama-3.1-8b-instant", verbose=False)
        print("✓ PASS: 8B instant correctly accepted")
    except Exception as e:
        print(f"❌ FAIL: 8B instant rejected: {e}")
        sys.exit(1)
    
    print("\n✅ TEST 2 PASSED\n")


def test_qwen_feature_flag():
    """Test that Qwen respects ENABLE_QWEN_FALLBACK flag."""
    print("="*60)
    print("TEST 3: Qwen Feature Flag")
    print("="*60)
    
    from orchestrator.llm_client import MultiProviderLLM
    import config
    
    # Verify flag is False
    assert config.ENABLE_QWEN_FALLBACK == False, "ENABLE_QWEN_FALLBACK should be False"
    print(f"✓ Config: ENABLE_QWEN_FALLBACK = {config.ENABLE_QWEN_FALLBACK}")
    
    # Create client (should NOT initialize Qwen)
    client = MultiProviderLLM(primary="gemini", fallback="groq", verbose=False)
    
    assert client.tertiary_enabled == False, "Tertiary should not be enabled"
    print("✓ PASS: Tertiary (Qwen) not enabled")
    
    assert client.qwen is None, "Qwen client should be None"
    print("✓ PASS: Qwen client is None")
    
    assert client.tertiary is None, "Tertiary provider should be None"
    print("✓ PASS: Tertiary provider is None")
    
    # Check stats
    stats = client.get_stats()
    assert stats['tertiary_enabled'] == False
    print("✓ PASS: Stats show tertiary_enabled = False")
    
    fallback_chain = stats['fallback_chain']
    assert "[Graceful Abort]" in fallback_chain
    print(f"✓ PASS: Fallback chain shows graceful abort: {fallback_chain}")
    
    print("\n✅ TEST 3 PASSED\n")


def test_provider_configuration():
    """Test provider configuration constants."""
    print("="*60)
    print("TEST 4: Provider Configuration")
    print("="*60)
    
    import config
    
    # Test PRIMARY_PROVIDER
    assert config.PRIMARY_PROVIDER == "gemini", "Primary should be Gemini"
    print(f"✓ PRIMARY_PROVIDER = {config.PRIMARY_PROVIDER}")
    
    # Test SECONDARY_PROVIDER
    assert config.SECONDARY_PROVIDER == "groq", "Secondary should be Groq"
    print(f"✓ SECONDARY_PROVIDER = {config.SECONDARY_PROVIDER}")
    
    # Test TERTIARY_PROVIDER (should be None by default)
    assert config.TERTIARY_PROVIDER is None, "Tertiary should be None by default"
    print(f"✓ TERTIARY_PROVIDER = {config.TERTIARY_PROVIDER}")
    
    print("\n✅ TEST 4 PASSED\n")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("LLM FALLBACK CHAIN - VERIFICATION TESTS")
    print("="*60)
    
    try:
        test_config_defaults()
        test_groq_70b_rejection()
        test_qwen_feature_flag()
        test_provider_configuration()
        
        print("="*60)
        print("🎉 ALL TESTS PASSED!")
        print("="*60)
        print()
        print("✓ Qwen disabled by default")
        print("✓ 70B models rejected")
        print("✓ Graceful abort configured")
        print("✓ Provider configuration correct")
        print()
        print("System is demo-safe! ✨")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
