"""Demo of Gemini key rotation logic (simulation)."""

print("="*70)
print("GEMINI KEY ROTATION - SIMULATION")
print("="*70)

# Simulate the key rotation logic
class KeyRotationDemo:
    def __init__(self):
        self.keys = [
            "AIzaSyB69A22qMqh757X...vLGQ",
            "AIzaSyBr45BYl1WmV5aC...d0U2",
            "AIzaSyBZCfK1xLLcBadM...vkJs",
            "AIzaSyAft_UYIJ5voDjJ...q8U3"
        ]
        self.current_index = 0
        self.exhausted = set()
    
    def make_request(self, request_num, will_fail=False):
        print(f"\nRequest #{request_num}:")
        
        # Skip exhausted keys
        while self.current_index in self.exhausted and len(self.exhausted) < len(self.keys):
            self.current_index = (self.current_index + 1) % len(self.keys)
        
        if len(self.exhausted) >= len(self.keys):
            print("  X ALL KEYS EXHAUSTED - Falling back to Groq")
            return False
        
        key_num = self.current_index + 1
        print(f"  -> Using Gemini Key #{key_num}: {self.keys[self.current_index]}")
        
        if will_fail:
            print(f"  X Key #{key_num} quota exhausted (429 error)")
            print(f"  -> Marking key #{key_num} as exhausted")
            self.exhausted.add(self.current_index)
            self.current_index = (self.current_index + 1) % len(self.keys)
            print(f"  -> Rotating to key #{self.current_index + 1}")
            return False
        else:
            print(f"  ✓ Success with key #{key_num}")
            return True

demo = KeyRotationDemo()

print("\nScenario: Keys exhaust one by one\n")
print("-" * 70)

# Request 1: Key #1 works
demo.make_request(1, will_fail=False)

# Request 2: Key #1 exhausted, rotates to #2
demo.make_request(2, will_fail=True)
demo.make_request(3, will_fail=False)  # Retry with key #2

# Request 3: Key #2 exhausted, rotates to #3
demo.make_request(4, will_fail=True)
demo.make_request(5, will_fail=False)  # Retry with key #3

# Request 4: Key #3 exhausted, rotates to #4
demo.make_request(6, will_fail=True)
demo.make_request(7, will_fail=False)  # Retry with key #4

# Request 5: Key #4 exhausted, all keys gone
demo.make_request(8, will_fail=True)
demo.make_request(9, will_fail=True)  # Should fallback to Groq

print("\n" + "="*70)
print("SUMMARY:")
print(f"  - Total keys: {len(demo.keys)}")
print(f"  - Exhausted keys: {len(demo.exhausted)}")
print(f"  - Fallback triggered: {'Yes' if len(demo.exhausted) >= len(demo.keys) else 'No'}")
print("="*70)
