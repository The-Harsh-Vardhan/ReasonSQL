"""Test that Gemini is now the primary provider."""
print("="*60)
print("GEMINI PRIMARY PROVIDER - VERIFICATION")
print("="*60)

from config import LLM_PROVIDER, LLM_MODEL

print(f"\n✓ Provider: {LLM_PROVIDER}")
print(f"✓ Model: {LLM_MODEL}")

if LLM_PROVIDER == "gemini":
    print("\n✅ SUCCESS: Gemini is now the primary provider!")
else:
    print(f"\n❌ FAIL: Expected 'gemini' but got '{LLM_PROVIDER}'")

print("="*60)
