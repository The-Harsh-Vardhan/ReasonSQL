"""Test Gemini API key rotation."""
import os
from dotenv import load_dotenv

load_dotenv()

print("="*60)
print("GEMINI API KEY ROTATION - VERIFICATION")
print("="*60)

# Check all keys
keys = []
for i in range(1, 10):
    key = os.getenv(f"GEMINI_API_KEY_{i}")
    if key:
        keys.append((i, key))

print(f"\n✓ Found {len(keys)} Gemini API keys:")
for num, key in keys:
    print(f"  Key #{num}: {key[:20]}...{key[-4:]}")

# Test GeminiClient initialization
print("\n" + "-"*60)
print("Testing GeminiClient initialization...")
print("-"*60)

try:
    from orchestrator.llm_client import GeminiClient
    
    client = GeminiClient(verbose=True)
    print(f"\n✓ GeminiClient initialized successfully")
    print(f"  Total keys loaded: {len(client.api_keys)}")
    print(f"  Current key index: {client.current_key_index}")
    print(f"  Exhausted keys: {client.exhausted_keys}")
    
    print("\n✅ Key rotation system ready!")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("="*60)
