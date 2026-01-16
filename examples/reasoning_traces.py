"""
Example reasoning traces demonstrating the deterministic orchestrator behavior.

This file shows expected outputs for:
1. An ambiguous query that triggers clarification
2. A failed query that self-corrects
3. A successful complex query
4. A meta-query about the database

These examples illustrate:
- How the state machine routes based on agent outputs
- How structured outputs enable deterministic flow control
- How the reasoning trace captures every decision
"""
import json

# ============================================================
# EXAMPLE 1: AMBIGUOUS QUERY
# ============================================================

AMBIGUOUS_QUERY_TRACE = {
    "query": "Show me recent orders from top customers",
    "flow": [
        "START → INTENT_ANALYSIS",
        "INTENT_ANALYSIS → CLARIFICATION (ambiguous terms detected)",
        "CLARIFICATION → SCHEMA_EXPLORATION (resolved with assumptions)",
        "SCHEMA_EXPLORATION → QUERY_PLANNING",
        "QUERY_PLANNING → SQL_GENERATION",
        "SQL_GENERATION → SAFETY_VALIDATION",
        "SAFETY_VALIDATION → SQL_EXECUTION (APPROVED)",
        "SQL_EXECUTION → RESULT_VALIDATION",
        "RESULT_VALIDATION → RESPONSE_SYNTHESIS",
        "RESPONSE_SYNTHESIS → END"
    ],
    "trace": [
        {
            "step": 1,
            "agent": "IntentAnalyzer",
            "action": "Classified query intent",
            "decision": "Intent=AMBIGUOUS, Confidence=0.7",
            "output": {
                "status": "ambiguous",
                "intent": "DATA_QUERY",  # Would be data, but terms are unclear
                "ambiguous_terms": ["recent", "top"],
                "reason": "Query contains undefined temporal ('recent') and ranking ('top') terms"
            }
        },
        {
            "step": 2,
            "agent": "ClarificationAgent",
            "action": "Resolved ambiguous terms",
            "decision": "Resolved: ['recent', 'top']",
            "output": {
                "status": "ok",
                "resolved_terms": {
                    "recent": "last 30 days",
                    "top": "top 10 by total purchase amount"
                },
                "assumptions_made": [
                    "Interpreting 'recent' as last 30 days (from today)",
                    "Interpreting 'top customers' as top 10 by total purchase amount"
                ],
                "clarification_questions": [],
                "refined_query": "Show orders from the last 30 days from the top 10 customers by total purchase amount"
            }
        },
        {
            "step": 3,
            "agent": "SchemaExplorer",
            "action": "Explored database schema",
            "decision": "Found 11 tables",
            "output": {
                "status": "ok",
                "tables": ["Customer", "Invoice", "InvoiceLine", "Track", "Album", "Artist", "..."],
                "relevant_tables_for_query": ["Customer", "Invoice"],
                "schema_summary": "Invoice table has CustomerId FK to Customer. Invoice.InvoiceDate for temporal filtering."
            }
        },
        {
            "step": 4,
            "agent": "QueryPlanner",
            "action": "Created query plan",
            "decision": "Base: Invoice, Joins: 1, Limit: 100",
            "output": {
                "status": "ok",
                "base_table": "Invoice",
                "select_columns": [
                    "Customer.CustomerId",
                    "Customer.FirstName",
                    "Customer.LastName", 
                    "Invoice.InvoiceId",
                    "Invoice.InvoiceDate",
                    "Invoice.Total"
                ],
                "joins": [{"table": "Customer", "on": "Invoice.CustomerId = Customer.CustomerId"}],
                "filters": [
                    {"column": "Invoice.InvoiceDate", "operator": ">=", "value": "date('now', '-30 days')"},
                    {"column": "Customer.CustomerId", "operator": "IN", "value": "(subquery for top 10)"}
                ],
                "limit": 100,
                "reasoning": "Using subquery to identify top 10 customers, then filtering recent invoices"
            }
        },
        {
            "step": 5,
            "agent": "SQLGenerator",
            "action": "Generated SQL query",
            "decision": "Uses CTE: True, Tables: 2",
            "output": {
                "status": "ok",
                "sql": """WITH TopCustomers AS (
    SELECT CustomerId
    FROM Invoice
    GROUP BY CustomerId
    ORDER BY SUM(Total) DESC
    LIMIT 10
)
SELECT 
    c.CustomerId,
    c.FirstName,
    c.LastName,
    i.InvoiceId,
    i.InvoiceDate,
    i.Total
FROM Invoice i
JOIN Customer c ON i.CustomerId = c.CustomerId
WHERE c.CustomerId IN (SELECT CustomerId FROM TopCustomers)
  AND i.InvoiceDate >= date('now', '-30 days')
ORDER BY i.InvoiceDate DESC
LIMIT 100;"""
            }
        },
        {
            "step": 6,
            "agent": "SafetyValidator",
            "action": "Validated SQL safety",
            "decision": "Decision: APPROVED",
            "output": {
                "status": "ok",
                "decision": "APPROVED",
                "has_limit": True,
                "has_select_star": False,
                "is_read_only": True,
                "violations": []
            }
        },
        {
            "step": 7,
            "agent": "SQLExecutor",
            "action": "Executed SQL",
            "decision": "Status: ok, Rows: 23",
            "output": {
                "status": "ok",
                "row_count": 23,
                "column_names": ["CustomerId", "FirstName", "LastName", "InvoiceId", "InvoiceDate", "Total"],
                "execution_time_ms": 45.2
            }
        },
        {
            "step": 8,
            "agent": "ResultValidator",
            "action": "Validated result sanity",
            "decision": "Valid: True, Matches intent: True",
            "output": {
                "status": "ok",
                "is_valid": True,
                "anomalies_detected": [],
                "matches_intent": True,
                "confidence": 0.95
            }
        },
        {
            "step": 9,
            "agent": "ResponseSynthesizer",
            "action": "Created human-readable response",
            "decision": "Status: ok",
            "output": {
                "status": "ok",
                "answer": "I found 23 recent orders from top customers. The top customers by total purchase amount include Luis Rojas (3 orders), Fynn Zimmermann (2 orders), and Helena Holý (2 orders). Most orders are from the last 2 weeks, with purchases ranging from $0.99 to $13.86."
            }
        }
    ],
    "final_response": {
        "answer": "I found 23 recent orders from top customers...",
        "sql_used": "WITH TopCustomers AS (...) SELECT ...",
        "row_count": 23,
        "warnings": ["Assumptions made: ['Interpreting recent as last 30 days', 'Interpreting top customers as top 10 by total purchase amount']"],
        "total_time_ms": 2340
    }
}


# ============================================================
# EXAMPLE 2: FAILED QUERY WITH SELF-CORRECTION
# ============================================================

SELF_CORRECTION_TRACE = {
    "query": "Show me all tracks by artists named 'Beatles'",
    "flow": [
        "START → INTENT_ANALYSIS",
        "INTENT_ANALYSIS → SCHEMA_EXPLORATION",
        "SCHEMA_EXPLORATION → QUERY_PLANNING",
        "QUERY_PLANNING → SQL_GENERATION",
        "SQL_GENERATION → SAFETY_VALIDATION",
        "SAFETY_VALIDATION → SQL_EXECUTION (APPROVED)",
        "SQL_EXECUTION → SELF_CORRECTION (empty result)",
        "SELF_CORRECTION → QUERY_PLANNING (retry 1)",
        "QUERY_PLANNING → SQL_GENERATION",
        "SQL_GENERATION → SAFETY_VALIDATION",
        "SAFETY_VALIDATION → SQL_EXECUTION (APPROVED)",
        "SQL_EXECUTION → RESULT_VALIDATION",
        "RESULT_VALIDATION → RESPONSE_SYNTHESIS",
        "RESPONSE_SYNTHESIS → END"
    ],
    "trace": [
        {
            "step": 1,
            "agent": "IntentAnalyzer",
            "action": "Classified query intent",
            "decision": "Intent=DATA_QUERY, Confidence=0.9",
            "output": {
                "status": "ok",
                "intent": "DATA_QUERY",
                "relevant_tables": ["Track", "Album", "Artist"],
                "is_complex": False
            }
        },
        {
            "step": 2,
            "agent": "SchemaExplorer",
            "action": "Explored database schema",
            "decision": "Found Artist → Album → Track relationship",
            "output": {
                "status": "ok",
                "relevant_tables_for_query": ["Track", "Album", "Artist"],
                "schema_summary": "Track.AlbumId → Album.AlbumId, Album.ArtistId → Artist.ArtistId"
            }
        },
        {
            "step": 3,
            "agent": "QueryPlanner",
            "action": "Created query plan",
            "decision": "Base: Track, Joins: 2, Filter: Artist.Name = 'Beatles'",
            "output": {
                "status": "ok",
                "base_table": "Track",
                "filters": [{"column": "Artist.Name", "operator": "=", "value": "Beatles"}],
                "reasoning": "Exact match on artist name"
            }
        },
        {
            "step": 4,
            "agent": "SQLGenerator",
            "action": "Generated SQL query",
            "output": {
                "sql": """SELECT t.TrackId, t.Name as TrackName, a.Title as AlbumTitle, ar.Name as ArtistName
FROM Track t
JOIN Album a ON t.AlbumId = a.AlbumId
JOIN Artist ar ON a.ArtistId = ar.ArtistId
WHERE ar.Name = 'Beatles'
LIMIT 100;"""
            }
        },
        {
            "step": 5,
            "agent": "SafetyValidator",
            "decision": "APPROVED",
            "output": {"status": "ok", "decision": "APPROVED"}
        },
        {
            "step": 6,
            "agent": "SQLExecutor",
            "action": "Executed SQL",
            "decision": "Status: ok, Rows: 0",
            "output": {
                "status": "ok",
                "row_count": 0,
                "is_empty": True,
                "error_message": None
            }
        },
        {
            "step": 7,
            "agent": "SelfCorrection",
            "action": "Analyzed failure and proposed fix",
            "decision": "Should retry: True, Skip to: PLANNER",
            "output": {
                "status": "retry",
                "original_error": "Empty result set",
                "diagnosis": "Exact match 'Beatles' returned 0 rows. The artist name in the database might be different (e.g., 'The Beatles', 'Beatles, The', or similar). Also, Beatles might not be in the Chinook database which primarily has rock and metal artists.",
                "correction_strategy": "Use LIKE with wildcard to search for partial matches: '%Beatles%'",
                "should_retry": True,
                "skip_to_step": "PLANNER"
            }
        },
        {
            "step": 8,
            "agent": "QueryPlanner",
            "action": "Created query plan (retry 1)",
            "decision": "Using LIKE '%Beatles%' instead of exact match",
            "output": {
                "status": "ok",
                "filters": [{"column": "Artist.Name", "operator": "LIKE", "value": "%Beatles%"}],
                "reasoning": "Changed to fuzzy match based on self-correction feedback"
            }
        },
        {
            "step": 9,
            "agent": "SQLGenerator",
            "action": "Generated SQL query",
            "output": {
                "sql": """SELECT t.TrackId, t.Name as TrackName, a.Title as AlbumTitle, ar.Name as ArtistName
FROM Track t
JOIN Album a ON t.AlbumId = a.AlbumId
JOIN Artist ar ON a.ArtistId = ar.ArtistId
WHERE ar.Name LIKE '%Beatles%'
LIMIT 100;"""
            }
        },
        {
            "step": 10,
            "agent": "SafetyValidator",
            "decision": "APPROVED",
            "output": {"status": "ok", "decision": "APPROVED"}
        },
        {
            "step": 11,
            "agent": "SQLExecutor",
            "action": "Executed SQL",
            "decision": "Status: ok, Rows: 0",
            "note": "Still 0 because Beatles isn't in Chinook",
            "output": {
                "status": "ok",
                "row_count": 0,
                "is_empty": True
            }
        },
        {
            "step": 12,
            "agent": "ResultValidator",
            "action": "Validated result sanity",
            "output": {
                "status": "ok",
                "is_valid": True,
                "anomalies_detected": [],
                "warnings": ["Query returned 0 rows - artist may not exist in database"],
                "matches_intent": True
            }
        },
        {
            "step": 13,
            "agent": "ResponseSynthesizer",
            "action": "Created human-readable response",
            "output": {
                "answer": "I couldn't find any tracks by artists matching 'Beatles' in the database. The Chinook database primarily contains rock, metal, and various other genres but doesn't appear to include Beatles tracks. You might want to search for other artists or check what artists are available with 'What artists are in the database?'"
            }
        }
    ],
    "final_response": {
        "answer": "I couldn't find any tracks by artists matching 'Beatles'...",
        "sql_used": "SELECT ... WHERE ar.Name LIKE '%Beatles%' LIMIT 100",
        "row_count": 0,
        "warnings": ["Required 1 correction attempts"],
        "total_time_ms": 3210
    }
}


# ============================================================
# EXAMPLE 3: SAFETY GATE REJECTION
# ============================================================

SAFETY_BLOCKED_TRACE = {
    "query": "Delete all tracks with zero plays",
    "flow": [
        "START → INTENT_ANALYSIS",
        "INTENT_ANALYSIS → SCHEMA_EXPLORATION",
        "SCHEMA_EXPLORATION → QUERY_PLANNING",
        "QUERY_PLANNING → SQL_GENERATION",
        "SQL_GENERATION → SAFETY_VALIDATION",
        "SAFETY_VALIDATION → BLOCKED (REJECTED)"
    ],
    "trace": [
        {
            "step": 1,
            "agent": "IntentAnalyzer",
            "decision": "Intent=DATA_QUERY",
            "note": "Intent analyzer doesn't catch the destructive nature - that's SafetyValidator's job"
        },
        {
            "step": 2,
            "agent": "SchemaExplorer",
            "decision": "Found Track table"
        },
        {
            "step": 3,
            "agent": "QueryPlanner",
            "decision": "Created DELETE plan",
            "note": "Planner follows user intent but SafetyValidator will catch this"
        },
        {
            "step": 4,
            "agent": "SQLGenerator",
            "output": {
                "sql": "DELETE FROM Track WHERE PlayCount = 0;"
            }
        },
        {
            "step": 5,
            "agent": "SafetyValidator",
            "action": "Validated SQL safety",
            "decision": "Decision: REJECTED",
            "output": {
                "status": "blocked",
                "decision": "REJECTED",
                "is_read_only": False,
                "forbidden_keywords_found": ["DELETE"],
                "violations": [
                    "Forbidden keyword 'DELETE' detected - only read operations allowed",
                    "Missing LIMIT clause"
                ],
                "suggested_fixes": [
                    "This system only supports read-only SELECT queries",
                    "If you want to identify tracks with zero plays, try: 'Show me tracks with zero plays'"
                ]
            }
        }
    ],
    "final_response": {
        "answer": "Query blocked by safety validator: ['Forbidden keyword DELETE detected - only read operations allowed']. This system only supports read-only SELECT queries. If you want to identify tracks with zero plays, try asking 'Show me tracks with zero plays' instead.",
        "sql_used": "N/A (blocked)",
        "row_count": 0,
        "warnings": [],
        "total_time_ms": 890
    }
}


# ============================================================
# EXAMPLE 4: META QUERY (SHORT CIRCUIT)
# ============================================================

META_QUERY_TRACE = {
    "query": "What tables are in the database?",
    "flow": [
        "START → INTENT_ANALYSIS",
        "INTENT_ANALYSIS → SCHEMA_EXPLORATION (META_QUERY detected)",
        "SCHEMA_EXPLORATION → RESPONSE_SYNTHESIS (short circuit for META)",
        "RESPONSE_SYNTHESIS → END"
    ],
    "trace": [
        {
            "step": 1,
            "agent": "IntentAnalyzer",
            "action": "Classified query intent",
            "decision": "Intent=META_QUERY, Confidence=0.95",
            "output": {
                "status": "ok",
                "intent": "META_QUERY",
                "reason": "User is asking about database structure, not data"
            }
        },
        {
            "step": 2,
            "agent": "SchemaExplorer",
            "action": "Explored database schema",
            "decision": "Found 11 tables (META_QUERY mode)",
            "output": {
                "status": "ok",
                "tables": [
                    {"name": "Album", "columns": ["AlbumId", "Title", "ArtistId"], "row_count": 347},
                    {"name": "Artist", "columns": ["ArtistId", "Name"], "row_count": 275},
                    {"name": "Customer", "columns": ["CustomerId", "FirstName", "LastName", "..."], "row_count": 59},
                    {"name": "Employee", "columns": ["EmployeeId", "FirstName", "LastName", "..."], "row_count": 8},
                    {"name": "Genre", "columns": ["GenreId", "Name"], "row_count": 25},
                    {"name": "Invoice", "columns": ["InvoiceId", "CustomerId", "InvoiceDate", "Total"], "row_count": 412},
                    {"name": "InvoiceLine", "columns": ["InvoiceLineId", "InvoiceId", "TrackId", "..."], "row_count": 2240},
                    {"name": "MediaType", "columns": ["MediaTypeId", "Name"], "row_count": 5},
                    {"name": "Playlist", "columns": ["PlaylistId", "Name"], "row_count": 18},
                    {"name": "PlaylistTrack", "columns": ["PlaylistId", "TrackId"], "row_count": 8715},
                    {"name": "Track", "columns": ["TrackId", "Name", "AlbumId", "..."], "row_count": 3503}
                ],
                "schema_summary": "11 tables total: Album, Artist, Customer, Employee, Genre, Invoice, InvoiceLine, MediaType, Playlist, PlaylistTrack, Track"
            }
        },
        {
            "step": 3,
            "agent": "ResponseSynthesizer",
            "action": "Created human-readable response",
            "decision": "Status: ok",
            "output": {
                "answer": """The database contains 11 tables:

1. **Artist** (275 rows) - Music artists
2. **Album** (347 rows) - Albums linked to artists
3. **Track** (3,503 rows) - Individual tracks linked to albums
4. **Genre** (25 rows) - Music genres
5. **MediaType** (5 rows) - Media formats (MP3, AAC, etc.)
6. **Playlist** (18 rows) - Playlists
7. **PlaylistTrack** (8,715 rows) - Tracks in playlists (many-to-many)
8. **Customer** (59 rows) - Customer information
9. **Employee** (8 rows) - Store employees
10. **Invoice** (412 rows) - Customer invoices
11. **InvoiceLine** (2,240 rows) - Line items on invoices

Key relationships:
- Artist → Album → Track (music hierarchy)
- Customer → Invoice → InvoiceLine → Track (purchase hierarchy)
- Playlist ↔ Track (many-to-many via PlaylistTrack)"""
            }
        }
    ],
    "final_response": {
        "answer": "The database contains 11 tables: Artist, Album, Track, Genre, MediaType...",
        "sql_used": "N/A (meta-query - used schema inspection)",
        "row_count": 0,
        "warnings": [],
        "total_time_ms": 450
    }
}


def print_trace(trace_data: dict):
    """Pretty-print a reasoning trace."""
    print(f"\n{'='*70}")
    print(f"QUERY: {trace_data['query']}")
    print(f"{'='*70}")
    
    print("\nFLOW:")
    for step in trace_data['flow']:
        print(f"  {step}")
    
    print("\nDETAILED TRACE:")
    for entry in trace_data['trace']:
        print(f"\n  Step {entry['step']}: {entry['agent']}")
        if 'action' in entry:
            print(f"    Action: {entry['action']}")
        if 'decision' in entry:
            print(f"    Decision: {entry['decision']}")
        if 'output' in entry:
            output = entry['output']
            if isinstance(output, dict):
                for k, v in output.items():
                    if k != 'sql':
                        print(f"    {k}: {v}")
                    else:
                        print(f"    sql: [SQL query - {len(v)} chars]")
        if 'note' in entry:
            print(f"    Note: {entry['note']}")
    
    print(f"\nFINAL RESPONSE:")
    final = trace_data['final_response']
    print(f"  Answer: {final['answer'][:100]}...")
    print(f"  SQL: {final['sql_used'][:50]}...")
    print(f"  Rows: {final['row_count']}")
    print(f"  Time: {final['total_time_ms']}ms")
    if final.get('warnings'):
        print(f"  Warnings: {final['warnings']}")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("EXAMPLE REASONING TRACES")
    print("="*70)
    
    print("\n\n>>> EXAMPLE 1: AMBIGUOUS QUERY <<<")
    print_trace(AMBIGUOUS_QUERY_TRACE)
    
    print("\n\n>>> EXAMPLE 2: SELF-CORRECTION <<<")
    print_trace(SELF_CORRECTION_TRACE)
    
    print("\n\n>>> EXAMPLE 3: SAFETY BLOCKED <<<")
    print_trace(SAFETY_BLOCKED_TRACE)
    
    print("\n\n>>> EXAMPLE 4: META QUERY <<<")
    print_trace(META_QUERY_TRACE)
