#!/usr/bin/env python3
"""
Command Line Interface for NL2SQL Multi-Agent System.
Provides a professional, transparent view of the 12-agent pipeline execution.

DESIGN PRINCIPLES:
- Make the multi-agent workflow OBVIOUS (not a black box)
- Show Input → Action → Output → Reasoning per agent
- Clean structure suitable for demos and debugging
- Support both compact (Judge Mode) and verbose modes
- Demo Mode with 5 curated queries
- Comparison Mode to show naive baseline vs multi-agent

MODES:
- Judge Mode (default): Shows only key decision points
- Verbose Mode (--verbose): Shows all 12 agents with full details
- Demo Mode (--demo): Runs 5 preset queries demonstrating capabilities
- Comparison Mode (--compare-naive): Shows naive baseline alongside multi-agent
"""
import sys
import argparse
from typing import Optional
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich import box
from rich.rule import Rule
import time

# Add parent directory to path for imports
sys.path.insert(0, str(__file__).rsplit('\\', 1)[0])

from orchestrator import NL2SQLOrchestrator, run_query
from models import ExecutionStatus, FinalResponse
from baseline import run_naive_query, format_naive_result_for_display, NAIVE_COMPARISON_LABEL

console = Console()


# ============================================================
# DEMO MODE CONFIGURATION
# ============================================================

DEMO_QUERIES = [
    {
        "category": "🔢 Simple Query",
        "query": "How many customers are from Brazil?",
        "description": "Tests basic SELECT COUNT with WHERE clause"
    },
    {
        "category": "📋 Meta Query",
        "query": "What tables exist in this database?",
        "description": "Tests schema introspection (no SQL generated)"
    },
    {
        "category": "🔗 Join + Aggregation",
        "query": "Which 5 artists have the most tracks?",
        "description": "Tests multi-table JOIN with GROUP BY and ORDER BY"
    },
    {
        "category": "❓ Ambiguous Query",
        "query": "Show me recent invoices",
        "description": "Tests clarification agent (resolves 'recent' → 30 days)"
    },
    {
        "category": "🧩 Edge Case",
        "query": "Find customers who have never made a purchase",
        "description": "Tests LEFT JOIN with NULL check (may return empty)"
    }
]

# Key agents to highlight in Judge Mode
KEY_AGENTS = ["IntentAnalyzer", "SchemaExplorer", "QueryPlanner", "SafetyValidator", "ResponseSynthesizer"]


def print_header():
    """Print the application header."""
    header = """
╔═══════════════════════════════════════════════════════════════╗
║         🔍 NL2SQL Multi-Agent System v1.0                     ║
║         Natural Language to SQL with Intelligent Agents       ║
╚═══════════════════════════════════════════════════════════════╝
    """
    console.print(header, style="bold blue")


def print_execution_header(query: str, provider: str = "Groq", max_llm_calls: int = 8):
    """
    Print detailed execution header with query, timestamp, and configuration.
    WHY: Transparency - user knows exactly what's being executed and the constraints.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    console.print("\n" + "─" * 70, style="bold blue")
    console.print("🚀 [bold cyan]NL2SQL Multi-Agent System - Query Execution[/bold cyan]", justify="center")
    console.print("─" * 70 + "\n", style="bold blue")
    
    # Query info box
    info_table = Table.grid(padding=(0, 2))
    info_table.add_column(style="cyan", justify="right")
    info_table.add_column(style="white")
    
    info_table.add_row("📝 Query:", f"[bold]{query}[/bold]")
    info_table.add_row("🕐 Timestamp:", timestamp)
    info_table.add_row("🤖 LLM Provider:", f"[green]{provider}[/green]")
    info_table.add_row("📊 LLM Budget:", f"[yellow]{max_llm_calls} calls max[/yellow]")
    info_table.add_row("🔧 Architecture:", "[magenta]12-agent pipeline with batching[/magenta]")
    
    console.print(Panel(info_table, border_style="blue", padding=(1, 2)))
    console.print()


def print_workflow_stage(stage_name: str, agents: list, verbose: bool = False):
    """
    Print a workflow stage header with agents involved.
    WHY: Shows pipeline progression - not a monolithic black box.
    """
    console.print(f"\n[bold yellow]{'─' * 70}[/bold yellow]")
    console.print(f"[bold yellow]Stage: {stage_name}[/bold yellow]")
    console.print(f"[dim]Agents: {', '.join(agents)}[/dim]")
    console.print(f"[bold yellow]{'─' * 70}[/bold yellow]\n")


def print_agent_status(agent_name: str, status: str, detail: str = ""):
    """
    Print real-time agent execution status.
    WHY: Live feedback during execution - user sees what's happening.
    
    Status types: RUNNING, DONE, SKIPPED, RETRY, ERROR
    """
    icons = {
        "RUNNING": "▶",
        "DONE": "✓",
        "SKIPPED": "⏭",
        "RETRY": "🔄",
        "ERROR": "✗"
    }
    
    colors = {
        "RUNNING": "yellow",
        "DONE": "green",
        "SKIPPED": "dim",
        "RETRY": "cyan",
        "ERROR": "red"
    }
    
    icon = icons.get(status, "•")
    color = colors.get(status, "white")
    
    status_text = f"  {icon} {agent_name:<25} [{color}][{status}][/{color}]"
    if detail:
        status_text += f"  [dim]{detail}[/dim]"
    
    console.print(status_text)


def print_step_detail(step_num: int, agent_name: str, action_data: dict, verbose: bool = True):
    """
    Print detailed breakdown of a single agent step.
    WHY: Full transparency - shows Input/Action/Output/Reasoning for each agent.
    
    Format:
    ------------------------------------------------
    Step 3: QueryPlanner
    ------------------------------------------------
    INPUT: ...
    ACTION: ...
    OUTPUT: ...
    REASONING: ...
    """
    if not verbose:
        return  # Skip detailed output in compact mode
    
    console.print(f"\n[bold cyan]{'─' * 70}[/bold cyan]")
    console.print(f"[bold cyan]Step {step_num}: {agent_name}[/bold cyan]")
    console.print(f"[bold cyan]{'─' * 70}[/bold cyan]\n")
    
    # Extract fields with fallbacks
    input_text = action_data.get('input_summary') or action_data.get('input') or "N/A"
    action_text = action_data.get('action') or action_data.get('summary') or "Processing step"
    output_text = action_data.get('output_summary') or action_data.get('output') or action_data.get('detail') or "Completed"
    reasoning_text = action_data.get('reasoning') or None
    
    # INPUT section
    console.print("[bold green]INPUT:[/bold green]")
    console.print(f"  {input_text}\n")
    
    # ACTION section
    console.print("[bold yellow]ACTION:[/bold yellow]")
    console.print(f"  {action_text}\n")
    
    # OUTPUT section
    console.print("[bold blue]OUTPUT:[/bold blue]")
    console.print(f"  {output_text}\n")
    
    # REASONING section
    console.print("[bold magenta]REASONING:[/bold magenta]")
    if reasoning_text:
        console.print(f"  {reasoning_text}")
    else:
        console.print("  [dim]Deterministic step (no LLM reasoning)[/dim]")
    
    console.print()


def print_compact_trace(response: FinalResponse):
    """
    Print compact reasoning trace - just the workflow overview.
    WHY: Quick summary without overwhelming detail.
    """
    trace = response.reasoning_trace
    
    console.print("\n[bold cyan]🧠 Reasoning Trace (Compact)[/bold cyan]\n")
    
    # Handle both formats
    actions = trace.actions if hasattr(trace, 'actions') else trace
    
    for i, action in enumerate(actions, 1):
        if isinstance(action, dict):
            agent = action.get("agent", "Unknown")
            summary = action.get("action") or action.get("summary", "")
        else:
            agent = action.agent_name
            summary = action.action
        
        # Truncate summary
        summary = summary[:60] + "..." if len(summary) > 60 else summary
        print_agent_status(f"{i}. {agent}", "DONE", summary)
    
    console.print()


def print_judge_trace(response: FinalResponse):
    """
    Print Judge Mode trace - only key decision points with highlights.
    WHY: Judges need to quickly see the important parts without information overload.
    
    Shows only: IntentAnalyzer, SchemaExplorer, QueryPlanner, SafetyValidator, ResponseSynthesizer
    """
    trace = response.reasoning_trace
    actions = trace.actions if hasattr(trace, 'actions') else trace
    
    console.print(f"\n[bold cyan]{'═' * 70}[/bold cyan]")
    console.print("[bold cyan]🎯 KEY DECISION POINTS (Judge Mode)[/bold cyan]", justify="center")
    console.print(f"[bold cyan]{'═' * 70}[/bold cyan]\n")
    console.print("[dim]Showing 5 key agents. Use --verbose for full 12-agent trace.[/dim]\n")
    
    step_num = 1
    for action in actions:
        if isinstance(action, dict):
            agent_name = action.get("agent", "Unknown")
            action_data = action
        else:
            agent_name = action.agent_name
            action_data = {
                'input_summary': action.input_summary,
                'action': action.action,
                'output_summary': action.output_summary,
                'reasoning': action.reasoning
            }
        
        # Only show key agents
        if agent_name in KEY_AGENTS:
            # Print highlighted header
            console.print(f"[bold yellow]⭐ Step {step_num}: {agent_name}[/bold yellow]")
            
            # Show output summary only (concise)
            output = action_data.get('output_summary') or action_data.get('output') or "Completed"
            output = output[:150] + "..." if len(output) > 150 else output
            console.print(f"   [green]→ {output}[/green]\n")
            
            step_num += 1
    
    console.print(f"[dim]{'─' * 70}[/dim]")
    console.print(f"[dim]Total agents executed: {len(actions)} | Key agents shown: {step_num - 1}[/dim]\n")


def print_naive_comparison(naive_result, multiagent_response: FinalResponse):
    """
    Print side-by-side comparison of naive baseline vs multi-agent system.
    
    WHY: Demonstrates the value of multi-agent reasoning by showing
    where naive approaches fail.
    """
    console.print(f"\n[bold yellow]{'═' * 70}[/bold yellow]")
    console.print("[bold yellow]⚖️  COMPARISON: Naive Baseline vs Multi-Agent System[/bold yellow]", justify="center")
    console.print(f"[bold yellow]{'═' * 70}[/bold yellow]\n")
    
    # Get naive display data
    naive_display = format_naive_result_for_display(naive_result)
    
    # ===== NAIVE BASELINE SECTION =====
    console.print(f"[bold red]{'─' * 70}[/bold red]")
    console.print("[bold red]❌ NAIVE BASELINE[/bold red]")
    console.print(f"[dim]{NAIVE_COMPARISON_LABEL}[/dim]\n")
    
    # Status
    status_style = "green" if naive_display['is_success'] else "red"
    console.print(f"  [bold]Status:[/bold] [{status_style}]{naive_display['status_label']}[/{status_style}]")
    
    # SQL
    console.print(f"\n  [bold]Generated SQL:[/bold]")
    if naive_display['sql'] and naive_display['sql'] != "No SQL generated":
        console.print(Syntax(naive_display['sql'], "sql", theme="monokai"))
    else:
        console.print("  [red]Failed to generate SQL[/red]")
    
    # Error (if any)
    if naive_display['error']:
        console.print(f"\n  [bold red]Error:[/bold red] {naive_display['error']}")
    
    # Results summary
    if naive_display['is_success']:
        console.print(f"\n  [bold]Results:[/bold] {naive_display['row_count']} rows returned")
        if naive_display['data_preview']:
            # Show first 3 rows as table
            table = Table(box=box.SIMPLE, show_header=True)
            for col in naive_display['columns'][:5]:
                table.add_column(col, style="dim")
            for row in naive_display['data_preview'][:3]:
                table.add_row(*[str(row.get(col, ''))[:20] for col in naive_display['columns'][:5]])
            console.print(table)
    
    console.print()
    
    # ===== MULTI-AGENT SECTION =====
    console.print(f"[bold green]{'─' * 70}[/bold green]")
    console.print("[bold green]✅ MULTI-AGENT SYSTEM[/bold green]")
    console.print(f"[dim]12 agents • Schema reasoning • Self-correcting[/dim]\n")
    
    # Status
    status = multiagent_response.reasoning_trace.final_status
    ma_status_style = "green" if status == ExecutionStatus.SUCCESS else "red"
    console.print(f"  [bold]Status:[/bold] [{ma_status_style}]{status.value.upper()}[/{ma_status_style}]")
    
    # SQL
    console.print(f"\n  [bold]Generated SQL:[/bold]")
    if multiagent_response.sql:
        console.print(Syntax(multiagent_response.sql, "sql", theme="monokai"))
    else:
        console.print("  [dim]No SQL needed (meta-query)[/dim]")
    
    # Answer
    console.print(f"\n  [bold]Answer:[/bold]")
    answer = multiagent_response.answer[:300] if multiagent_response.answer else "No answer"
    console.print(f"  [green]{answer}[/green]")
    
    # Results summary
    if multiagent_response.data:
        console.print(f"\n  [bold]Results:[/bold] {len(multiagent_response.data)} rows returned")
    
    console.print(f"\n[bold yellow]{'═' * 70}[/bold yellow]\n")


def print_reasoning_trace(response: FinalResponse, verbose: bool = False, judge_mode: bool = True):
    """
    Display the full reasoning trace with per-step details.
    WHY: Complete transparency into the multi-agent decision-making process.
    
    Modes:
    - judge_mode=True, verbose=False: Show only key agents (default)
    - judge_mode=False, verbose=False: Compact trace of all agents
    - verbose=True: Full Input/Action/Output/Reasoning for all agents
    """
    if verbose:
        # Verbose mode: show full Input/Action/Output/Reasoning per step
        trace = response.reasoning_trace
        actions = trace.actions if hasattr(trace, 'actions') else trace
        
        console.print(f"\n[bold cyan]{'═' * 70}[/bold cyan]")
        console.print("[bold cyan]📋 DETAILED EXECUTION TRACE (All 12 Agents)[/bold cyan]", justify="center")
        console.print(f"[bold cyan]{'═' * 70}[/bold cyan]\n")
        
        for i, action in enumerate(actions, 1):
            if isinstance(action, dict):
                action_data = action
                agent_name = action.get("agent", "Unknown")
            else:
                action_data = {
                    'input_summary': action.input_summary,
                    'action': action.action,
                    'output_summary': action.output_summary,
                    'reasoning': action.reasoning
                }
                agent_name = action.agent_name
            
            print_step_detail(i, agent_name, action_data, verbose=True)
    elif judge_mode:
        # Judge mode: show only key decision points
        print_judge_trace(response)
    else:
        # Compact mode: just show agent execution order
        print_compact_trace(response)


def print_sql_section(response: FinalResponse):
    """
    Display the generated SQL with syntax highlighting.
    WHY: Shows the actual query - key output for validation.
    """
    console.print(f"\n[bold cyan]{'═' * 70}[/bold cyan]")
    console.print("[bold cyan]📝 GENERATED SQL[/bold cyan]", justify="center")
    console.print(f"[bold cyan]{'═' * 70}[/bold cyan]\n")
    
    # Show SQL with syntax highlighting
    sql = response.sql_used if response.sql_used and response.sql_used != "N/A" else "No SQL generated (meta-query or error)"
    
    if sql != "No SQL generated (meta-query or error)":
        syntax = Syntax(sql, "sql", theme="monokai", line_numbers=True)
        console.print(syntax)
    else:
        console.print(f"  [dim]{sql}[/dim]")
    
    console.print()


def print_execution_result(response: FinalResponse):
    """
    Display execution results with status and metrics.
    WHY: Shows whether the query succeeded and what data was returned.
    """
    console.print(f"\n[bold cyan]{'═' * 70}[/bold cyan]")
    console.print("[bold cyan]⚡ EXECUTION RESULT[/bold cyan]", justify="center")
    console.print(f"[bold cyan]{'═' * 70}[/bold cyan]\n")
    
    # Determine status
    trace = response.reasoning_trace
    if hasattr(trace, 'final_status'):
        status = trace.final_status
    elif hasattr(response, 'status'):
        status = response.status
    else:
        status = ExecutionStatus.SUCCESS
    
    # Status with icon
    status_icons = {
        ExecutionStatus.SUCCESS: ("✅", "green"),
        ExecutionStatus.EMPTY: ("📭", "yellow"),
        ExecutionStatus.ERROR: ("❌", "red"),
        ExecutionStatus.VALIDATION_FAILED: ("⚠️", "yellow"),
        ExecutionStatus.BLOCKED: ("🚫", "red")
    }
    
    icon, color = status_icons.get(status, ("❓", "white"))
    
    result_table = Table.grid(padding=(0, 2))
    result_table.add_column(style="cyan", justify="right")
    result_table.add_column()
    
    result_table.add_row("Status:", f"[{color}]{icon} {status.value.upper()}[/{color}]")
    result_table.add_row("Rows returned:", f"[bold]{response.row_count}[/bold]")
    
    # Show retry info if applicable
    if hasattr(trace, 'correction_attempts') and trace.correction_attempts > 0:
        result_table.add_row("Self-corrections:", f"[yellow]{trace.correction_attempts}[/yellow]")
    
    console.print(result_table)
    console.print()


def print_final_answer(response: FinalResponse):
    """
    Display the human-readable final answer.
    WHY: The actual answer to the user's question - most important output.
    """
    console.print(f"\n[bold green]{'═' * 70}[/bold green]")
    console.print("[bold green]💬 FINAL ANSWER[/bold green]", justify="center")
    console.print(f"[bold green]{'═' * 70}[/bold green]\n")
    
    console.print(Panel(
        response.answer,
        border_style="green",
        padding=(1, 2),
        title="[bold]Response[/bold]",
        title_align="left"
    ))
    
    # Show warnings if any
    if response.warnings:
        console.print("\n[yellow]⚠️  Warnings:[/yellow]")
        for warning in response.warnings:
            console.print(f"  • {warning}")
    
    console.print()


def print_metrics_summary(response: FinalResponse):
    """
    Display compact system metrics.
    WHY: Shows performance and resource usage - important for quota-aware systems.
    """
    console.print(f"\n[bold blue]{'═' * 70}[/bold blue]")
    console.print("[bold blue]📊 SYSTEM METRICS[/bold blue]", justify="center")
    console.print(f"[bold blue]{'═' * 70}[/bold blue]\n")
    
    trace = response.reasoning_trace
    
    # Extract metrics
    if hasattr(trace, 'total_time_ms'):
        total_time = trace.total_time_ms
    elif hasattr(response, 'execution_metrics'):
        total_time = response.execution_metrics.get('total_time_ms', 0)
    else:
        total_time = 0
    
    # LLM calls
    if hasattr(response, 'execution_metrics'):
        llm_calls = response.execution_metrics.get('llm_calls', 'N/A')
        llm_budget = response.execution_metrics.get('llm_budget', 'N/A')
    else:
        llm_calls = len(trace.actions) if hasattr(trace, 'actions') else 'N/A'
        llm_budget = 8
    
    # Retries
    retries = trace.correction_attempts if hasattr(trace, 'correction_attempts') else 0
    
    # Status
    if hasattr(trace, 'final_status'):
        status = trace.final_status.value if hasattr(trace.final_status, 'value') else str(trace.final_status)
    else:
        status = 'unknown'
    
    # Build metrics table
    metrics = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    metrics.add_column(style="cyan", justify="right")
    metrics.add_column(style="white")
    
    metrics.add_row("⏱️  Total time:", f"[bold green]{total_time:.0f} ms[/bold green]")
    metrics.add_row("🧠 LLM calls used:", f"[bold yellow]{llm_calls} / {llm_budget}[/bold yellow]")
    metrics.add_row("🔄 Self-corrections:", f"[bold cyan]{retries}[/bold cyan]")
    metrics.add_row("📈 Final status:", f"[bold magenta]{status.upper()}[/bold magenta]")
    
    console.print(metrics)
    console.print(f"\n[bold blue]{'═' * 70}[/bold blue]\n")


def interactive_mode(orchestrator: NL2SQLOrchestrator, verbose: bool = False, judge_mode: bool = True, compare_naive: bool = False):
    """
    Run in interactive mode with continuous query input.
    WHY: Allows exploration without restarting - good for demos.
    """
    print_header()
    
    mode_text = "Judge Mode (key agents)" if judge_mode else "Full Mode (all agents)"
    compare_text = " + Naive Comparison" if compare_naive else ""
    console.print(f"[bold]Interactive Mode | {mode_text}{compare_text}[/bold]")
    console.print("[dim]Type your questions in natural language. Type 'exit' or 'quit' to stop.[/dim]\n")
    console.print("[dim]Example queries:[/dim]")
    console.print("  • How many customers are from Brazil?")
    console.print("  • What tables exist in this database?")
    console.print("  • Show me the top 5 artists with the most tracks")
    console.print("")
    
    while True:
        try:
            # Get user input
            console.print("[bold cyan]" + "─" * 70 + "[/bold cyan]")
            query = console.input("[bold yellow]Your question: [/bold yellow]")
            
            if query.lower() in ['exit', 'quit', 'q']:
                console.print("\n[bold green]Thank you for using NL2SQL! Goodbye! 👋[/bold green]")
                break
            
            if not query.strip():
                console.print("[yellow]Please enter a question.[/yellow]")
                continue
            
            # Print execution header
            print_execution_header(query, provider="Gemini/Groq (auto-fallback)", max_llm_calls=8)
            
            naive_result = None
            
            # Run naive baseline if comparison mode is enabled
            if compare_naive:
                console.print("[bold yellow]⚡ Running naive baseline...[/bold yellow]")
                naive_result = run_naive_query(query)
            
            # Process the query with a spinner
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True
            ) as progress:
                progress.add_task(description="Processing query through 12-agent pipeline...", total=None)
                response = orchestrator.process_query(query)
            
            # Show comparison if enabled
            if compare_naive and naive_result:
                print_naive_comparison(naive_result, response)
            
            # Display results
            print_reasoning_trace(response, verbose=verbose, judge_mode=judge_mode)
            print_sql_section(response)
            print_execution_result(response)
            print_final_answer(response)
            print_metrics_summary(response)
            
        except KeyboardInterrupt:
            console.print("\n\n[bold green]Interrupted. Goodbye! 👋[/bold green]")
            break
        except Exception as e:
            error_msg = str(e).lower()
            if "quota" in error_msg or "rate limit" in error_msg:
                console.print(f"\n[yellow]⚠️ Provider Quota Exceeded[/yellow]")
                console.print("[dim]The system will automatically switch to fallback provider on next query.[/dim]")
            else:
                console.print(f"[bold red]Error: {str(e)}[/bold red]")
            console.print("[dim]Please try again with a different query.[/dim]")


def single_query_mode(query: str, verbose: bool = False, judge_mode: bool = True, compare_naive: bool = False):
    """
    Process a single query and display results.
    WHY: Quick testing and scripting - ideal for CI/CD or batch processing.
    """
    print_header()
    
    # Print execution header with configuration
    print_execution_header(query, provider="Gemini/Groq (auto-fallback)", max_llm_calls=8)
    
    # Process query
    try:
        naive_result = None
        
        # Run naive baseline first if comparison mode is enabled
        if compare_naive:
            console.print("[bold yellow]⚡ Running naive baseline (single LLM call)...[/bold yellow]")
            naive_result = run_naive_query(query)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            progress.add_task(description="Processing query through 12-agent pipeline...", total=None)
            response = run_query(query, verbose=False)  # Backend verbose off, CLI verbose controls output
        
        # Display comparison if enabled
        if compare_naive and naive_result:
            print_naive_comparison(naive_result, response)
        
        # Display full results
        print_reasoning_trace(response, verbose=verbose, judge_mode=judge_mode)
        print_sql_section(response)
        print_execution_result(response)
        print_final_answer(response)
        print_metrics_summary(response)
        
    except Exception as e:
        error_msg = str(e).lower()
        if "quota" in error_msg or "rate limit" in error_msg:
            console.print(f"\n[yellow]⚠️ Provider Quota Exceeded[/yellow]")
            console.print("[dim]Primary provider (Gemini) quota exhausted. System switching to fallback (Groq).[/dim]")
            console.print("[dim]Please wait a moment and try again.[/dim]")
        else:
            console.print(f"[bold red]Error: {str(e)}[/bold red]")


def demo_mode(verbose: bool = False, judge_mode: bool = True, compare_naive: bool = False):
    """
    Run demonstration with 5 curated queries.
    WHY: Perfect for rehearsing presentations and showing system capabilities.
    
    Queries cover:
    1. Simple query - basic aggregation
    2. Meta-query - schema introspection
    3. Join + aggregation - multi-table operations
    4. Ambiguous query - clarification handling
    5. Edge case - empty result handling
    """
    print_header()
    
    comparison_text = " + Naive Comparison" if compare_naive else ""
    console.print(Panel(
        f"[bold magenta]🎮 DEMO MODE - 5 Curated Queries{comparison_text}[/bold magenta]\n\n"
        "This demonstrates the 12-agent pipeline across different query types.\n"
        "Each query tests a different capability of the system.\n\n"
        "[dim]Press Enter between queries to continue.[/dim]",
        border_style="magenta",
        padding=(1, 2)
    ))
    
    # Rate limit tracking
    queries_run = 0
    start_time = time.time()
    
    orchestrator = NL2SQLOrchestrator(verbose=False)
    
    for i, demo in enumerate(DEMO_QUERIES, 1):
        # Demo separator
        console.print(f"\n[bold blue]{'═' * 70}[/bold blue]")
        console.print(Panel(
            f"[bold yellow]DEMO {i}/{len(DEMO_QUERIES)}[/bold yellow]\n\n"
            f"[bold]{demo['category']}[/bold]\n"
            f"[cyan]Query:[/cyan] {demo['query']}\n"
            f"[dim]{demo['description']}[/dim]",
            border_style="yellow",
            padding=(0, 2)
        ))
        
        # Rate limit check - wait if needed
        queries_run += 1
        if queries_run > 3:
            elapsed = time.time() - start_time
            if elapsed < 60:
                wait_time = int(60 - elapsed) + 5
                console.print(f"\n[yellow]⏳ Rate limit protection: waiting {wait_time}s before next query...[/yellow]")
                time.sleep(wait_time)
                start_time = time.time()
                queries_run = 1
        
        print_execution_header(demo['query'], provider="Gemini/Groq (auto-fallback)", max_llm_calls=8)
        
        try:
            naive_result = None
            
            # Run naive baseline if comparison mode is enabled
            if compare_naive:
                console.print("[bold yellow]⚡ Running naive baseline...[/bold yellow]")
                naive_result = run_naive_query(demo['query'])
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True
            ) as progress:
                progress.add_task(description="Processing through 12-agent pipeline...", total=None)
                response = orchestrator.process_query(demo['query'])
            
            # Show comparison if enabled
            if compare_naive and naive_result:
                print_naive_comparison(naive_result, response)
            
            # Output based on mode
            print_reasoning_trace(response, verbose=verbose, judge_mode=judge_mode)
            print_sql_section(response)
            print_final_answer(response)
            print_metrics_summary(response)
            
            # Success indicator
            console.print(f"[bold green]✅ Demo {i} complete![/bold green]")
            
        except Exception as e:
            error_msg = str(e).lower()
            if "quota" in error_msg or "rate limit" in error_msg:
                console.print(f"\n[yellow]⚠️ Provider quota exceeded. Waiting 30s before retry...[/yellow]")
                time.sleep(30)
                try:
                    response = orchestrator.process_query(demo['query'])
                    print_reasoning_trace(response, verbose=verbose, judge_mode=judge_mode)
                    print_sql_section(response)
                    print_final_answer(response)
                    print_metrics_summary(response)
                except Exception as e2:
                    console.print(f"[red]Error after retry: {str(e2)}[/red]")
            else:
                console.print(f"[red]Error: {str(e)}[/red]")
        
        # Pause between demos (except last one)
        if i < len(DEMO_QUERIES):
            console.print(f"\n[dim]Press Enter to continue to Demo {i+1}/{len(DEMO_QUERIES)}...[/dim]")
            input()
    
    # Demo summary
    console.print(f"\n[bold green]{'═' * 70}[/bold green]")
    console.print(Panel(
        "[bold green]🎉 DEMO COMPLETE![/bold green]\n\n"
        f"Demonstrated {len(DEMO_QUERIES)} query types:\n"
        "• Simple aggregation\n"
        "• Meta/schema queries\n"
        "• Join + aggregation\n"
        "• Ambiguous query handling\n"
        "• Edge case (empty results)\n\n"
        "[dim]Thank you for watching![/dim]",
        border_style="green",
        padding=(1, 2)
    ))


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="NL2SQL Multi-Agent System - Convert natural language to SQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py                              # Interactive mode (Judge Mode)
  python cli.py -q "How many customers?"     # Single query (Judge Mode)
  python cli.py -q "..." --verbose           # Single query (Full trace)
  python cli.py -q "..." --full              # Single query (All agents, compact)
  python cli.py --demo                       # Run 5 demo queries
  python cli.py --demo --verbose             # Demo with full traces
  python cli.py -q "..." --compare-naive     # Compare with naive baseline

Modes:
  Judge Mode (default): Shows only 5 key agents - cleaner for presentations
  Full Mode (--full):   Shows all 12 agents in compact format
  Verbose (--verbose):  Shows all 12 agents with Input/Action/Output/Reasoning
  Comparison (--compare-naive): Shows naive baseline alongside multi-agent
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
        help="Run demonstration with 5 curated queries"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output (show full Input/Action/Output/Reasoning per agent)"
    )
    
    parser.add_argument(
        "--full",
        action="store_true",
        help="Show all 12 agents (not just key agents). Use with --verbose for full details."
    )
    
    parser.add_argument(
        "--compare-naive",
        action="store_true",
        dest="compare_naive",
        help="Compare multi-agent system with naive single-shot baseline"
    )
    
    args = parser.parse_args()
    
    # Determine judge_mode (opposite of --full)
    judge_mode = not args.full
    
    try:
        if args.demo:
            demo_mode(verbose=args.verbose, judge_mode=judge_mode, compare_naive=args.compare_naive)
        elif args.query:
            single_query_mode(args.query, verbose=args.verbose, judge_mode=judge_mode, compare_naive=args.compare_naive)
        else:
            orchestrator = NL2SQLOrchestrator(verbose=False)
            interactive_mode(orchestrator, verbose=args.verbose, judge_mode=judge_mode, compare_naive=args.compare_naive)
            
    except Exception as e:
        console.print(f"[bold red]Fatal error: {str(e)}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
