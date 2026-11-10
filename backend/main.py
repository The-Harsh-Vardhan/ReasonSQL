"""
ReasonSQL command-line interface.

    reasonsql ask "How many customers are there?"
    reasonsql ask --file queries.txt --json
    reasonsql serve --port 8000
    reasonsql eval --baseline --report docs/results/eval.md

`python -m backend.main "question"` still works (treated as `ask`).
"""

import argparse
import asyncio
import runpy
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

COMMANDS = {"ask", "serve", "eval"}


async def _ask(question: str):
    """Run one question through the same LangGraph path as POST /query."""
    from configs import MAX_RETRIES
    from backend.graph import get_pipeline
    from backend.api.routers.query import _build_query_response_from_state

    state = {
        "user_query": question,
        "history": [],
        "messages": [],
        "retry_count": 0,
        "max_retries": MAX_RETRIES,
        "reasoning_trace": [],
    }
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    final_state = await get_pipeline().ainvoke(state, config=config)
    return _build_query_response_from_state(final_state)


def _print_response(question: str, r, as_json: bool) -> None:
    if as_json:
        print(r.model_dump_json())
        return
    print(f"\nQ: {question}\n{'=' * 60}\n{r.answer}")
    if r.sql_used:
        print(f"\nSQL:\n{r.sql_used}")
    trace = r.reasoning_trace
    print(f"\nStatus: {trace.final_status.value} | rows: {r.row_count} | "
          f"retries: {trace.correction_attempts} | time: {(trace.total_time_ms or 0):.0f} ms")


def cmd_ask(args) -> int:
    questions = [args.question] if args.question else []
    if args.file:
        questions += [line.strip() for line in Path(args.file).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not questions:
        print("Give a question or --file.", file=sys.stderr)
        return 2
    failed = 0
    for q in questions:
        r = asyncio.run(_ask(q))
        _print_response(q, r, args.json)
        failed += not r.success
    return 1 if failed else 0


def cmd_serve(args) -> int:
    import uvicorn
    uvicorn.run("backend.api.main:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def cmd_eval(args) -> int:
    sys.argv = [str(ROOT / "scripts" / "evaluate.py"), *args.rest]
    try:
        runpy.run_path(sys.argv[0], run_name="__main__")
    except SystemExit as e:
        return int(e.code or 0)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="reasonsql", description="ReasonSQL: natural language to SQL with a LangGraph agent pipeline.")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("ask", help="answer a question against the configured database")
    a.add_argument("question", nargs="?", help="natural language question")
    a.add_argument("--file", "-f", help="text file with one question per line")
    a.add_argument("--json", action="store_true", help="print the full API-shaped response as JSON")
    a.set_defaults(func=cmd_ask)

    s = sub.add_parser("serve", help="start the FastAPI backend")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--reload", action="store_true", help="auto-reload on code changes")
    s.set_defaults(func=cmd_serve)

    e = sub.add_parser("eval", help="run the golden-case evaluation (options pass through to scripts/evaluate.py)",
                       add_help=False)
    e.set_defaults(func=cmd_eval)
    return p


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in COMMANDS and not argv[0].startswith("-"):
        argv.insert(0, "ask")  # backwards compatible: `python -m backend.main "question"`
    parser = build_parser()
    args, rest = parser.parse_known_args(argv)
    if args.command == "eval":
        args.rest = rest  # everything after `eval` goes to scripts/evaluate.py untouched
    elif rest:
        parser.error(f"unrecognized arguments: {' '.join(rest)}")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
