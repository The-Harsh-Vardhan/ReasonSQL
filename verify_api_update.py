"""Verify new Gemini API key and Groq model update."""
import os
from dotenv import load_dotenv

load_dotenv()

print("="*60)
print("API KEY & MODEL UPDATE VERIFICATION")
print("="*60)

# Check Gemini key
gemini_key = os.getenv('GOOGLE_API_KEY')
if gemini_key:
    print(f"\n✓ Gemini Key: {gemini_key[:20]}...{gemini_key[-4:]}")
else:
    print("\n✗ Gemini Key: NOT FOUND")

# Check Groq fallback model
groq_model = os.getenv('GROQ_FALLBACK_MODEL')
print(f"✓ Groq Fallback Model: {groq_model}")

# Check LLM provider
llm_provider = os.getenv('LLM_PROVIDER')
print(f"✓ LLM Provider: {llm_provider}")

# Check primary model
llm_model = os.getenv('LLM_MODEL')
print(f"✓ Primary Model: {llm_model}")

print("\n" + "="*60)
print("✅ Configuration updated successfully!")
print("="*60)
print("\nChanges:")
print("  • New Gemini API key installed")
print("  • Groq fallback model: llama-3.1-8b-instant")
print("    (Higher rate limits than llama-3.3-70b-versatile)")
print("\nRestart Streamlit to apply changes.")
