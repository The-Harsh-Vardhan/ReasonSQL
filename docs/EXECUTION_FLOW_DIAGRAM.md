# Batch-Optimized Orchestrator Execution Flow

## Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER SUBMITS QUERY                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      RATE LIMITER CHECK                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ Can we proceed? (Check: request_count < 5 in last 60 seconds)       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                │                                    │
                ▼ YES                                ▼ NO
       ┌─────────────────┐                 ┌──────────────────────┐
       │ Proceed         │                 │ RateLimitExceeded    │
       └─────────────────┘                 │ ABORT gracefully     │
                │                           └──────────────────────┘
                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  🧠 BATCH 1: Reasoning & Planning                          [API CALL #1]    │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Single LLM call executing 4 logical agents in one prompt:             │ │
│  │   1. IntentAnalyzer:     Classify DATA_QUERY | META_QUERY | AMBIGUOUS │ │
│  │   2. ClarificationAgent: Resolve ambiguities, make assumptions        │ │
│  │   3. QueryDecomposer:    Analyze complexity, identify steps           │ │
│  │   4. QueryPlanner:       Design query plan (tables, joins, filters)   │ │
│  │                                                                        │ │
│  │ LLM returns JSON with results from all 4 agents                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │ Intent?       │
        └───────────────┘
                │
    ┌───────────┼───────────┬────────────┐
    ▼           ▼           ▼            ▼
[AMBIGUOUS] [META_QUERY] [DATA_QUERY] [DATA_QUERY]
 (unresolved)              (simple)     (complex)
    │           │              │            │
    │           │              └────────┬───┘
    │           │                       │
    ▼           │                       ▼
  ABORT         │         ┌─────────────────────────────────┐
  (block)       │         │ 📊 SchemaExplorer [Deterministic]│
                │         │   - Database introspection      │
                │         │   - NO LLM call                 │
                │         └─────────────────────────────────┘
                │                       │
                │                       ▼
                │              ┌─────────────────┐
                │              │ Needs data      │
                │              │ context?        │
                │              └─────────────────┘
                │                   │        │
                │                   ▼ NO     ▼ YES
                │                   │    ┌───────────────────────────┐
                │                   │    │ 🔍 DataExplorer           │
                │                   │    │   [Deterministic]         │
                │                   │    │   - Sample data           │
                │                   │    │   - NO LLM call           │
                │                   │    └───────────────────────────┘
                │                   │              │
                │                   └──────┬───────┘
                │                          │
                ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  (META_QUERY path)                    (DATA_QUERY path)                     │
│  Skip SQL generation                                                        │
│  Go directly to Response              ▼                                     │
│  Synthesis (Batch 4)           ┌─────────────────────────────────────────┐ │
│                                │ ⚙️  BATCH 2: SQL Generation [API CALL #2]│ │
│                                │  ┌────────────────────────────────────┐ │ │
│                                │  │ Single LLM call:                   │ │ │
│                                │  │   SQLGenerator: Generate SQL       │ │ │
│                                │  │                                    │ │ │
│                                │  │ Uses plan from Batch 1             │ │ │
│                                │  │ Applies safety rules (LIMIT, etc.)  │ │ │
│                                │  └────────────────────────────────────┘ │ │
│                                └─────────────────────────────────────────┘ │
│                                                │                            │
│                                                ▼                            │
│                                  ┌───────────────────────────────┐         │
│                                  │ 🛡️  SafetyValidator           │         │
│                                  │   [Deterministic]             │         │
│                                  │   - Check forbidden keywords  │         │
│                                  │   - Verify LIMIT clause       │         │
│                                  │   - Reject SELECT *           │         │
│                                  │   - NO LLM call               │         │
│                                  └───────────────────────────────┘         │
│                                                │                            │
│                                    ┌───────────┴──────────┐                │
│                                    ▼                      ▼                │
│                              [APPROVED]              [REJECTED]            │
│                                    │                      │                │
│                                    │                      ▼                │
│                                    │                    ABORT              │
│                                    │                                       │
│                                    ▼                                       │
│                         ┌────────────────────────────┐                     │
│                         │ 🚀 SQLExecutor              │                     │
│                         │   [Deterministic]          │                     │
│                         │   - Execute SQL            │                     │
│                         │   - Capture results/errors │                     │
│                         │   - NO LLM call            │                     │
│                         └────────────────────────────┘                     │
│                                    │                                       │
│                        ┌───────────┴───────────┐                           │
│                        ▼                       ▼                           │
│                   [SUCCESS]              [ERROR]                           │
│                        │                       │                           │
│                        │                       ▼                           │
│                        │              ┌──────────────────┐                 │
│                        │              │ Retry available? │                 │
│                        │              └──────────────────┘                 │
│                        │                   │          │                    │
│                        │                   ▼ YES     ▼ NO                  │
│                        │     ┌────────────────────────┐  │                 │
│                        │     │ 🔄 BATCH 3: Correction │  │                 │
│                        │     │    [API CALL #3]       │  │                 │
│                        │     │  ┌──────────────────┐  │  │                 │
│                        │     │  │ Single LLM call: │  │  │                 │
│                        │     │  │ SelfCorrection   │  │  │                 │
│                        │     │  │ - Analyze error  │  │  │                 │
│                        │     │  │ - Fix SQL        │  │  │                 │
│                        │     │  └──────────────────┘  │  │                 │
│                        │     └────────────────────────┘  │                 │
│                        │                   │             │                 │
│                        │                   └──► Re-validate & Re-execute   │
│                        │                       (max 2 retries)             │
│                        │                                 │                 │
│                        └─────────────────────────────────┘                 │
│                                    │                                       │
│                                    ▼                                       │
│                         ┌────────────────────────────┐                     │
│                         │ ✅ ResultValidator          │                     │
│                         │   [Deterministic]          │                     │
│                         │   - Sanity checks          │                     │
│                         │   - Anomaly detection      │                     │
│                         │   - NO LLM call            │                     │
│                         └────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
                │                                 │
                └────────────┬────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  💬 BATCH 4: Response Synthesis                        [API CALL #4 or #2] │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Single LLM call:                                                       │ │
│  │   ResponseSynthesizer: Generate human-readable answer                 │ │
│  │                                                                        │ │
│  │ Uses query results (or error) to create natural language response     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FINAL RESPONSE                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ • Human-readable answer                                                │ │
│  │ • Generated SQL                                                        │ │
│  │ • Row count                                                            │ │
│  │ • Execution status                                                     │ │
│  │ • Full reasoning trace (12 agents logged with batch info)             │ │
│  │ • Warnings (if any)                                                    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────────┐
                    │ Rate Limiter Update│
                    │ Record this request│
                    └────────────────────┘
```

## API Call Count by Scenario

### Scenario 1: Simple Data Query (No Errors)
```
Batch 1: Reasoning & Planning    → API Call #1
SchemaExplorer (deterministic)   → No API call
Batch 2: SQL Generation          → API Call #2
SafetyValidator (deterministic)  → No API call
SQLExecutor (deterministic)      → No API call
ResultValidator (deterministic)  → No API call
Batch 4: Response Synthesis      → API Call #3

TOTAL: 3 API calls
```

### Scenario 2: Meta-Query
```
Batch 1: Reasoning & Planning    → API Call #1
SchemaExplorer (deterministic)   → No API call
[Skip Batch 2 - no SQL needed]
Batch 4: Response Synthesis      → API Call #2

TOTAL: 2 API calls
```

### Scenario 3: Query with 1 Retry
```
Batch 1: Reasoning & Planning    → API Call #1
SchemaExplorer (deterministic)   → No API call
Batch 2: SQL Generation          → API Call #2
SafetyValidator (deterministic)  → No API call
SQLExecutor (deterministic)      → Error!
Batch 3: Self-Correction         → API Call #3
SafetyValidator (deterministic)  → No API call
SQLExecutor (deterministic)      → Success
ResultValidator (deterministic)  → No API call
Batch 4: Response Synthesis      → API Call #4

TOTAL: 4 API calls
```

### Scenario 4: Query with 2 Retries (Max)
```
Batch 1: Reasoning & Planning    → API Call #1
SchemaExplorer (deterministic)   → No API call
Batch 2: SQL Generation          → API Call #2
SQLExecutor → Error #1
Batch 3: Self-Correction (1st)   → API Call #3
SQLExecutor → Error #2
Batch 3: Self-Correction (2nd)   → API Call #4
SQLExecutor → Success
Batch 4: Response Synthesis      → API Call #5

TOTAL: 5 API calls (hits rate limit!)
```

## Rate Limit Enforcement Points

```
                  Request Queue
                       │
                       ▼
              ┌────────────────────┐
              │  RateLimiter Check │ ◄──── Before EVERY batch call
              └────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
   [Can Proceed]              [Cannot Proceed]
         │                           │
         ▼                           ▼
   Make API Call            RaiseLimitExceeded
   Record timestamp         Abort gracefully
         │                           │
         ▼                           ▼
   Continue execution        Return error response
```

## Key Design Principles Visualized

1. **Batching**: Multiple logical agents in one API call
   ```
   Old: Agent 1 → LLM → Agent 2 → LLM → Agent 3 → LLM
   New: Agents 1,2,3 → Single LLM call → All results
   ```

2. **Deterministic Agents**: No LLM needed
   ```
   SchemaExplorer → SQLite PRAGMA → Results (0 API calls)
   SafetyValidator → Regex checks → Approved/Rejected (0 API calls)
   ```

3. **Single Entry Point**: All LLM calls through orchestrator
   ```
   Agents ❌ → LLM (forbidden)
   Orchestrator ✅ → LLM → Agents receive results
   ```

4. **Hard Rate Limiting**: No overruns possible
   ```
   Request 5: ✅ Allowed (5/5)
   Request 6: ❌ BLOCKED (would be 6/5)
   ```
