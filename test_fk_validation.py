"""
Test FK-safe JOIN validation system.

This script tests the schema graph's ability to:
1. Detect invalid JOIN conditions that violate FK relationships
2. Suggest correct FK paths for multi-hop relationships
3. Validate that direct FK relationships work
"""

from tools.schema_graph import SchemaGraph
from config import DATABASE_PATH

def test_schema_graph():
    """Test the schema graph construction and FK validation."""
    
    print("="*60)
    print("FK-SAFE JOIN VALIDATION TEST")
    print("="*60)
    
    # Build schema graph
    print("\n1. Building schema graph from database...")
    graph = SchemaGraph.from_database(DATABASE_PATH)
    
    print(f"   ✓ Graph built with {len(graph.all_tables)} tables")
    print(f"   ✓ Tables: {', '.join(sorted(graph.all_tables))}")
    print(f"   ✓ FK edges: {len(graph.edges)}")
    
    # Test case 1: INVALID JOIN (Artist → Track directly)
    print("\n2. Testing INVALID JOIN: Artist.ArtistId = Track.AlbumId")
    invalid_join = "Artist.ArtistId = Track.AlbumId"
    is_valid, error_msg = graph.validate_join_condition(invalid_join)
    
    if not is_valid:
        print(f"   ✓ CORRECTLY DETECTED as invalid")
        print(f"   ✗ Error: {error_msg}")
    else:
        print(f"   ✗ FAILED: Should have detected as invalid!")
    
    # Test case 2: Get correct path (Artist → Track)
    print("\n3. Finding correct FK path: Artist → Track")
    suggestion = graph.suggest_correct_joins("Artist", "Track")
    print(f"   ✓ Suggestion: {suggestion}")
    
    # Test case 3: VALID JOIN (Album → Track directly)
    print("\n4. Testing VALID JOIN: Album.AlbumId = Track.AlbumId")
    valid_join = "Album.AlbumId = Track.AlbumId"
    is_valid, error_msg = graph.validate_join_condition(valid_join)
    
    if is_valid:
        print(f"   ✓ CORRECTLY VALIDATED as valid")
    else:
        print(f"   ✗ FAILED: Should have validated!")
        print(f"   Error: {error_msg}")
    
    # Test case 4: Extract JOINs from SQL
    print("\n5. Testing JOIN extraction from SQL...")
    test_sql = """
    SELECT Artist.Name, Track.Name 
    FROM Artist 
    JOIN Track ON Artist.ArtistId = Track.AlbumId
    LIMIT 10
    """
    joins = graph.get_all_joins_in_sql(test_sql)
    print(f"   ✓ Extracted {len(joins)} JOIN condition(s)")
    for join in joins:
        print(f"     - {join}")
    
    # Test case 5: Complex multi-hop path
    print("\n6. Testing FK path finding...")
    path = graph.get_fk_path("Artist", "Track")
    if path:
        print(f"   ✓ Found path with {len(path.tables)} tables:")
        print(f"     Tables: {' → '.join(path.tables)}")
        for edge in path.edges:
            print(f"     FK: {edge.from_table}.{edge.from_column} → {edge.to_table}.{edge.to_column}")
    else:
        print(f"   ✗ No path found (unexpected)")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)


if __name__ == "__main__":
    test_schema_graph()
