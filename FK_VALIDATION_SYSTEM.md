# FK-Safe JOIN Validation System

## Overview

Prevents schema-invalid JOINs by validating all JOIN conditions against actual foreign key relationships in the database. Automatically corrects invalid JOINs using BFS pathfinding through the FK graph.

## Problem

**Before:** System generates syntactically valid but schema-invalid JOINs:
```sql
-- WRONG: Artist.ArtistId = Track.AlbumId (violates FK schema)
SELECT Artist.Name, COUNT(Track.TrackId)
FROM Artist
JOIN Track ON Artist.ArtistId = Track.AlbumId  -- ❌ NO FK EXISTS
GROUP BY Artist.Name
```

**After:** System detects violation and auto-corrects:
```sql
-- RIGHT: Artist → Album → Track (respects FK relationships)
SELECT Artist.Name, COUNT(Track.TrackId)
FROM Artist
JOIN Album ON Artist.ArtistId = Album.ArtistId    -- ✓ FK: Artist.ArtistId → Album.ArtistId
JOIN Track ON Album.AlbumId = Track.AlbumId      -- ✓ FK: Album.AlbumId → Track.AlbumId
GROUP BY Artist.Name
```

## Architecture

### 1. Schema Graph (`tools/schema_graph.py`)

**Data Structures:**
- `FKEdge`: Single FK relationship (from_table.from_col → to_table.to_col)
- `JoinPath`: Ordered sequence of tables + FK edges representing valid path
- `SchemaGraph`: Directed graph with forward + reverse adjacency lists

**Key Methods:**
```python
# Build graph from database
graph = SchemaGraph.from_database(DATABASE_PATH)

# Find shortest FK path (BFS, max 3 hops)
path = graph.get_fk_path("Artist", "Track")
# Returns: Artist → Album → Track

# Validate JOIN condition
is_valid, error = graph.validate_join_condition("Artist.ArtistId = Track.AlbumId")
# Returns: (False, "Invalid JOIN: not a direct FK relationship...")

# Suggest correct path
suggestion = graph.suggest_correct_joins("Artist", "Track")
# Returns: "Multi-hop path required: Artist → Album → Track\nJOIN conditions needed:\n..."

# Extract all JOINs from SQL
joins = graph.get_all_joins_in_sql(sql_query)
# Returns: ["Artist.ArtistId = Track.AlbumId", ...]
```

**Algorithm:**
- Bidirectional BFS (FKs work both ways)
- Finds shortest path between any two tables (max 3 hops)
- Returns intermediate tables needed for valid JOINs

### 2. SafetyValidator Enhancement (`orchestrator/batch_optimized_orchestrator.py`)

**Integration:**
```python
def __init__(self):
    # Build schema graph once at startup
    self.schema_graph = SchemaGraph.from_database(DATABASE_PATH)

def _deterministic_safety_validation(self, state):
    # Existing checks: forbidden keywords, LIMIT, SELECT *
    
    # NEW: FK JOIN validation
    join_conditions = self.schema_graph.get_all_joins_in_sql(sql)
    
    for join_cond in join_conditions:
        is_valid, error_msg = self.schema_graph.validate_join_condition(join_cond)
        
        if not is_valid:
            fk_violations.append(error_msg)
            
            # Extract tables and suggest correct path
            suggestion = self.schema_graph.suggest_correct_joins(table1, table2)
            fk_violations.append(f"Suggestion: {suggestion}")
    
    state.fk_violations = fk_violations  # Store separately for self-correction
```

**New State Field:**
```python
class BatchPipelineState:
    fk_violations: List[str] = field(default_factory=list)  # FK-specific violations
```

### 3. Self-Correction Enhancement

**Updated Prompt:**
```python
def _batch_3_self_correction(self, state):
    if state.fk_violations:
        error_context = f"FK SCHEMA VIOLATION: {'; '.join(state.fk_violations)}"
    
    prompt = f"""
    CRITICAL: If the error mentions FK (foreign key) violations:
    - The JOIN condition violates the database schema's foreign key relationships
    - You MUST use the suggested FK path provided in the error message
    - Example: If joining Artist to Track, you need intermediate table Album:
      WRONG: Artist.ArtistId = Track.AlbumId (violates FK)
      RIGHT: Artist JOIN Album ON Artist.ArtistId = Album.ArtistId 
             JOIN Track ON Album.AlbumId = Track.AlbumId
    
    ERROR: {error_context}
    SCHEMA: {state.schema_context}
    """
```

**Enhanced Trace:**
```python
if state.fk_violations:
    trace_summary = f"FK CORRECTION (Retry {state.retry_count + 1}): {state.correction_analysis}"
else:
    trace_summary = f"Retry {state.retry_count + 1}: {state.correction_analysis}"
```

### 4. Execution Flow

**Normal Flow (Valid FK):**
```
BATCH 2: SQL Generation
  ↓
SafetyValidator: ✓ APPROVED (FK valid)
  ↓
SQLExecutor: Execute query
  ↓
BATCH 4: Response
```

**FK Violation Flow (Auto-Correction):**
```
BATCH 2: SQL Generation (generates invalid JOIN)
  ↓
SafetyValidator: ✗ FK VIOLATION detected
  ↓
BATCH 3: Self-Correction (LLM fixes JOIN using suggested path)
  ↓
SafetyValidator: ✓ APPROVED (corrected SQL has valid FK)
  ↓
SQLExecutor: Execute corrected query
  ↓
BATCH 4: Response
```

**Failure After Max Retries:**
```
BATCH 2: SQL Generation (invalid JOIN)
  ↓
SafetyValidator: ✗ FK VIOLATION
  ↓
BATCH 3: Self-Correction attempt 1 → still invalid
  ↓
BATCH 3: Self-Correction attempt 2 → still invalid
  ↓
ABORT: "FK violations persist after 2 attempts"
```

## Integration Points

### 1. Orchestrator Initialization
```python
class BatchOptimizedOrchestrator:
    def __init__(self):
        self.schema_graph = SchemaGraph.from_database(DATABASE_PATH)
```

### 2. Safety Validation (Before Execution)
```python
state = self._deterministic_safety_validation(state)

if state.fk_violations:
    # Trigger immediate self-correction
    state = self._batch_3_self_correction(state)
```

### 3. Self-Correction Trigger
```python
# NEW: FK violations trigger correction BEFORE execution
if state.fk_violations:
    retry_loop = 0
    while retry_loop <= state.max_retries:
        state = self._batch_3_self_correction(state)
        state = self._deterministic_safety_validation(state)
        
        if state.safety_approved:
            break
```

### 4. Reasoning Trace
```python
state.add_trace("SafetyValidator", 
                f"✗ FK VIOLATION: {len(fk_violations)} invalid JOIN(s)",
                sql)

state.add_trace("SelfCorrectionAgent",
                f"FK CORRECTION (Retry {retry_count}): {analysis}",
                corrected_sql)
```

## Testing

### Unit Test (`test_fk_validation.py`)
```bash
python test_fk_validation.py
```

**Test Cases:**
1. Invalid JOIN detection: Artist.ArtistId = Track.AlbumId → ✗
2. Valid JOIN validation: Album.AlbumId = Track.AlbumId → ✓
3. FK path finding: Artist → Track → suggests Artist → Album → Track
4. JOIN extraction from SQL
5. Multi-hop path construction

### End-to-End Demo (`demo_fk_correction.py`)
```bash
python demo_fk_correction.py
```

**Demo Scenarios:**
1. Multi-hop JOIN correction (Artist → Track)
2. Direct FK validation (Album → Track)
3. Reasoning trace showing FK corrections

## Database Schema (Chinook)

**FK Relationships:**
```
Artist (ArtistId)
  ↓ FK: ArtistId → Album.ArtistId
Album (AlbumId, ArtistId)
  ↓ FK: AlbumId → Track.AlbumId
Track (TrackId, AlbumId, GenreId, MediaTypeId)
  ↓ FK: TrackId → InvoiceLine.TrackId
InvoiceLine (InvoiceLineId, InvoiceId, TrackId)
  ↓ FK: InvoiceId → Invoice.InvoiceId
Invoice (InvoiceId, CustomerId)
  ↓ FK: CustomerId → Customer.CustomerId
Customer (CustomerId, SupportRepId)

Genre (GenreId)
  ↓ FK: GenreId → Track.GenreId

MediaType (MediaTypeId)
  ↓ FK: MediaTypeId → Track.MediaTypeId

Playlist (PlaylistId)
  ↓ FK: PlaylistId → PlaylistTrack.PlaylistId
PlaylistTrack (PlaylistId, TrackId)
  ↓ FK: TrackId → Track.TrackId

Employee (EmployeeId, ReportsTo)
  ↓ FK: EmployeeId → Customer.SupportRepId
  ↓ FK: ReportsTo → Employee.EmployeeId (self-reference)
```

**Multi-Hop Paths:**
- Artist → Track: Artist → Album → Track (2 hops)
- Customer → Track: Customer → Invoice → InvoiceLine → Track (3 hops)
- Genre → Artist: Genre → Track → Album → Artist (3 hops)

## Key Features

✅ **FK Schema Graph**: Bidirectional graph with all FK relationships  
✅ **BFS Pathfinding**: Finds shortest valid path (max 3 hops)  
✅ **JOIN Validation**: Regex-based extraction + validation  
✅ **Auto-Correction**: LLM fixes invalid JOINs using suggested paths  
✅ **Reasoning Trace**: Shows FK corrections transparently  
✅ **Safety Guardrail**: Blocks execution of schema-invalid JOINs  
✅ **Retry Logic**: Up to 2 correction attempts before aborting  

## Limitations

- **Max 3 Hops**: BFS limited to prevent excessive complexity
- **SQLite Only**: Uses SQLite `PRAGMA foreign_key_list()`
- **Simple JOINs**: Regex may not handle complex nested queries
- **No Subqueries**: JOIN extraction doesn't parse subquery JOINs

## Future Enhancements

1. **AST Parsing**: Use SQL parser instead of regex for robust JOIN extraction
2. **Cost-Based Paths**: Prefer shorter paths or avoid certain tables
3. **Join Hints**: Allow LLM to suggest preferred intermediate tables
4. **Performance**: Cache schema graph instead of rebuilding
5. **Multi-DB**: Support PostgreSQL, MySQL FK extraction
6. **Composite Keys**: Handle multi-column FK relationships

## Files Modified

| File | Changes | Lines |
|------|---------|-------|
| `tools/schema_graph.py` | ✅ NEW: Schema graph + FK validation | 461 |
| `orchestrator/batch_optimized_orchestrator.py` | ✅ MODIFIED: Import, init, SafetyValidator, SelfCorrection | ~100 |
| `models/schemas.py` | ✅ MODIFIED: Added `fk_violations` field | 1 |
| `test_fk_validation.py` | ✅ NEW: Unit tests | 84 |
| `demo_fk_correction.py` | ✅ NEW: E2E demo | 100 |

## Status

🟢 **COMPLETE**: FK-safe JOIN validation fully integrated and tested

## Next Steps

1. Run `python demo_fk_correction.py` to see live FK correction
2. Monitor reasoning traces for FK violation patterns
3. Adjust max_retries if LLM needs more attempts
4. Consider adding FK hints to query planning stage
