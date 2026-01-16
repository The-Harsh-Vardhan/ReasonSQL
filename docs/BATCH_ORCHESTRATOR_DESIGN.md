# Batch-Optimized Orchestrator: Quota-Safety Refactor

## Overview

This orchestrator implements **STRICT agent batching** to reduce Gemini API calls from 12 per query to 2-5, while maintaining all 12 logical agents for architectural clarity and transparency.

## Problem Statement

**Before (Old System):**
- Each of 12 agents made individual LLM calls → 12+ API calls per query
- No rate limiting → Risk of quota exhaustion
- Soft budget warnings → Could be ignored
- Expensive for demo/judging scenarios

**After (Batch-Optimized):**
- 4 consolidated LLM calls (batches) → 2-5 API calls per query
- Hard rate limiting → 5 requests/minute enforced
- Graceful abort on limit → No silent overruns
- 75% cost reduction

## Agent → Batch Mapping

```
┌──────────────────────┬────────────────┬──────────────────────────────────┐
│ Logical Agent        │ Execution Type │ Batch Assignment                 │
├──────────────────────┼────────────────┼──────────────────────────────────┤
│ IntentAnalyzer       │ LLM            │ BATCH 1: Reasoning & Planning    │
│ ClarificationAgent   │ LLM            │ BATCH 1: Reasoning & Planning    │
│ QueryDecomposer      │ LLM            │ BATCH 1: Reasoning & Planning    │
│ QueryPlanner         │ LLM            │ BATCH 1: Reasoning & Planning    │
├──────────────────────┼────────────────┼──────────────────────────────────┤
│ SchemaExplorer       │ Deterministic  │ NO BATCH (Database introspection)│
│ DataExplorer         │ Deterministic  │ NO BATCH (Database sampling)     │
│ SafetyValidator      │ Deterministic  │ NO BATCH (Rule-based checks)     │
│ SQLExecutor          │ Deterministic  │ NO BATCH (Query execution)       │
│ ResultValidator      │ Deterministic  │ NO BATCH (Sanity checks)         │
├──────────────────────┼────────────────┼──────────────────────────────────┤
│ SQLGenerator         │ LLM            │ BATCH 2: SQL Generation          │
├──────────────────────┼────────────────┼──────────────────────────────────┤
│ SelfCorrectionAgent  │ LLM            │ BATCH 3: Correction (conditional)│
├──────────────────────┼────────────────┼──────────────────────────────────┤
│ ResponseSynthesizer  │ LLM            │ BATCH 4: Response                │
└──────────────────────┴────────────────┴──────────────────────────────────┘
```

**WHY THIS GROUPING?**

- **BATCH 1** combines early reasoning agents because they all analyze the user query + schema without needing SQL execution results
- **BATCH 2** is isolated because SQL generation requires the completed plan from Batch 1
- **BATCH 3** is conditional (only on execution failure) and needs error feedback
- **BATCH 4** is last because response synthesis needs final results
- **Deterministic agents** use pure database operations or rule-based logic (no LLM needed)

## API Call Budget

```
Normal query:  3 API calls  (Batch 1 + Batch 2 + Batch 4)
Meta-query:    2 API calls  (Batch 1 + Batch 4, skip SQL generation)
With 1 retry:  4 API calls  (+ Batch 3)
With 2 retries: 5 API calls (+ Batch 3 twice)

HARD LIMIT: 5 requests/minute (enforced at runtime)
```

## Rate Limiter Implementation

### Design: Sliding Window

```python
class RateLimiter:
    def __init__(self, max_requests=5, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_times = deque()  # Stores timestamps
    
    def can_proceed(self) -> bool:
        """Check if request is allowed."""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)
        
        # Remove expired timestamps
        while self.request_times and self.request_times[0] < cutoff:
            self.request_times.popleft()
        
        return len(self.request_times) < self.max_requests
    
    def record_request(self):
        """Record a new request."""
        self.request_times.append(datetime.now())
```

### Enforcement

The orchestrator **aborts gracefully** if rate limit is exceeded:

```python
def call_llm_batch(...):
    if not self.rate_limiter.can_proceed():
        wait_time = self.rate_limiter.wait_time()
        raise RateLimitExceeded(
            f"Rate limit of 5 requests/minute exceeded. "
            f"Would need to wait {wait_time:.1f}s. Aborting."
        )
```

**No silent overruns.** The system will NOT make unauthorized API calls.

## Single Entry Point: `call_llm_batch()`

All LLM calls go through this method:

```python
def call_llm_batch(
    batch_name: str,        # e.g., "BATCH 1: Reasoning & Planning"
    roles: List[str],       # e.g., ["IntentAnalyzer", "ClarificationAgent"]
    prompt: str,            # Multi-role prompt with JSON schema
    state: PipelineState    # Current state
) -> Dict[str, Any]:
    """
    ENFORCES:
    - Rate limiting (5 req/min hard)
    - Structured JSON output
    - Logging and traceability
    """
```

**Agents never call LLM directly.** They are passive data processors that receive outputs from batched LLM calls.

## Transparency & Traceability

Even though agents are batched, the reasoning trace maintains full visibility:

```python
response = orchestrator.process_query("How many customers?")

for action in response.reasoning_trace.actions:
    print(f"{action.agent_name}: {action.reasoning}")
    # Output includes which batch executed this agent
```

Example trace output:

```
IntentAnalyzer: Intent: DATA_QUERY (confidence: 0.95)
  Batch: BATCH 1: Reasoning & Planning
  LLM Calls So Far: 1

ClarificationAgent: No ambiguity detected
  Batch: BATCH 1: Reasoning & Planning
  LLM Calls So Far: 1

SchemaExplorer: Found 11 tables
  Batch: NONE (Deterministic)
  LLM Calls So Far: 1

SQLGenerator: Generated SQL
  Batch: BATCH 2: SQL Generation
  LLM Calls So Far: 2

ResponseSynthesizer: Generated answer
  Batch: BATCH 4: Response Synthesis
  LLM Calls So Far: 3
```

**Judges can see:**
- All 12 agents executed
- Which agents ran in which batch
- Total LLM calls vs logical agent count
- Why batching was necessary

## Cost Comparison

| Scenario | Old System | New System | Reduction |
|----------|------------|------------|-----------|
| Simple query | 12 calls | 3 calls | **75%** |
| With 1 retry | 14 calls | 4 calls | **71%** |
| With 2 retries | 16 calls | 5 calls | **69%** |
| Meta-query | 5 calls | 2 calls | **60%** |
| **100 queries/day** | **1,200 calls** | **300 calls** | **75%** |

## Usage Example

```python
from orchestrator import BatchOptimizedOrchestrator, RateLimitExceeded

# Initialize
orch = BatchOptimizedOrchestrator(verbose=True)

# Process query
try:
    response = orch.process_query("How many customers from Brazil?")
    print(response.answer)
    
    # Check quota usage
    print(f"LLM calls: {len(response.reasoning_trace.actions)}")
    print(f"Rate limit: {orch.rate_limiter.get_status()}")

except RateLimitExceeded as e:
    print(f"Rate limit hit: {e}")
    # Wait and retry, or queue for later
```

## Testing

Run the test suite to verify batching:

```bash
python test_batch_orchestrator.py
```

Tests include:
1. Simple query execution (verify 3 API calls)
2. Rate limiter functionality (verify 5 req/min enforcement)
3. Agent-to-batch mapping verification
4. Graceful abort on rate limit
5. Cost comparison demonstration

## Why This Refactor Matters

### For Demos/Judging
- **Sustainable**: Can run indefinitely without quota exhaustion
- **Predictable**: Max 5 requests/minute regardless of query complexity
- **Transparent**: All 12 agents visible in trace despite batching

### For Production
- **Cost-effective**: 75% reduction in API costs
- **Robust**: Hard rate limiting prevents overruns
- **Maintainable**: Agent logic unchanged, only orchestration refactored

### For Development
- **Debuggable**: Full trace shows which agents ran when
- **Flexible**: Easy to adjust batch groupings if needed
- **Documented**: Clear mapping between agents and batches

## Architecture Preservation

**What DIDN'T change:**
- All 12 agents still exist as logical components
- Agent responsibilities unchanged
- Reasoning transparency maintained
- Error handling and self-correction preserved

**What DID change:**
- Multiple agents execute in single LLM calls (batching)
- Hard rate limiting enforced
- Orchestrator controls ALL LLM calls (agents are passive)
- Graceful abort on quota violations

This is a **quota-safety refactor**, not a feature change.
