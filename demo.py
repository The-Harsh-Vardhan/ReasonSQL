#!/usr/bin/env python3
"""
Demonstration script for NL2SQL Multi-Agent System.
Shows how the system handles various query complexities and edge cases.

This script demonstrates:
1. Simple queries
2. Meta-queries (schema exploration)
3. Moderate complexity (joins, aggregations)
4. Complex queries requiring reasoning
5. Ambiguous queries requiring clarification
6. Error handling and self-correction
"""
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich import box

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator import NL2SQLOrchestrator
from models import ExecutionStatus

console = Console()


def print_demo_header():
    """Print demo header."""
    console.print("\n")
    console.print(Panel.fit(
        "[bold blue]🎮 NL2SQL Multi-Agent System - Demonstration[/bold blue]\n"
        "[dim]Showcasing intelligent query processing with self-correction[/dim]",
        border_style="blue"
    ))
    console.print("\n")


def print_section(title: str, description: str):
    """Print a section header."""
    console.print(f"\n[bold magenta]{'='*60}[/bold magenta]")
    console.print(f"[bold yellow]{title}[/bold yellow]")
    console.print(f"[dim]{description}[/dim]")
    console.print(f"[bold magenta]{'='*60}[/bold magenta]\n")


def run_demo_query(orchestrator: NL2SQLOrchestrator, query: str, 
                   expected_behavior: str, naive_failure: str):
    """Run a demo query and display results."""
    console.print(f"[bold cyan]Query:[/bold cyan] {query}")
    console.print(f"[dim]Expected: {expected_behavior}[/dim]")
    console.print(f"[dim red]Naive approach fails because: {naive_failure}[/dim red]")
    console.print("")
    
    try:
        response = orchestrator.process_query(query)
        
        # Display SQL
        console.print("[bold green]Generated SQL:[/bold green]")
        if response.sql_used and response.sql_used != "N/A":
            console.print(Syntax(response.sql_used, "sql", theme="monokai"))
        else:
            console.print(f"[dim]{response.sql_used}[/dim]")
        
        # Display answer
        status_emoji = {
            ExecutionStatus.SUCCESS: "✅",
            ExecutionStatus.EMPTY: "📭",
            ExecutionStatus.ERROR: "❌",
            ExecutionStatus.VALIDATION_FAILED: "⚠️"
        }
        emoji = status_emoji.get(response.reasoning_trace.final_status, "❓")
        
        console.print(f"\n{emoji} [bold green]Answer:[/bold green]")
        console.print(Panel(response.answer, border_style="green"))
        
        # Display metrics
        trace = response.reasoning_trace
        console.print(f"[dim]Time: {trace.total_time_ms:.0f}ms | "
                     f"Agents used: {len(trace.actions)} | "
                     f"Corrections: {trace.correction_attempts}[/dim]")
        
        # Show why this succeeded where naive approach fails
        if trace.correction_attempts > 0:
            console.print(f"[bold yellow]✨ Self-correction engaged: "
                         f"Query was fixed after {trace.correction_attempts} attempt(s)[/bold yellow]")
        
        return True
        
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
        return False


def main():
    """Run the full demonstration."""
    print_demo_header()
    
    console.print("[bold]Initializing agents...[/bold]")
    orchestrator = NL2SQLOrchestrator(verbose=False)
    console.print("[green]✓ Agents initialized successfully[/green]\n")
    
    # Demo queries organized by complexity
    demo_cases = [
        {
            "section": "1️⃣ SIMPLE QUERIES",
            "description": "Basic queries that naive approaches might handle, but our system does it safer",
            "queries": [
                {
                    "query": "How many customers are from Brazil?",
                    "expected": "Returns count with proper schema exploration first",
                    "naive_fail": "Might use SELECT * or miss the correct table name"
                },
                {
                    "query": "List all albums by AC/DC",
                    "expected": "Joins Artist and Album tables correctly",
                    "naive_fail": "May not know that ArtistId links these tables"
                }
            ]
        },
        {
            "section": "2️⃣ META-QUERIES (Schema Exploration)",
            "description": "Questions about database structure - naive approaches often ignore these",
            "queries": [
                {
                    "query": "What tables exist in this database?",
                    "expected": "Lists all tables with descriptions",
                    "naive_fail": "Tries to generate SQL instead of inspecting schema"
                },
                {
                    "query": "What columns does the Invoice table have?",
                    "expected": "Shows column names, types, and relationships",
                    "naive_fail": "Generates SELECT query instead of PRAGMA"
                }
            ]
        },
        {
            "section": "3️⃣ MODERATE COMPLEXITY (Joins & Aggregations)",
            "description": "Queries requiring joins and aggregations",
            "queries": [
                {
                    "query": "Which 5 artists have the most tracks?",
                    "expected": "Joins Artist→Album→Track with COUNT and LIMIT",
                    "naive_fail": "May miss one join or forget LIMIT clause"
                },
                {
                    "query": "Total revenue by country, sorted highest first",
                    "expected": "Aggregates Invoice.Total grouped by BillingCountry",
                    "naive_fail": "Might use wrong column or miss ORDER BY"
                }
            ]
        },
        {
            "section": "4️⃣ COMPLEX QUERIES (Reasoning Required)",
            "description": "Queries that require understanding relationships and logic",
            "queries": [
                {
                    "query": "Which customers have never made a purchase?",
                    "expected": "LEFT JOIN Customer-Invoice, filter WHERE Invoice IS NULL",
                    "naive_fail": "Uses INNER JOIN which returns nothing useful"
                },
                {
                    "query": "Are there any genres with no tracks?",
                    "expected": "LEFT JOIN Genre-Track, filter for NULL tracks",
                    "naive_fail": "Misunderstands the negative condition"
                }
            ]
        },
        {
            "section": "5️⃣ AMBIGUOUS QUERIES (Clarification Needed)",
            "description": "Vague queries where our system asks for clarification",
            "queries": [
                {
                    "query": "Show me recent orders",
                    "expected": "Asks for clarification: What timeframe is 'recent'?",
                    "naive_fail": "Makes arbitrary assumption about 'recent'"
                },
                {
                    "query": "Who are our best customers?",
                    "expected": "Asks: By revenue? By frequency? By recent activity?",
                    "naive_fail": "Picks arbitrary metric without asking"
                }
            ]
        }
    ]
    
    success_count = 0
    total_count = 0
    
    for case in demo_cases:
        print_section(case["section"], case["description"])
        
        for q in case["queries"]:
            total_count += 1
            if run_demo_query(
                orchestrator,
                q["query"],
                q["expected"],
                q["naive_fail"]
            ):
                success_count += 1
            console.print("\n")
    
    # Summary
    print_section("📊 DEMO SUMMARY", "Overall results from demonstration")
    
    summary_table = Table(title="Results", box=box.ROUNDED)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")
    summary_table.add_row("Total Queries", str(total_count))
    summary_table.add_row("Successful", str(success_count))
    summary_table.add_row("Success Rate", f"{success_count/total_count*100:.1f}%")
    
    console.print(summary_table)
    
    # Key differentiators
    console.print("\n[bold yellow]🌟 Key Differentiators from Naive Approaches:[/bold yellow]")
    console.print("""
    1. [green]Schema Exploration First[/green] - Always understands database before querying
    2. [green]Intent Classification[/green] - Distinguishes data queries from meta-queries
    3. [green]Safety Constraints[/green] - Never uses SELECT *, always has LIMIT
    4. [green]Self-Correction[/green] - Retries with different strategy if query fails
    5. [green]Clarification[/green] - Asks questions instead of making assumptions
    6. [green]Reasoning Trace[/green] - Transparent decision-making visible to user
    """)
    
    console.print("\n[bold green]Demo complete! ✨[/bold green]\n")


if __name__ == "__main__":
    main()
