# Orchestrator Implementations

This directory contains multiple orchestrator implementations, each optimized for different use cases.

## Recommended: Batch-Optimized Orchestrator ⭐

**File:** `batch_optimized_orchestrator.py`

**Use when:** Production deployment, demos, judging scenarios requiring quota safety

**Features:**
- ✅ HARD rate limiting (5 requests/minute enforced)
- ✅ Agent batching (12 agents → 2-5 API calls)
- ✅ 75% cost reduction vs naive approach
- ✅ Graceful abort on quota violations
- ✅ Full transparency (all 12 agents in trace)

**API Call Budget:**
- Normal query: 3 calls
- With retry: 4-5 calls
- Meta-query: 2 calls

```python
from orchestrator import BatchOptimizedOrchestrator

orch = BatchOptimizedOrchestrator(verbose=True)
response = orch.process_query("Your question here")
```

**See:** `docs/BATCH_ORCHESTRATOR_DESIGN.md` for full documentation

---

## Quota-Optimized Orchestrator

**File:** `quota_optimized_orchestrator.py`

**Use when:** You need quota awareness but don't need hard rate limiting

**Features:**
- ✅ Consolidated LLM calls (12 agents → 4-6 API calls)
- ✅ Budget tracking and warnings
- ⚠️ Soft limits (can be exceeded)
- ✅ Reduced retry limit (2 vs 3)

**API Call Budget:**
- Normal query: 4 calls
- With retry: 5-6 calls
- Hard cap: 8 calls

```python
from orchestrator import QuotaOptimizedOrchestrator

orch = QuotaOptimizedOrchestrator(verbose=True, max_llm_calls=8)
response = orch.process_query("Your question here")
```

**See:** `docs/QUOTA_OPTIMIZATION.md`

---

## Deterministic Orchestrator

**File:** `deterministic_orchestrator.py`

**Use when:** You need full control and explicit state machine flow

**Features:**
- ✅ Explicit state transitions
- ✅ Deterministic execution order
- ✅ No agent-to-agent calls
- ⚠️ Higher LLM usage (up to 12 calls)

**API Call Budget:**
- Uses LLM for each of 7 LLM-required agents
- No batching optimization

```python
from orchestrator import DeterministicOrchestrator

orch = DeterministicOrchestrator(verbose=True)
response = orch.process_query("Your question here")
```

---

## Enhanced Orchestrator (Legacy)

**File:** `enhanced_orchestrator.py`

**Use when:** Reference implementation only

**Features:**
- Original 12-agent implementation
- Sequential execution
- Full CrewAI integration

**Not recommended for production** (high API usage)

---

## Crew Orchestrator (Legacy)

**File:** `crew_orchestrator.py`

**Use when:** Reference implementation only

**Features:**
- Original proof-of-concept
- Basic CrewAI usage

**Not recommended for production**

---

## Comparison Table

| Orchestrator | API Calls/Query | Rate Limiting | Recommended For |
|--------------|----------------|---------------|-----------------|
| **Batch-Optimized** ⭐ | 2-5 | HARD (5 req/min) | **Production, Demos** |
| Quota-Optimized | 4-6 | Soft (warnings) | Development |
| Deterministic | 7-12 | None | Testing, Control |
| Enhanced (Legacy) | 12+ | None | Reference only |
| Crew (Legacy) | 12+ | None | Reference only |

## Default Export

```python
from orchestrator import NL2SQLOrchestrator, run_query

# NL2SQLOrchestrator is an alias for BatchOptimizedOrchestrator
orch = NL2SQLOrchestrator()

# Or use the convenience function
response = run_query("Your question here")
```

## Migration Guide

### From Quota-Optimized → Batch-Optimized

```python
# Old
from orchestrator import QuotaOptimizedOrchestrator
orch = QuotaOptimizedOrchestrator(max_llm_calls=8)

# New
from orchestrator import BatchOptimizedOrchestrator
orch = BatchOptimizedOrchestrator()
# Rate limiting is automatic (5 req/min)
```

### From Deterministic → Batch-Optimized

```python
# Old
from orchestrator import DeterministicOrchestrator
orch = DeterministicOrchestrator()

# New
from orchestrator import BatchOptimizedOrchestrator
orch = BatchOptimizedOrchestrator()
# Agent execution is still deterministic, just batched
```

## Testing

Test the batch-optimized orchestrator:

```bash
python test_batch_orchestrator.py
```

See example execution flows:
- `docs/BATCH_EXECUTION_EXAMPLES.md`

## Rate Limit Handling

```python
from orchestrator import BatchOptimizedOrchestrator, RateLimitExceeded

orch = BatchOptimizedOrchestrator()

try:
    response = orch.process_query("Your question")
except RateLimitExceeded as e:
    print(f"Rate limit hit: {e}")
    # Wait and retry, or queue for later
    
# Check status
status = orch.rate_limiter.get_status()
print(f"Used: {status['used']}/{status['limit']}")
print(f"Remaining: {status['remaining']}")
```

## Why Batch-Optimized is Default

1. **Sustainability**: Can run indefinitely without quota exhaustion
2. **Cost**: 75% reduction in API costs
3. **Safety**: Hard rate limiting prevents accidental overruns
4. **Transparency**: All 12 agents maintained in trace
5. **Production-ready**: Graceful error handling

For detailed design rationale, see `docs/BATCH_ORCHESTRATOR_DESIGN.md`
