#!/usr/bin/env python3
"""
Command Line Interface for NL2SQL Multi-Agent System.
Provides an interactive terminal experience with colored output and reasoning traces.
"""
import sys
import argparse
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

# Add parent directory to path for imports
sys.path.insert(0, str(__file__).rsplit('\\', 1)[0])

from orchestrator import NL2SQLOrchestrator, run_query
from models import ExecutionStatus, FinalResponse

console = Console()


def print_header():
    """Print the application header."""
    header = """
╔═══════════════════════════════════════════════════════════════╗
║         🔍 NL2SQL Multi-Agent System v1.0                     ║
║         Natural Language to SQL with Intelligent Agents       ║
╚═══════════════════════════════════════════════════════════════╝
    """
    console.print(header, style="bold blue")


def print_reasoning_trace(response: FinalResponse):
    """Display the reasoning trace in a formatted way."""
    trace = response.reasoning_trace
    
    # Handle both old format (ReasoningTrace object) and new format (list of dicts)
    if isinstance(trace, list):
        # New quota-optimized orchestrator format
        table = Table(
            title="🧠 Reasoning Trace",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan"
        )
        table.add_column("", style="dim", width=3)
        table.add_column("Agent", style="green", width=22)
        table.add_column("Action", style="yellow", width=27)
        table.add_column("Output Summary", style="white", width=47)
        
        for i, action in enumerate(trace, 1):
            agent = action.get("agent", "Unknown")[:21]
            act = action.get("action", "")[:26]
            summary = action.get("summary", "")
            if len(summary) > 46:
                summary = summary[:46] + "..."
            table.add_row(str(i), agent, act, summary)
        
        console.print(table)
        
        # Print metrics from execution_metrics
        metrics_data = response.execution_metrics if hasattr(response, 'execution_metrics') else {}
        metrics = Table(title="📊 Execution Metrics", box=box.SIMPLE)
        metrics.add_column("Metric", style="cyan")
        metrics.add_column("Value", style="green")
        metrics.add_row("Total Time", f"{metrics_data.get('total_time_ms', 0):.2f} ms")
        metrics.add_row("LLM Calls", f"{metrics_data.get('llm_calls', 'N/A')} / {metrics_data.get('llm_budget', 'N/A')}")
        metrics.add_row("Retries", str(metrics_data.get('retries', 0)))
        metrics.add_row("Final Status", str(metrics_data.get('status', 'unknown')))
        console.print(metrics)
        
    else:
        # Old deterministic orchestrator format (ReasoningTrace object)
        table = Table(
            title="🧠 Reasoning Trace",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan"
        )
        table.add_column("", style="dim", width=3)
        table.add_column("Agent", style="green", width=22)
        table.add_column("Action", style="yellow", width=27)
        table.add_column("Output Summary", style="white", width=47)
        
        for i, action in enumerate(trace.actions, 1):
            table.add_row(
                str(i),
                action.agent_name[:21],
                action.action[:26],
                action.output_summary[:46] + "..." if len(action.output_summary) > 46 else action.output_summary
            )
        
        console.print(table)
        
        # Print metrics
        metrics = Table(title="📊 Execution Metrics", box=box.SIMPLE)
        metrics.add_column("Metric", style="cyan")
        metrics.add_column("Value", style="green")
        metrics.add_row("Total Time", f"{trace.total_time_ms:.2f} ms")
        metrics.add_row("Correction Attempts", str(trace.correction_attempts))
        metrics.add_row("Final Status", trace.final_status.value if hasattr(trace.final_status, 'value') else str(trace.final_status))
        console.print(metrics)


def print_sql(sql: str):
    """Display the generated SQL with syntax highlighting."""
    console.print("\n📝 [bold cyan]Generated SQL:[/bold cyan]")
    syntax = Syntax(sql, "sql", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, border_style="cyan"))


def print_answer(response: FinalResponse):
    """Display the final answer."""
    status_emoji = {
        ExecutionStatus.SUCCESS: "✅",
        ExecutionStatus.EMPTY: "📭",
        ExecutionStatus.ERROR: "❌",
        ExecutionStatus.VALIDATION_FAILED: "⚠️",
        ExecutionStatus.BLOCKED: "🚫"
    }
    
    # Handle both formats
    if hasattr(response, 'status'):
        status = response.status
    elif hasattr(response, 'reasoning_trace') and hasattr(response.reasoning_trace, 'final_status'):
        status = response.reasoning_trace.final_status
    else:
        status = ExecutionStatus.SUCCESS
    
    emoji = status_emoji.get(status, "❓")
    
    console.print(f"\n{emoji} [bold green]Answer:[/bold green]")
    console.print(Panel(
        Markdown(response.answer),
        border_style="green",
        title="Response"
    ))
    
    if hasattr(response, 'row_count') and response.row_count > 0:
        console.print(f"[dim]Rows returned: {response.row_count}[/dim]")
    
    if response.warnings:
        for warning in response.warnings:
            console.print(f"[yellow]⚠️ Warning: {warning}[/yellow]")


def interactive_mode(orchestrator: NL2SQLOrchestrator):
    """Run in interactive mode with continuous query input."""
    print_header()
    
    console.print("[bold]Type your questions in natural language. Type 'exit' or 'quit' to stop.[/bold]\n")
    console.print("[dim]Example queries:[/dim]")
    console.print("  • How many customers are from Brazil?")
    console.print("  • What tables exist in this database?")
    console.print("  • Show me the top 5 artists with the most tracks")
    console.print("")
    
    while True:
        try:
            # Get user input
            console.print("[bold cyan]───────────────────────────────────────────[/bold cyan]")
            query = console.input("[bold yellow]Your question: [/bold yellow]")
            
            if query.lower() in ['exit', 'quit', 'q']:
                console.print("\n[bold green]Thank you for using NL2SQL! Goodbye! 👋[/bold green]")
                break
            
            if not query.strip():
                console.print("[yellow]Please enter a question.[/yellow]")
                continue
            
            # Process the query with a spinner
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True
            ) as progress:
                progress.add_task(description="Processing your query...", total=None)
                response = orchestrator.process_query(query)
            
            # Display results
            print_reasoning_trace(response)
            print_sql(response.sql_used)
            print_answer(response)
            
            console.print("")
            
        except KeyboardInterrupt:
            console.print("\n\n[bold green]Interrupted. Goodbye! 👋[/bold green]")
            break
        except Exception as e:
            console.print(f"[bold red]Error: {str(e)}[/bold red]")
            console.print("[dim]Please try again with a different query.[/dim]")


def single_query_mode(query: str, verbose: bool = False, show_trace: bool = True):
    """Process a single query and display results."""
    print_header()
    
    console.print(f"[bold]Query:[/bold] {query}\n")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        progress.add_task(description="Processing...", total=None)
        response = run_query(query, verbose=verbose)
    
    if show_trace:
        print_reasoning_trace(response)
    
    print_sql(response.sql_used)
    print_answer(response)


def demo_mode():
    """Run demonstration with sample queries."""
    print_header()
    console.print("[bold magenta]🎮 DEMO MODE - Running sample queries[/bold magenta]\n")
    
    demo_queries = [
        ("Simple", "How many customers are from Brazil?"),
        ("Meta-query", "What tables exist in this database?"),
        ("Moderate", "Which 5 artists have the most tracks?"),
        ("Complex", "Total revenue by country, sorted highest first"),
        ("Ambiguous", "Show me recent orders"),
    ]
    
    orchestrator = NL2SQLOrchestrator(verbose=False)
    
    for category, query in demo_queries:
        console.print(f"\n[bold blue]{'='*60}[/bold blue]")
        console.print(f"[bold yellow]Category: {category}[/bold yellow]")
        console.print(f"[bold]Query: {query}[/bold]\n")
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True
            ) as progress:
                progress.add_task(description="Processing...", total=None)
                response = orchestrator.process_query(query)
            
            print_sql(response.sql_used)
            print_answer(response)
            
            console.print(f"[dim]Time: {response.reasoning_trace.total_time_ms:.2f}ms | "
                         f"Corrections: {response.reasoning_trace.correction_attempts}[/dim]")
            
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
        
        console.print("")


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="NL2SQL Multi-Agent System - Convert natural language to SQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py                          # Interactive mode
  python cli.py -q "How many customers?" # Single query
  python cli.py --demo                   # Run demo queries
  python cli.py -q "..." --verbose       # Verbose output
        """
    )
    
    parser.add_argument(
        "-q", "--query",
        type=str,
        help="Process a single query and exit"
    )
    
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run demonstration with sample queries"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output from agents"
    )
    
    parser.add_argument(
        "--no-trace",
        action="store_true",
        help="Hide the reasoning trace in output"
    )
    
    args = parser.parse_args()
    
    try:
        if args.demo:
            demo_mode()
        elif args.query:
            single_query_mode(
                args.query,
                verbose=args.verbose,
                show_trace=not args.no_trace
            )
        else:
            orchestrator = NL2SQLOrchestrator(verbose=args.verbose)
            interactive_mode(orchestrator)
            
    except Exception as e:
        console.print(f"[bold red]Fatal error: {str(e)}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
