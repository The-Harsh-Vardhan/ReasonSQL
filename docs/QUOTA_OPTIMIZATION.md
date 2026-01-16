# LLM Quota Optimization Guide

## Overview

The NL2SQL Multi-Agent System has been optimized to minimize LLM API calls while maintaining the conceptual 12-agent architecture.

## Agent Classification

| Agent | Type | LLM Call | Notes |
|-------|------|----------|-------|
| IntentAnalyzer | LLM_REQUIRED | Call 1 | Consolidated with ClarificationAgent |
| ClarificationAgent | LLM_REQUIRED | Call 1 | Consolidated with IntentAnalyzer |
| SchemaExplorer | **NON_LLM** | - | Pure database introspection |
| QueryDecomposer | LLM_REQUIRED | Call 2 | Consolidated with QueryPlanner |
| DataExplorer | **NON_LLM** | - | Pure database sampling |
| QueryPlanner | LLM_REQUIRED | Call 2 | Consolidated with QueryDecomposer |
| SQLGenerator | LLM_REQUIRED | Call 3 | Dedicated SQL generation |
| SafetyValidator | **NON_LLM** | - | Rule-based validation |
| SQLExecutor | **NON_LLM** | - | Pure database execution |
| SelfCorrection | LLM_REQUIRED | Call 4* | *Only on execution failure |
| ResultValidator | **NON_LLM** | - | Rule-based sanity checks |
| ResponseSynthesizer | LLM_REQUIRED | Call 5 | Final answer generation |

## LLM Call Budget

### Normal Query Flow (No Errors)

```
User Query
    │
    ▼
┌─────────────────────────────────────┐
│ LLM Call 1: Query Understanding     │  ← IntentAnalyzer + ClarificationAgent
│   - Intent classification           │
│   - Ambiguity detection/resolution  │
│   - Complexity assessment           │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ NON-LLM: Schema Exploration         │  ← Database introspection only
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ LLM Call 2: Query Planning          │  ← QueryDecomposer + QueryPlanner
│   - Decomposition (if complex)      │
│   - Join strategy                   │
│   - Column selection                │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ LLM Call 3: SQL Generation          │  ← SQLGenerator
│   - Generate valid SQLite SQL       │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ NON-LLM: Safety Validation          │  ← Rule-based checks
│ NON-LLM: SQL Execution              │  ← Database execution
│ NON-LLM: Result Validation          │  ← Sanity checks
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ LLM Call 4: Response Synthesis      │  ← ResponseSynthesizer
│   - Generate human-readable answer  │
└─────────────────────────────────────┘
    │
    ▼
  Response (4 LLM calls total)
```

### Error Recovery Flow

```
Execution Failure
    │
    ▼
┌─────────────────────────────────────┐
│ LLM Call N: Self-Correction         │  ← SelfCorrection Agent
│   - Analyze error                   │
│   - Generate corrected SQL          │
└─────────────────────────────────────┘
    │
    ▼
  Back to Safety Validation
  (adds 1 LLM call per retry, max 2 retries)
```

## Expected LLM Call Counts

| Scenario | LLM Calls | Notes |
|----------|-----------|-------|
| Simple data query | 4 | Understanding → Planning → SQL → Response |
| Meta query | 2 | Understanding → Response (skips planning/SQL) |
| Query with 1 retry | 5 | +1 for self-correction |
| Query with 2 retries | 6 | +2 for self-corrections |
| Max possible | 8 | Hard cap (configurable) |

## Quota Comparison

### Before Optimization (Deterministic Orchestrator)

Each agent made its own LLM call:
- IntentAnalyzer: 1 call
- ClarificationAgent: 1 call
- SchemaExplorer: 1 call
- QueryDecomposer: 1 call
- DataExplorer: 1 call
- QueryPlanner: 1 call
- SQLGenerator: 1 call
- SafetyValidator: 1 call
- SQLExecutor: 1 call
- SelfCorrection: 1-3 calls
- ResultValidator: 1 call
- ResponseSynthesizer: 1 call

**Total: 11-14 LLM calls per query**

### After Optimization (Quota-Optimized Orchestrator)

- Query Understanding: 1 consolidated call (was 2)
- Query Planning: 1 consolidated call (was 2)
- SQL Generation: 1 call
- Self-Correction: 0-2 calls (only on failure)
- Response Synthesis: 1 call

**Total: 4-6 LLM calls per query**

**Reduction: 60-70% fewer LLM calls**

## Usage

### Basic Usage

```python
from orchestrator import QuotaOptimizedOrchestrator

# Default: 8 LLM calls max
orchestrator = QuotaOptimizedOrchestrator()
response = orchestrator.process_query("How many customers are from Brazil?")

# Check LLM usage
print(f"LLM calls used: {response.execution_metrics['llm_calls']}")
print(f"Budget: {response.execution_metrics['llm_budget']}")
```

### Custom Budget

```python
# Strict budget for demos
orchestrator = QuotaOptimizedOrchestrator(max_llm_calls=5)

# Relaxed budget for complex queries
orchestrator = QuotaOptimizedOrchestrator(max_llm_calls=10)
```

### CLI Usage

```bash
# Uses quota-optimized orchestrator by default
python cli.py -q "How many customers are from Brazil?"

# Check the execution metrics in output for LLM usage
```

## Rate Limit Handling

The orchestrator includes automatic retry with exponential backoff:

1. First retry: Wait 5 seconds
2. Second retry: Wait 10 seconds
3. Third retry: Wait 20 seconds
4. After 3 failed retries: Raise error

## Configuration

In `.env`:

```bash
# Provider (groq recommended for higher rate limits)
LLM_PROVIDER=gemini  # or groq

# Model
LLM_MODEL=gemini/gemini-2.5-flash

# Retries (reduced from 3 to 2 for quota efficiency)
MAX_RETRIES=2
```

## Gemini API Quotas

| Tier | Requests/Minute | Requests/Day |
|------|-----------------|--------------|
| Free | 5 | 20 |
| Pay-as-you-go | 2,000 | Unlimited |

With 4-6 calls per query, free tier supports ~3-5 queries per day.

**Recommendation:** Use Groq API for development (higher free tier limits).

## Architecture Principles

1. **Agents remain conceptually separate** - Each agent has clear responsibilities
2. **Consolidation is at execution level** - Multiple agents share LLM calls
3. **NON-LLM agents are pure code** - No hidden LLM calls
4. **Budget is explicit** - Every call is tracked and logged
5. **Orchestrator controls all LLM access** - No agent can call LLM directly
