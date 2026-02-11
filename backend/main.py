"""
ReasonSQL Backend Entry Point

This module provides the main entry point for the backend API.
It can be used for:
- Running the CLI interface
- Starting an API server (future)
- Batch processing queries

Usage:
    python -m backend.main "How many customers are there?"
    python -m backend.main --file queries.txt
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.orchestrator import NL2SQLOrchestrator, run_query
from backend.models import FinalResponse, ExecutionStatus


def process_single_query(query: str, verbose: bool = True) -> FinalResponse:
    """
    Process a single natural language query.
    
    Args:
        query: Natural language question
        verbose: Whether to print progress
        
    Returns:
        FinalResponse with answer, SQL, and reasoning trace
    """
    import asyncio
    return asyncio.run(run_query(query, verbose=verbose))


def main():
    """Main entry point for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="ReasonSQL - Multi-Agent NL2SQL System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m backend.main "How many customers are there?"
  python -m backend.main "What tables exist in the database?"
  python -m backend.main --quiet "Show top 5 artists by track count"
        """
    )
    
    parser.add_argument(
        "query",
        nargs="?",
        help="Natural language query to process"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress verbose output"
    )
    parser.add_argument(
        "--file", "-f",
        type=str,
        help="File containing queries (one per line)"
    )
    
    args = parser.parse_args()
    
    if args.file:
        # Process file of queries
        with open(args.file, 'r') as f:
            queries = [line.strip() for line in f if line.strip()]
        
        for i, query in enumerate(queries, 1):
            print(f"\n{'='*60}")
            print(f"Query {i}/{len(queries)}: {query}")
            print('='*60)
            response = process_single_query(query, verbose=not args.quiet)
            print(f"\nAnswer: {response.answer}")
            if response.sql_used:
                print(f"SQL: {response.sql_used}")
    
    elif args.query:
        # Process single query
        response = process_single_query(args.query, verbose=not args.quiet)
        
        print("\n" + "="*60)
        print("FINAL ANSWER")
        print("="*60)
        print(response.answer)
        
        if response.sql_used and response.sql_used != "N/A":
            print(f"\nSQL Used:\n{response.sql_used}")
        
        print(f"\nStatus: {response.reasoning_trace.final_status.value}")
        print(f"Time: {response.reasoning_trace.total_time_ms:.0f}ms")
        if response.row_count:
            print(f"Rows: {response.row_count}")
    
    else:
        parser.print_help()
        print("\nError: Please provide a query or use --file")
        sys.exit(1)


if __name__ == "__main__":
    main()
