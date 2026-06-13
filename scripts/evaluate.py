#!/usr/bin/env python3
"""
ReasonSQL Evaluation Suite — Feature G

Runs a golden test suite against the live API and reports accuracy metrics.
Optionally pushes results to LangSmith as a dataset for tracking regressions.

Usage:
    python scripts/evaluate.py
    python scripts/evaluate.py --api-url https://your-render-url.onrender.com
    python scripts/evaluate.py --no-langsmith  # Skip LangSmith dataset push
    python scripts/evaluate.py --categories count filter join  # Run subset

Requirements:
    pip install httpx langsmith rich

Environment:
    LANGCHAIN_API_KEY - Required for LangSmith push
    LANGCHAIN_PROJECT - LangSmith project name (default: reasonsql-eval)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
    RICH = True
except ImportError:
    RICH = False
    class Console:
        def print(self, *args, **kwargs): print(*args)
    class Progress:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def add_task(self, *a, **kw): return 0
        def advance(self, *a): pass


console = Console()
GOLDEN_CASES = Path(__file__).parent / "golden_cases.json"


# =============================================================================
# EVALUATION LOGIC
# =============================================================================

def check_sql_contains(sql: Optional[str], expected: list[str]) -> bool:
    """Check if generated SQL contains all expected keywords (case-insensitive)."""
    if not sql:
        return False
    sql_upper = sql.upper()
    return all(kw.upper() in sql_upper for kw in expected)


def evaluate_case(case: dict, response: dict) -> dict:
    """Score a single test case against the API response."""
    result = {
        "id": case["id"],
        "category": case["category"],
        "question": case["question"][:60],
        "passed": False,
        "details": [],
        "status": response.get("reasoning_trace", {}).get("final_status", "unknown"),
        "row_count": response.get("row_count", 0),
        "sql": response.get("sql_used", ""),
        "cache_hit": response.get("cache_hit", False),
    }

    checks_passed = 0
    checks_total = 0

    # Check: expected_success
    if "expected_success" in case:
        checks_total += 1
        if response.get("success") == case["expected_success"]:
            checks_passed += 1
            result["details"].append("✅ success flag correct")
        else:
            result["details"].append(f"❌ success: expected {case['expected_success']}, got {response.get('success')}")

    # Check: expected_intent
    if "expected_intent" in case:
        checks_total += 1
        actual_intent = response.get("reasoning_trace", {}).get("final_status")
        expected = case["expected_intent"].lower().replace("_query", "")
        if expected in str(actual_intent).lower() or response.get("is_meta_query"):
            checks_passed += 1
            result["details"].append(f"✅ intent: {actual_intent}")
        else:
            result["details"].append(f"❌ intent: expected {case['expected_intent']}, got {actual_intent}")

    # Check: expected_status
    if "expected_status" in case:
        checks_total += 1
        actual_status = response.get("reasoning_trace", {}).get("final_status", "")
        if actual_status == case["expected_status"]:
            checks_passed += 1
            result["details"].append(f"✅ status: {actual_status}")
        else:
            result["details"].append(f"❌ status: expected {case['expected_status']}, got {actual_status}")

    # Check: expected_sql_contains
    if "expected_sql_contains" in case:
        checks_total += 1
        sql = response.get("sql_used", "")
        if check_sql_contains(sql, case["expected_sql_contains"]):
            checks_passed += 1
            result["details"].append(f"✅ SQL contains {case['expected_sql_contains']}")
        else:
            missing = [k for k in case["expected_sql_contains"] if k.upper() not in (sql or "").upper()]
            result["details"].append(f"❌ SQL missing: {missing}")

    # Check: expected_row_count (exact)
    if "expected_row_count" in case:
        checks_total += 1
        actual = response.get("row_count", 0)
        expected_rc = case["expected_row_count"]
        if actual == expected_rc:
            checks_passed += 1
            result["details"].append(f"✅ row_count: {actual}")
        else:
            result["details"].append(f"❌ row_count: expected {expected_rc}, got {actual}")

    # Check: expected_row_count_min
    if "expected_row_count_min" in case:
        checks_total += 1
        actual = response.get("row_count", 0)
        if actual >= case["expected_row_count_min"]:
            checks_passed += 1
            result["details"].append(f"✅ row_count >= {case['expected_row_count_min']}: {actual}")
        else:
            result["details"].append(f"❌ row_count: expected >={case['expected_row_count_min']}, got {actual}")

    # Default: just check that the API returned success if no specific checks
    if checks_total == 0:
        checks_total = 1
        if response.get("success"):
            checks_passed = 1
            result["details"].append("✅ success (default check)")
        else:
            result["details"].append("❌ query failed")

    result["passed"] = checks_passed == checks_total
    result["score"] = checks_passed / checks_total if checks_total > 0 else 0
    return result


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="ReasonSQL Evaluation Suite")
    parser.add_argument("--api-url", default=os.getenv("API_URL", "http://localhost:8000"),
                        help="Base URL of the ReasonSQL API")
    parser.add_argument("--categories", nargs="*",
                        help="Filter to specific categories (e.g. count filter join)")
    parser.add_argument("--no-langsmith", action="store_true",
                        help="Skip LangSmith dataset creation")
    parser.add_argument("--timeout", type=int, default=60,
                        help="Request timeout in seconds (default: 60)")
    args = parser.parse_args()

    # Load test cases
    with open(GOLDEN_CASES) as f:
        cases = json.load(f)

    if args.categories:
        cases = [c for c in cases if c["category"] in args.categories]
        console.print(f"[yellow]Filtered to {len(cases)} cases: {args.categories}[/yellow]" if RICH else f"Filtered to {len(cases)} cases")

    api_url = args.api_url.rstrip("/")
    console.print(f"\n[bold cyan]ReasonSQL Evaluation Suite[/bold cyan]" if RICH else "\nReasonSQL Evaluation Suite")
    console.print(f"API: {api_url} | Cases: {len(cases)}\n" if RICH else f"API: {api_url} | Cases: {len(cases)}\n")

    results = []
    errors = []

    with httpx.Client(timeout=args.timeout) as client:
        for i, case in enumerate(cases, 1):
            console.print(f"[{i:02d}/{len(cases):02d}] {case['question'][:60]}..." if RICH else f"[{i:02d}/{len(cases):02d}] {case['question'][:60]}...")
            t0 = time.time()
            try:
                resp = client.post(
                    f"{api_url}/query",
                    json={"query": case["question"], "database_id": "default"},
                )
                resp.raise_for_status()
                data = resp.json()
                elapsed = time.time() - t0
                result = evaluate_case(case, data)
                result["elapsed_ms"] = round(elapsed * 1000)
                results.append(result)
                status = "✅" if result["passed"] else "❌"
                console.print(f"   {status} ({result['elapsed_ms']}ms) — {result['details'][0] if result['details'] else 'no checks'}")
            except Exception as exc:
                elapsed = time.time() - t0
                errors.append({"id": case["id"], "question": case["question"], "error": str(exc)})
                results.append({
                    "id": case["id"], "category": case["category"],
                    "question": case["question"][:60],
                    "passed": False, "score": 0,
                    "details": [f"❌ Request error: {exc}"],
                    "elapsed_ms": round(elapsed * 1000),
                })
                console.print(f"   ⚠️  Error: {str(exc)[:80]}")

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    accuracy = passed / total * 100 if total > 0 else 0
    avg_ms = sum(r.get("elapsed_ms", 0) for r in results) / total if total > 0 else 0

    console.print("\n" + "─" * 60)
    console.print(f"[bold]Results:[/bold] {passed}/{total} passed ({accuracy:.1f}% accuracy)" if RICH else f"Results: {passed}/{total} passed ({accuracy:.1f}% accuracy)")
    console.print(f"Average latency: {avg_ms:.0f}ms")

    # Category breakdown
    by_category: dict[str, dict] = {}
    for r in results:
        cat = r["category"]
        if cat not in by_category:
            by_category[cat] = {"passed": 0, "total": 0}
        by_category[cat]["total"] += 1
        if r["passed"]:
            by_category[cat]["passed"] += 1

    console.print("\n[bold]By category:[/bold]" if RICH else "\nBy category:")
    for cat, stats in sorted(by_category.items()):
        pct = stats["passed"] / stats["total"] * 100
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        console.print(f"  {cat:<20} {bar} {stats['passed']}/{stats['total']} ({pct:.0f}%)")

    # LangSmith push
    if not args.no_langsmith and os.getenv("LANGCHAIN_API_KEY"):
        try:
            from langsmith import Client
            ls_client = Client()
            dataset_name = f"reasonsql-chinook-eval-{int(time.time())}"
            dataset = ls_client.create_dataset(
                dataset_name=dataset_name,
                description="ReasonSQL golden test cases for Chinook DB",
            )
            for case in cases:
                ls_client.create_example(
                    inputs={"query": case["question"], "database_id": "default"},
                    outputs={"expected": case},
                    dataset_id=dataset.id,
                )
            console.print(f"\n[green]✅ LangSmith dataset created: {dataset_name}[/green]" if RICH else f"\n✅ LangSmith dataset: {dataset_name}")
        except Exception as exc:
            console.print(f"\n[yellow]LangSmith push failed (non-critical): {exc}[/yellow]" if RICH else f"\nLangSmith push failed: {exc}")

    # Exit code
    sys.exit(0 if accuracy >= 70 else 1)


if __name__ == "__main__":
    main()
