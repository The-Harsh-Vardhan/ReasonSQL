"""
Schema Graph for FK-Safe JOIN Validation

PURPOSE:
========
This module builds a directed graph of foreign-key relationships
and provides utilities to validate that SQL JOIN conditions
respect the actual database schema.

WHY THIS EXISTS:
================
To prevent bugs where the LLM generates syntactically valid SQL
with schema-invalid JOINs, such as:
  Artist.ArtistId = Track.AlbumId  ❌ WRONG

The correct path requires an intermediate table:
  Artist.ArtistId = Album.ArtistId 
  AND Album.AlbumId = Track.AlbumId ✅ CORRECT

USAGE:
======
    graph = SchemaGraph.from_database(db_path)
    
    # Check if JOIN is valid
    is_valid, error = graph.validate_join("Artist", "ArtistId", "Track", "AlbumId")
    
    # Get correct FK path
    path = graph.get_fk_path("Artist", "Track")
    # Returns: ["Artist → Album → Track"]
"""

import sqlite3
import re
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from collections import defaultdict, deque


@dataclass
class FKEdge:
    """A single foreign-key relationship (directed edge)."""
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    
    def __str__(self) -> str:
        return f"{self.from_table}.{self.from_column} → {self.to_table}.{self.to_column}"
    
    def __hash__(self) -> int:
        return hash((self.from_table, self.from_column, self.to_table, self.to_column))


@dataclass
class JoinPath:
    """A valid JOIN path through the schema graph."""
    tables: List[str]  # Ordered list of tables
    edges: List[FKEdge]  # FK relationships along the path
    
    def __str__(self) -> str:
        return " → ".join(self.tables)
    
    def get_join_conditions(self) -> List[str]:
        """Get SQL JOIN conditions for this path."""
        return [f"{e.from_table}.{e.from_column} = {e.to_table}.{e.to_column}" 
                for e in self.edges]


class SchemaGraph:
    """
    Directed graph representing foreign-key relationships in a database.
    
    Nodes: Table names
    Edges: FK relationships (from_table.from_col → to_table.to_col)
    """
    
    def __init__(self):
        self.edges: List[FKEdge] = []
        self.adjacency: Dict[str, List[FKEdge]] = defaultdict(list)
        self.reverse_adjacency: Dict[str, List[FKEdge]] = defaultdict(list)
        self.all_tables: Set[str] = set()
    
    @classmethod
    def from_database(cls, db_path: str) -> 'SchemaGraph':
        """
        Build schema graph by extracting FK relationships from database.
        
        Args:
            db_path: Path to SQLite database
            
        Returns:
            SchemaGraph instance with all FK relationships loaded
        """
        graph = cls()
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                if table.startswith('sqlite_'):
                    continue
                
                graph.all_tables.add(table)
                
                # Extract FK relationships
                cursor.execute(f"PRAGMA foreign_key_list({table});")
                fk_data = cursor.fetchall()
                
                for fk in fk_data:
                    # fk format: (id, seq, table, from, to, on_update, on_delete, match)
                    edge = FKEdge(
                        from_table=table,
                        from_column=fk[3],
                        to_table=fk[2],
                        to_column=fk[4]
                    )
                    graph.add_edge(edge)
            
            conn.close()
            
        except Exception as e:
            print(f"Warning: Failed to build schema graph: {e}")
        
        return graph
    
    def add_edge(self, edge: FKEdge):
        """Add a FK relationship to the graph."""
        self.edges.append(edge)
        self.adjacency[edge.from_table].append(edge)
        self.reverse_adjacency[edge.to_table].append(edge)
        self.all_tables.add(edge.from_table)
        self.all_tables.add(edge.to_table)
    
    def get_direct_edge(self, from_table: str, to_table: str) -> Optional[FKEdge]:
        """
        Get direct FK edge between two tables (if it exists).
        
        Returns:
            FKEdge if direct relationship exists, None otherwise
        """
        # Check forward direction
        for edge in self.adjacency.get(from_table, []):
            if edge.to_table == to_table:
                return edge
        
        # Check reverse direction
        for edge in self.adjacency.get(to_table, []):
            if edge.to_table == from_table:
                # Return reversed edge
                return FKEdge(
                    from_table=to_table,
                    from_column=edge.to_column,
                    to_table=from_table,
                    to_column=edge.from_column
                )
        
        return None
    
    def get_fk_path(self, start_table: str, end_table: str, max_hops: int = 3) -> Optional[JoinPath]:
        """
        Find shortest FK path between two tables using BFS.
        
        Args:
            start_table: Starting table name
            end_table: Target table name
            max_hops: Maximum number of intermediate tables allowed
            
        Returns:
            JoinPath if valid path exists, None otherwise
            
        Example:
            get_fk_path("Artist", "Track") 
            → JoinPath(tables=["Artist", "Album", "Track"], edges=[...])
        """
        if start_table == end_table:
            return JoinPath(tables=[start_table], edges=[])
        
        # Check for direct edge first
        direct_edge = self.get_direct_edge(start_table, end_table)
        if direct_edge:
            return JoinPath(
                tables=[direct_edge.from_table, direct_edge.to_table],
                edges=[direct_edge]
            )
        
        # BFS to find shortest path
        queue = deque([(start_table, [])])  # (current_table, path_edges)
        visited = {start_table}
        
        while queue:
            current, path = queue.popleft()
            
            if len(path) >= max_hops:
                continue
            
            # Explore neighbors (both directions)
            neighbors = []
            
            # Forward edges
            for edge in self.adjacency.get(current, []):
                neighbors.append((edge.to_table, edge))
            
            # Reverse edges (we can join in either direction)
            for edge in self.reverse_adjacency.get(current, []):
                # Create reversed edge
                rev_edge = FKEdge(
                    from_table=current,
                    from_column=edge.to_column,
                    to_table=edge.from_table,
                    to_column=edge.from_column
                )
                neighbors.append((edge.from_table, rev_edge))
            
            for next_table, edge in neighbors:
                if next_table in visited:
                    continue
                
                new_path = path + [edge]
                
                if next_table == end_table:
                    # Found path!
                    tables = [e.from_table for e in new_path] + [end_table]
                    return JoinPath(tables=tables, edges=new_path)
                
                visited.add(next_table)
                queue.append((next_table, new_path))
        
        return None  # No path found
    
    def validate_join_condition(self, join_str: str) -> Tuple[bool, str]:
        """
        Validate a JOIN condition string against schema.
        
        Args:
            join_str: SQL JOIN condition like "Artist.ArtistId = Album.ArtistId"
            
        Returns:
            (is_valid, error_message)
            
        Examples:
            validate_join_condition("Artist.ArtistId = Album.ArtistId")
            → (True, "")
            
            validate_join_condition("Artist.ArtistId = Track.AlbumId")
            → (False, "Invalid JOIN: Artist.ArtistId and Track.AlbumId are not related by FK")
        """
        # Parse JOIN condition
        # Pattern: table1.col1 = table2.col2
        pattern = r'(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)'
        match = re.search(pattern, join_str, re.IGNORECASE)
        
        if not match:
            return False, f"Could not parse JOIN condition: {join_str}"
        
        table1, col1, table2, col2 = match.groups()
        
        # Check if this matches any FK edge (either direction)
        for edge in self.edges:
            if (edge.from_table == table1 and edge.from_column == col1 and
                edge.to_table == table2 and edge.to_column == col2):
                return True, ""
            
            if (edge.from_table == table2 and edge.from_column == col2 and
                edge.to_table == table1 and edge.to_column == col1):
                return True, ""
        
        # Not a direct FK - check if path exists
        path = self.get_fk_path(table1, table2)
        
        if path and len(path.edges) > 1:
            return False, (
                f"Invalid JOIN: {table1}.{col1} = {table2}.{col2} is not a direct FK relationship. "
                f"Correct path requires intermediate tables: {path}"
            )
        
        return False, (
            f"Invalid JOIN: {table1}.{col1} and {table2}.{col2} are not related by any FK path. "
            f"No schema relationship exists between {table1} and {table2}."
        )
    
    def get_all_joins_in_sql(self, sql: str) -> List[str]:
        """
        Extract all JOIN conditions from a SQL query.
        
        Args:
            sql: SQL query string
            
        Returns:
            List of JOIN condition strings
            
        Example:
            sql = "SELECT * FROM Artist JOIN Album ON Artist.ArtistId = Album.ArtistId"
            → ["Artist.ArtistId = Album.ArtistId"]
        """
        joins = []
        
        # Pattern for JOIN ... ON conditions
        # Matches: JOIN table ON table1.col1 = table2.col2
        pattern = r'JOIN\s+\w+\s+ON\s+(\w+\.\w+\s*=\s*\w+\.\w+)'
        matches = re.finditer(pattern, sql, re.IGNORECASE)
        
        for match in matches:
            joins.append(match.group(1))
        
        # Also check WHERE clause for join conditions
        where_pattern = r'WHERE\s+.*?(\w+\.\w+\s*=\s*\w+\.\w+)'
        where_matches = re.finditer(where_pattern, sql, re.IGNORECASE)
        
        for match in where_matches:
            condition = match.group(1)
            # Only include if it looks like a join (two different tables)
            parts = condition.split('=')
            if len(parts) == 2:
                left_table = parts[0].strip().split('.')[0]
                right_table = parts[1].strip().split('.')[0]
                if left_table != right_table:
                    joins.append(condition)
        
        return joins
    
    def suggest_correct_joins(self, table1: str, table2: str) -> str:
        """
        Suggest correct JOIN conditions for two tables.
        
        Args:
            table1: First table name
            table2: Second table name
            
        Returns:
            String with suggested JOIN conditions
        """
        path = self.get_fk_path(table1, table2)
        
        if not path:
            return f"No FK relationship found between {table1} and {table2}"
        
        if len(path.edges) == 0:
            return f"{table1} is the same as {table2}"
        
        if len(path.edges) == 1:
            edge = path.edges[0]
            return f"Direct FK: {edge.from_table}.{edge.from_column} = {edge.to_table}.{edge.to_column}"
        
        # Multi-hop path
        suggestions = [f"Multi-hop path required: {path}"]
        suggestions.append("JOIN conditions needed:")
        for edge in path.edges:
            suggestions.append(f"  {edge.from_table}.{edge.from_column} = {edge.to_table}.{edge.to_column}")
        
        return "\n".join(suggestions)
    
    def __str__(self) -> str:
        """String representation of the schema graph."""
        lines = [f"SchemaGraph with {len(self.all_tables)} tables and {len(self.edges)} FK relationships:"]
        
        for table in sorted(self.all_tables):
            edges_from = self.adjacency.get(table, [])
            if edges_from:
                lines.append(f"\n{table}:")
                for edge in edges_from:
                    lines.append(f"  → {edge.to_table} ({edge.from_column} → {edge.to_column})")
        
        return "\n".join(lines)
