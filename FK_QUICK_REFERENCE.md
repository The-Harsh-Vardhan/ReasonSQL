# FK-Safe JOIN Validation - Quick Reference

## What Was Fixed

**Bug:** System generates schema-invalid JOINs like `Artist.ArtistId = Track.AlbumId`  
**Fix:** Validate all JOINs against FK relationships, auto-correct using BFS pathfinding

## Key Changes Summary

### 1. New Module: `tools/schema_graph.py` (461 lines)

```python
# Build FK graph from database
graph = SchemaGraph.from_database(DATABASE_PATH)

# Validate JOIN condition
is_valid, error = graph.validate_join_condition("Artist.ArtistId = Track.AlbumId")
# → (False, "Invalid JOIN: not a direct FK relationship...")

# Get correct FK path
path = graph.get_fk_path("Artist", "Track")
# → JoinPath(tables=["Artist", "Album", "Track"], edges=[...])

# Suggest corrections
suggestion = graph.suggest_correct_joins("Artist", "Track")
# → "Multi-hop path required: Artist → Album → Track\nJOIN conditions needed:\n..."
```

### 2. Orchestrator Changes: `batch_optimized_orchestrator.py`

**Import:**
```python
from tools.schema_graph import SchemaGraph
```

**Initialization:**
```python
def __init__(self):
    self.schema_graph = SchemaGraph.from_database(DATABASE_PATH)
```

**SafetyValidator Enhancement:**
```python
def _deterministic_safety_validation(self, state):
    # Extract all JOIN conditions from SQL
    join_conditions = self.schema_graph.get_all_joins_in_sql(sql)
    
    # Validate each JOIN against FK graph
    for join_cond in join_conditions:
        is_valid, error_msg = self.schema_graph.validate_join_condition(join_cond)
        
        if not is_valid:
            fk_violations.append(error_msg)
            suggestion = self.schema_graph.suggest_correct_joins(table1, table2)
            fk_violations.append(f"Suggestion: {suggestion}")
    
    state.fk_violations = fk_violations  # Store for self-correction
```

**Self-Correction Enhancement:**
```python
def _batch_3_self_correction(self, state):
    if state.fk_violations:
        error_context = f"FK SCHEMA VIOLATION: {'; '.join(state.fk_violations)}"
    
    prompt = f"""
    CRITICAL: If the error mentions FK violations:
    - You MUST use the suggested FK path provided
    - Example: Artist → Track requires intermediate Album
    
    {error_context}
    """
```

**Execution Flow Update:**
```python
# Check for FK violations BEFORE execution
if state.fk_violations:
    # Trigger immediate self-correction
    retry_loop = 0
    while retry_loop <= state.max_retries:
        state = self._batch_3_self_correction(state)
        state = self._deterministic_safety_validation(state)
        
        if state.safety_approved:
            break
```

### 3. State Model: `BatchPipelineState`

**New Field:**
```python
class BatchPipelineState:
    fk_violations: List[str] = field(default_factory=list)
```

## Execution Flow

### Before (No FK Validation):
```
SQL Generation → SafetyValidator (basic checks) → Execute → Possible semantic error
```

### After (FK Validation):
```
SQL Generation 
  ↓
SafetyValidator (FK + basic checks)
  ↓
FK Violation Detected? 
  ├─ NO → Execute
  └─ YES → Self-Correction (with FK path suggestion)
           ↓
           SafetyValidator (re-check)
           ↓
           Still Invalid? → Retry (max 2)
           Valid? → Execute
```

## Testing

**Unit Test:**
```bash
python test_fk_validation.py
```

**E2E Demo:**
```bash
python demo_fk_correction.py
```

## Example: Artist → Track Query

**Query:** "List top 5 artists by number of tracks"

**LLM Generates (WRONG):**
```sql
SELECT Artist.Name, COUNT(Track.TrackId)
FROM Artist
JOIN Track ON Artist.ArtistId = Track.AlbumId  -- ❌ INVALID FK
GROUP BY Artist.Name
LIMIT 5
```

**SafetyValidator Detects:**
```
✗ FK VIOLATION: Artist.ArtistId = Track.AlbumId is not a direct FK relationship
Suggestion: Multi-hop path required: Artist → Album → Track
  JOIN conditions needed:
    Artist.ArtistId = Album.ArtistId
    Album.AlbumId = Track.AlbumId
```

**SelfCorrection Fixes:**
```sql
SELECT Artist.Name, COUNT(Track.TrackId)
FROM Artist
JOIN Album ON Artist.ArtistId = Album.ArtistId    -- ✓ VALID FK
JOIN Track ON Album.AlbumId = Track.AlbumId      -- ✓ VALID FK
GROUP BY Artist.Name
LIMIT 5
```

**Result:** ✅ Query executes successfully with correct FK path

## Reasoning Trace Example

```
SafetyValidator: ✗ FK VIOLATION: 1 invalid JOIN(s)
  Detail: Artist.ArtistId = Track.AlbumId

SelfCorrectionAgent: FK CORRECTION (Retry 1): Detected invalid FK relationship
  Detail: SELECT ... FROM Artist JOIN Album ON Artist.ArtistId = Album.ArtistId 
          JOIN Track ON Album.AlbumId = Track.AlbumId ...

SafetyValidator: ✓ APPROVED (all safety checks passed)

SQLExecutor: ✓ Success: 5 rows
```

## Files Created/Modified

| File | Status | Purpose |
|------|--------|---------|
| `tools/schema_graph.py` | ✅ NEW | FK graph + validation logic |
| `orchestrator/batch_optimized_orchestrator.py` | ✅ MODIFIED | SafetyValidator + SelfCorrection |
| `test_fk_validation.py` | ✅ NEW | Unit tests |
| `demo_fk_correction.py` | ✅ NEW | E2E demo |
| `FK_VALIDATION_SYSTEM.md` | ✅ NEW | Detailed docs |
| `FK_QUICK_REFERENCE.md` | ✅ NEW | This file |

## Status

🟢 **COMPLETE** - FK validation fully integrated and tested

## Usage

The system now automatically:
1. Detects schema-invalid JOINs before execution
2. Suggests correct FK paths
3. Triggers LLM self-correction
4. Retries up to 2 times
5. Aborts if FK violations persist

**No manual intervention needed** - all handled transparently in reasoning trace.
