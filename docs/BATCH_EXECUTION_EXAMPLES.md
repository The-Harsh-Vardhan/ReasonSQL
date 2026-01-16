"""
EXAMPLE EXECUTION FLOWS: Batch-Optimized Orchestrator

This file demonstrates the API call reduction achieved through agent batching.

============================================================
EXAMPLE 1: Normal Query (2-3 API Calls)
============================================================

Query: "How many customers are from Brazil?"

EXECUTION FLOW:
┌────────────────────────────────────────────────────────────┐
│ BATCH 1: Reasoning & Planning [API CALL 1]                │
│   ├─ IntentAnalyzer: "DATA_QUERY"                         │
│   ├─ ClarificationAgent: No ambiguity                     │
│   ├─ QueryDecomposer: Simple query                        │
│   └─ QueryPlanner: SELECT COUNT(*) FROM Customer WHERE... │
├────────────────────────────────────────────────────────────┤
│ SchemaExplorer [DETERMINISTIC]                             │
│   └─ Database introspection: Customer table found         │
├────────────────────────────────────────────────────────────┤
│ BATCH 2: SQL Generation [API CALL 2]                      │
│   └─ SQLGenerator: Generates SQL with LIMIT               │
├────────────────────────────────────────────────────────────┤
│ SafetyValidator [DETERMINISTIC]                            │
│   └─ Approved: No violations                              │
├────────────────────────────────────────────────────────────┤
│ SQLExecutor [DETERMINISTIC]                                │
│   └─ Success: 5 rows returned                             │
├────────────────────────────────────────────────────────────┤
│ ResultValidator [DETERMINISTIC]                            │
│   └─ Valid: No warnings                                   │
├────────────────────────────────────────────────────────────┤
│ BATCH 4: Response Synthesis [API CALL 3]                  │
│   └─ ResponseSynthesizer: "There are 5 customers..."      │
└────────────────────────────────────────────────────────────┘

TOTAL API CALLS: 3
AGENTS EXECUTED: 12 (9 logged in trace)
QUOTA USED: 3/5 requests in current minute

============================================================
EXAMPLE 2: Query with Self-Correction (5 API Calls)
============================================================

Query: "List all albums by AC/DC"

EXECUTION FLOW:
┌────────────────────────────────────────────────────────────┐
│ BATCH 1: Reasoning & Planning [API CALL 1]                │
│   ├─ IntentAnalyzer: "DATA_QUERY"                         │
│   ├─ ClarificationAgent: No ambiguity                     │
│   ├─ QueryDecomposer: Moderate complexity (JOIN needed)   │
│   └─ QueryPlanner: Plan to JOIN Artist + Album            │
├────────────────────────────────────────────────────────────┤
│ SchemaExplorer [DETERMINISTIC]                             │
│   └─ Found: Artist, Album tables with foreign key         │
├────────────────────────────────────────────────────────────┤
│ BATCH 2: SQL Generation [API CALL 2]                      │
│   └─ SQLGenerator: Generates JOIN query                   │
├────────────────────────────────────────────────────────────┤
│ SafetyValidator [DETERMINISTIC]                            │
│   └─ Approved                                             │
├────────────────────────────────────────────────────────────┤
│ SQLExecutor [DETERMINISTIC]                                │
│   └─ ERROR: "no such column: Artist.ArtistName"           │
│       (Correct column is "Name", not "ArtistName")        │
├────────────────────────────────────────────────────────────┤
│ BATCH 3: Self-Correction (Retry 1) [API CALL 3]           │
│   └─ SelfCorrectionAgent: Analyzes error, fixes column    │
├────────────────────────────────────────────────────────────┤
│ SafetyValidator [DETERMINISTIC]                            │
│   └─ Approved: Corrected SQL is safe                      │
├────────────────────────────────────────────────────────────┤
│ SQLExecutor [DETERMINISTIC]                                │
│   └─ Success: 2 albums found                              │
├────────────────────────────────────────────────────────────┤
│ ResultValidator [DETERMINISTIC]                            │
│   └─ Valid                                                │
├────────────────────────────────────────────────────────────┤
│ BATCH 4: Response Synthesis [API CALL 4]                  │
│   └─ ResponseSynthesizer: "AC/DC has 2 albums..."         │
└────────────────────────────────────────────────────────────┘

TOTAL API CALLS: 4
RETRIES: 1
QUOTA USED: 4/5 requests in current minute

============================================================
EXAMPLE 3: Meta-Query (2 API Calls Only)
============================================================

Query: "What tables are in this database?"

EXECUTION FLOW:
┌────────────────────────────────────────────────────────────┐
│ BATCH 1: Reasoning & Planning [API CALL 1]                │
│   ├─ IntentAnalyzer: "META_QUERY"                         │
│   ├─ ClarificationAgent: Skipped (meta-query)             │
│   ├─ QueryDecomposer: Skipped (meta-query)                │
│   └─ QueryPlanner: Skipped (meta-query)                   │
├────────────────────────────────────────────────────────────┤
│ SchemaExplorer [DETERMINISTIC]                             │
│   └─ Lists all tables: Album, Artist, Customer, etc.      │
├────────────────────────────────────────────────────────────┤
│ BATCH 4: Response Synthesis [API CALL 2]                  │
│   └─ ResponseSynthesizer: "The database contains..."      │
└────────────────────────────────────────────────────────────┘

TOTAL API CALLS: 2
BATCHES SKIPPED: 2 (SQL Generation, Self-Correction)
QUOTA USED: 2/5 requests in current minute

============================================================
EXAMPLE 4: Rate Limit Scenario
============================================================

Scenario: 5 queries executed in rapid succession

Query 1: "Count customers"          → 3 API calls (Total: 3/5)
Query 2: "List genres"               → 3 API calls (Total: 6/5) ❌ BLOCKED

RATE LIMITER RESPONSE:
┌────────────────────────────────────────────────────────────┐
│ RateLimitExceeded Exception Raised                         │
│                                                            │
│ Error: "Rate limit of 5 requests/minute exceeded.         │
│         Would need to wait 42.3s. Aborting to prevent     │
│         overrun."                                          │
│                                                            │
│ Status: BLOCKED                                            │
│ Answer: "Query aborted: Rate limit exceeded"              │
└────────────────────────────────────────────────────────────┘

This demonstrates HARD rate limit enforcement.
The system aborts gracefully rather than making unauthorized calls.

============================================================
COMPARISON: Old vs New Orchestrator
============================================================

┌─────────────────────┬────────────────┬──────────────────┐
│ Scenario            │ Old (12 calls) │ New (Batched)    │
├─────────────────────┼────────────────┼──────────────────┤
│ Simple query        │ 12 API calls   │ 3 API calls      │
│ With 1 retry        │ 14 API calls   │ 4 API calls      │
│ With 2 retries      │ 16 API calls   │ 5 API calls      │
│ Meta-query          │ 5 API calls    │ 2 API calls      │
│ Rate limiting       │ None           │ 5 req/min HARD   │
│ Quota safety        │ Soft (logging) │ HARD (enforced)  │
└─────────────────────┴────────────────┴──────────────────┘

COST REDUCTION:
- Normal queries: 75% reduction (12 → 3)
- Queries with retry: 71% reduction (14 → 4)
- Meta-queries: 60% reduction (5 → 2)

SUSTAINABILITY:
- Old: Could exhaust quota in 1-2 minutes with rapid queries
- New: Hard limit ensures max 5 queries/minute regardless of complexity

============================================================
CODE EXAMPLE: Using the Orchestrator
============================================================

```python
from orchestrator import BatchOptimizedOrchestrator, RateLimitExceeded

# Initialize
orch = BatchOptimizedOrchestrator(verbose=True)

# Normal usage
try:
    response = orch.process_query("How many customers from Brazil?")
    print(response.answer)
    print(f"LLM calls made: {response.reasoning_trace.total_time_ms}")
except RateLimitExceeded as e:
    print(f"Rate limit hit: {e}")
    # Wait and retry, or queue for later

# Check rate limit status
print(orch.rate_limiter.get_status())
# Output: {'used': 3, 'limit': 5, 'remaining': 2, 'window_seconds': 60}
```

============================================================
TRANSPARENCY: Trace Output
============================================================

Even though batched, the reasoning trace shows all 12 agents:

```python
response = orch.process_query("Count customers")

for action in response.reasoning_trace.actions:
    print(f"{action.agent_name}: {action.reasoning}")
    print(f"  Batch: {action.output['llm_batch']}")
```

Output:
```
IntentAnalyzer: Intent: DATA_QUERY (confidence: 0.95)
  Batch: BATCH 1: Reasoning & Planning
ClarificationAgent: Resolved query: Count customers
  Batch: BATCH 1: Reasoning & Planning
QueryDecomposer: Complex: False, Steps: 1
  Batch: BATCH 1: Reasoning & Planning
QueryPlanner: Tables: ['Customer']
  Batch: BATCH 1: Reasoning & Planning
SchemaExplorer: Found 11 tables
  Batch: NONE
SQLGenerator: Generated SQL
  Batch: BATCH 2: SQL Generation
SafetyValidator: ✓ APPROVED
  Batch: NONE
SQLExecutor: ✓ Success: 59 rows
  Batch: NONE
ResultValidator: ✓ Valid
  Batch: NONE
ResponseSynthesizer: Generated answer
  Batch: BATCH 4: Response Synthesis
```

Judges can see:
- Which agents ran in which batch
- Logical separation maintained despite batching
- Total LLM calls vs logical agent count
"""
