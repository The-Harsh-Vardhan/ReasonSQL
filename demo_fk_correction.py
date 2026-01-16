"""
DEMO: FK-Safe JOIN Correction

This demo shows the system catching and correcting schema-invalid JOINs.

Test Cases:
1. Invalid JOIN: Artist → Track (missing intermediate Album table)
2. Valid JOIN: Album → Track (direct FK relationship)
3. Multi-hop: Customer → Track (requires Customer → Invoice → InvoiceLine → Track)
"""

from orchestrator.batch_optimized_orchestrator import run_query
import json


def demo_fk_correction():
    """Demonstrate FK-safe JOIN validation and correction."""
    
    print("="*80)
    print(" FK-SAFE JOIN VALIDATION DEMO ".center(80, "="))
    print("="*80)
    print()
    
    # Test Case 1: Query that would generate invalid JOIN
    print("TEST CASE 1: Query requiring multi-hop JOIN (Artist → Track)")
    print("-" * 80)
    query = "List top 5 artists by number of tracks"
    print(f"Query: {query}")
    print()
    print("Expected behavior:")
    print("  1. LLM generates: Artist.ArtistId = Track.AlbumId (WRONG)")
    print("  2. SafetyValidator DETECTS FK violation")
    print("  3. SelfCorrection fixes: Artist → Album → Track (RIGHT)")
    print()
    
    result = run_query(query, verbose=True)
    
    print()
    print("RESULT:")
    print(f"  Answer: {result.answer}")
    print(f"  SQL Used: {result.sql_used}")
    print(f"  Row Count: {result.row_count}")
    print(f"  Warnings: {result.warnings}")
    
    # Check if FK correction happened
    trace_summary = []
    for action in result.reasoning_trace.actions:
        if "FK" in action.action or "Correction" in action.agent_name:
            trace_summary.append(f"    - {action.agent_name}: {action.action}")
    
    if trace_summary:
        print()
        print("  FK CORRECTION TRACE:")
        for line in trace_summary:
            print(line)
    
    print()
    print("="*80)
    print()
    
    # Test Case 2: Query with valid direct FK
    print("TEST CASE 2: Query with valid direct FK (Album → Track)")
    print("-" * 80)
    query2 = "How many tracks are in the album 'Appetite for Destruction'?"
    print(f"Query: {query2}")
    print()
    print("Expected behavior:")
    print("  1. LLM generates: Album.AlbumId = Track.AlbumId (CORRECT)")
    print("  2. SafetyValidator APPROVES (direct FK exists)")
    print("  3. NO correction needed")
    print()
    
    result2 = run_query(query2, verbose=True)
    
    print()
    print("RESULT:")
    print(f"  Answer: {result2.answer}")
    print(f"  SQL Used: {result2.sql_used}")
    print(f"  Row Count: {result2.row_count}")
    print(f"  Correction Attempts: {result2.reasoning_trace.correction_attempts}")
    
    print()
    print("="*80)
    print(" DEMO COMPLETE ".center(80, "="))
    print("="*80)


if __name__ == "__main__":
    demo_fk_correction()
