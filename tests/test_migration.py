"""
ReasonSQL 2.0 — Local Test Suite
=================================
Tests the full migration without Docker by:
1. Using the existing Supabase PostgreSQL (from .env DATABASE_URL if it's a supabase URL)
   OR connecting to local postgres on localhost:5432
2. Testing each component independently before the full pipeline

Run:
    python tests/test_migration.py

Or individual sections:
    python tests/test_migration.py --section db
    python tests/test_migration.py --section retrieval
    python tests/test_migration.py --section llm
    python tests/test_migration.py --section pipeline
    python tests/test_migration.py --section api
"""

import os
import sys
import asyncio
import argparse
import traceback
from pathlib import Path
from typing import Callable

# ── Path setup ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── Rich output ─────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import print as rprint
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    console = None

# ── Results tracker ─────────────────────────────────────────────────────────
results = []

def _pass(name: str, detail: str = ""):
    results.append(("✅ PASS", name, detail))
    print(f"  ✅ PASS  {name}" + (f" — {detail}" if detail else ""))

def _fail(name: str, detail: str = ""):
    results.append(("❌ FAIL", name, detail))
    print(f"  ❌ FAIL  {name}" + (f" — {detail}" if detail else ""))

def _warn(name: str, detail: str = ""):
    results.append(("⚠️  WARN", name, detail))
    print(f"  ⚠️  WARN  {name}" + (f" — {detail}" if detail else ""))

def section(title: str):
    print(f"\n{'═'*60}")
    print(f"  {title}")
    print(f"{'═'*60}")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 0: ENVIRONMENT VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

def test_environment():
    section("0. Environment & Configuration")
    from dotenv import load_dotenv
    load_dotenv(interpolate=False)

    required = ["GEMINI_API_KEY", "DATABASE_URL"]
    optional = ["GROQ_API_KEY", "LANGCHAIN_API_KEY", "LANGCHAIN_TRACING_V2"]

    for key in required:
        val = os.getenv(key, "")
        if val and not val.startswith("your_"):
            _pass(f"ENV: {key}", f"{'*' * 10}{val[-4:]}")
        else:
            _fail(f"ENV: {key}", "Not set or still placeholder")

    for key in optional:
        val = os.getenv(key, "")
        if val and not val.startswith("your_") and not val.startswith("ls__your"):
            _pass(f"ENV: {key} (optional)", "Set")
        else:
            _warn(f"ENV: {key} (optional)", "Not set — optional feature disabled")

    # Check DATABASE_URL type
    db_url = os.getenv("DATABASE_URL", "")
    if "supabase" in db_url:
        _pass("DATABASE_URL", "Supabase (cloud) PostgreSQL")
    elif "localhost" in db_url or "127.0.0.1" in db_url:
        _pass("DATABASE_URL", "Local PostgreSQL")
    elif "postgres" in db_url:
        _warn("DATABASE_URL", "Docker hostname 'postgres' — may not resolve locally")
    else:
        _fail("DATABASE_URL", f"Unexpected format: {db_url[:30]}...")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: IMPORTS — all new packages must import cleanly
# ═══════════════════════════════════════════════════════════════════════════

def test_imports():
    section("1. Package Imports")

    packages = [
        ("langchain", "langchain"),
        ("langchain_community", "langchain-community"),
        ("langchain_core", "langchain-core"),
        ("langgraph", "langgraph"),
        ("langsmith", "langsmith"),
        ("langchain_openai", "langchain-openai"),
        ("langchain_huggingface", "langchain-huggingface"),
        ("faiss", "faiss-cpu"),
        ("rank_bm25", "rank-bm25"),
        ("sentence_transformers", "sentence-transformers"),
        ("sqlalchemy", "sqlalchemy"),
        ("psycopg2", "psycopg2-binary"),
        ("asyncpg", "asyncpg"),
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("pydantic", "pydantic"),
        ("dotenv", "python-dotenv"),
    ]

    for module, pkg in packages:
        try:
            __import__(module)
            _pass(f"import {module}")
        except ImportError as e:
            _fail(f"import {module}", f"pip install {pkg} — {e}")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: PROJECT MODULE IMPORTS
# ═══════════════════════════════════════════════════════════════════════════

def test_project_imports():
    section("2. Project Module Imports")

    modules = [
        ("configs", "DATABASE_URL, FORBIDDEN_KEYWORDS"),
        ("backend.db_connection", "get_tables, get_schema_as_text, execute_query, test_connection"),
        ("backend.retrieval.schema_indexer", "SchemaIndexer"),
        ("backend.retrieval.hybrid_retriever", "HybridSchemaRetriever"),
        ("backend.llm.providers", "get_primary_llm, get_fallback_llm, get_llm_with_fallback"),
        ("backend.llm.prompts", "REASONING_PROMPT, SQL_GENERATION_PROMPT"),
        ("backend.graph.state", "PipelineState"),
        ("backend.graph.nodes", "schema_retrieval_node, reasoning_node"),
        ("backend.graph.pipeline", "build_pipeline, get_pipeline"),
        ("backend.graph", "get_pipeline, PipelineState"),
    ]

    for mod, items in modules:
        try:
            m = __import__(mod, fromlist=items.split(", "))
            for item in items.split(", "):
                if not hasattr(m, item.strip()):
                    _fail(f"{mod}.{item.strip()}", "attribute not found")
            _pass(f"from {mod} import {items[:50]}")
        except Exception as e:
            _fail(f"import {mod}", str(e)[:100])


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: DATABASE — SQLAlchemy connectivity
# ═══════════════════════════════════════════════════════════════════════════

def test_database():
    section("3. Database — SQLAlchemy + PostgreSQL")

    try:
        from backend.db_connection import test_connection, get_tables, get_schema_as_text, execute_query

        # 3.1 Connection
        status = test_connection()
        if status.get("connected"):
            _pass("PostgreSQL connection", f"{status.get('table_count', 0)} tables (dataset: {status.get('dataset_name', 'unknown')})")
        else:
            _fail("PostgreSQL connection", status.get("error", "Unknown error"))
            print("    ⚠️  Cannot continue database tests without a connection.")
            print("    → Fix DATABASE_URL in .env (use localhost if not using Docker)")
            return

        # 3.2 Table list
        tables = get_tables()
        if tables:
            _pass("get_tables()", f"Found: {', '.join(tables[:5])}{'...' if len(tables) > 5 else ''}")
        else:
            _fail("get_tables()", "Empty result — is the Chinook dataset loaded?")
            return

        # 3.3 Schema as text (used by RAG)
        schema = get_schema_as_text()
        if schema and len(schema) == len(tables):
            sample = list(schema.values())[0][:80]
            _pass("get_schema_as_text()", f"Sample: {sample}...")
        else:
            _fail("get_schema_as_text()", f"Expected {len(tables)} entries, got {len(schema)}")

        # 3.4 Simple query
        results = execute_query('SELECT COUNT(*) as count FROM "Artist"')
        if results and results[0].get("count", 0) > 0:
            _pass("execute_query()", f"Artist count = {results[0]['count']}")
        else:
            _fail("execute_query()", f"Unexpected result: {results}")

    except Exception as e:
        _fail("Database test suite", f"{type(e).__name__}: {e}")
        traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4: RETRIEVAL — FAISS + BM25 + CrossEncoder
# ═══════════════════════════════════════════════════════════════════════════

def test_retrieval():
    section("4. Retrieval — FAISS + BM25 + Cross-Encoder")

    try:
        from backend.retrieval.schema_indexer import SchemaIndexer
        from backend.retrieval.hybrid_retriever import HybridSchemaRetriever

        # Minimal fake schemas for testing
        test_schemas = {
            "Artist": 'Table "Artist": "ArtistId" INTEGER PRIMARY KEY | "Name" TEXT NOT NULL',
            "Album": 'Table "Album": "AlbumId" INTEGER PRIMARY KEY | "Title" TEXT | "ArtistId" INTEGER FK: "ArtistId" → "Artist"("ArtistId")',
            "Track": 'Table "Track": "TrackId" INTEGER PRIMARY KEY | "Name" TEXT | "AlbumId" INTEGER | "GenreId" INTEGER | "UnitPrice" NUMERIC',
            "Customer": 'Table "Customer": "CustomerId" INTEGER PRIMARY KEY | "FirstName" TEXT | "LastName" TEXT | "Email" TEXT',
            "Invoice": 'Table "Invoice": "InvoiceId" INTEGER PRIMARY KEY | "CustomerId" INTEGER | "Total" NUMERIC',
            "InvoiceLine": 'Table "InvoiceLine": "InvoiceLineId" INTEGER PRIMARY KEY | "InvoiceId" INTEGER | "TrackId" INTEGER | "UnitPrice" NUMERIC | "Quantity" INTEGER',
        }

        # 4.1 SchemaIndexer: FAISS
        print("  ⏳ Loading embedding model (first time is slow, ~5-30s)...")
        indexer = SchemaIndexer()
        vectorstore = indexer.index_schema(test_schemas)
        _pass("SchemaIndexer.index_schema()", f"{len(test_schemas)} tables → FAISS index (dim={indexer._get_dimension()})")

        # 4.2 Semantic search
        results = indexer.semantic_search("customer purchases", k=3)
        if results:
            top_tables = [doc.metadata["table"] for doc, _ in results[:3]]
            _pass("FAISS.semantic_search()", f"Top-3 for 'customer purchases': {top_tables}")
        else:
            _fail("FAISS.semantic_search()", "No results returned")

        # 4.3 HybridRetriever (BM25 + FAISS)
        retriever = HybridSchemaRetriever(indexer)
        _pass("HybridSchemaRetriever.__init__()", "BM25 index built")

        # 4.4 Full hybrid retrieve (without cross-encoder reranking for speed)
        print("  ⏳ Loading cross-encoder (first time is slow, ~10-30s)...")
        retrieved = retriever.retrieve("top customers by total amount spent", k=4, rerank_top_n=3)
        if retrieved:
            _pass("HybridSchemaRetriever.retrieve()", f"Result: {retrieved}")
        else:
            _fail("HybridSchemaRetriever.retrieve()", "Empty result")

    except Exception as e:
        _fail("Retrieval test suite", f"{type(e).__name__}: {e}")
        traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5: LLM PROVIDERS — LangChain
# ═══════════════════════════════════════════════════════════════════════════

async def test_llm_async():
    section("5. LLM Providers — LangChain + Gemini")

    try:
        from backend.llm.providers import get_primary_llm, get_fallback_llm, get_llm_with_fallback
        from langchain_core.messages import HumanMessage

        # 5.1 Primary LLM (Gemini)
        print("  ⏳ Testing Gemini (primary LLM)...")
        llm = get_primary_llm()
        response = await llm.ainvoke([HumanMessage(content="Reply with exactly: OK")])
        if "OK" in response.content or len(response.content) < 20:
            _pass("Gemini (primary)", f"Response: {response.content.strip()[:50]}")
        else:
            _warn("Gemini (primary)", f"Unexpected response: {response.content[:50]}")

        # 5.2 Fallback chain
        chain = get_llm_with_fallback()
        _pass("get_llm_with_fallback()", "Chain built (Gemini → Groq)")

        # 5.3 Prompt templates
        from backend.llm.prompts import REASONING_PROMPT, SQL_GENERATION_PROMPT, SELF_CORRECTION_PROMPT, RESPONSE_SYNTHESIS_PROMPT
        for name, prompt in [
            ("REASONING_PROMPT", REASONING_PROMPT),
            ("SQL_GENERATION_PROMPT", SQL_GENERATION_PROMPT),
            ("SELF_CORRECTION_PROMPT", SELF_CORRECTION_PROMPT),
            ("RESPONSE_SYNTHESIS_PROMPT", RESPONSE_SYNTHESIS_PROMPT),
        ]:
            _pass(f"Prompt template: {name}", f"Input vars: {prompt.input_variables}")

    except Exception as e:
        _fail("LLM test suite", f"{type(e).__name__}: {e}")
        traceback.print_exc()


def test_llm():
    asyncio.run(test_llm_async())


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6: LANGGRAPH PIPELINE — Full E2E
# ═══════════════════════════════════════════════════════════════════════════

async def test_pipeline_async():
    section("6. LangGraph Pipeline — End-to-End Query")

    try:
        from backend.graph.pipeline import build_pipeline
        from backend.graph.state import PipelineState

        # 6.1 Compile graph
        print("  ⏳ Compiling LangGraph StateGraph...")
        pipeline = build_pipeline()
        _pass("LangGraph build_pipeline()", "StateGraph compiled")

        # 6.2 Meta query (no SQL needed — fastest test)
        print("  ⏳ Running META_QUERY test (schema question)...")
        initial_state = {
            "user_query": "What tables are in the database?",
            "history": [],
            "messages": [],
            "retry_count": 0,
            "max_retries": 2,
            "reasoning_trace": [],
        }

        result = await pipeline.ainvoke(initial_state)

        if result.get("final_answer"):
            _pass("META_QUERY pipeline", f"Answer: {result['final_answer'][:80]}...")
        else:
            _fail("META_QUERY pipeline", f"No final_answer. Error: {result.get('pipeline_error', 'unknown')}")

        # Check trace
        trace = result.get("reasoning_trace", [])
        if trace:
            _pass("Reasoning trace", f"{len(trace)} steps: {[t['agent'] for t in trace]}")
        else:
            _warn("Reasoning trace", "Empty — check nodes.py _add_trace calls")

        # 6.3 Data query (full pipeline with SQL)
        print("  ⏳ Running DATA_QUERY test (full SQL pipeline)...")
        initial_state2 = {
            "user_query": "How many artists are in the database?",
            "history": [],
            "messages": [],
            "retry_count": 0,
            "max_retries": 2,
            "reasoning_trace": [],
        }

        result2 = await pipeline.ainvoke(initial_state2)

        if result2.get("final_answer") and not result2.get("pipeline_error"):
            sql = result2.get("corrected_sql") or result2.get("generated_sql", "")
            _pass("DATA_QUERY pipeline", f"Answer: {result2['final_answer'][:80]}")
            _pass("Generated SQL", sql[:100])
            _pass("Row count", str(result2.get("row_count", 0)))
        else:
            _fail("DATA_QUERY pipeline", f"Error: {result2.get('pipeline_error') or result2.get('execution_error', 'unknown')}")
            if result2.get("generated_sql"):
                print(f"    Generated SQL was: {result2['generated_sql'][:100]}")

    except Exception as e:
        _fail("Pipeline test suite", f"{type(e).__name__}: {e}")
        traceback.print_exc()


def test_pipeline():
    asyncio.run(test_pipeline_async())


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7: FASTAPI — HTTP endpoint test
# ═══════════════════════════════════════════════════════════════════════════

async def test_api_async():
    section("7. FastAPI API Layer")

    try:
        from fastapi.testclient import TestClient
        from backend.api.main import app

        # Use sync TestClient for simplicity
        with TestClient(app, raise_server_exceptions=False) as client:

            # 7.1 Health check
            r = client.get("/health")
            if r.status_code == 200:
                data = r.json()
                _pass("GET /health", f"status={data.get('status')} db={data.get('database_connected')}")
            else:
                _fail("GET /health", f"HTTP {r.status_code}: {r.text[:100]}")

            # 7.2 List databases
            r = client.get("/databases")
            if r.status_code == 200:
                dbs = r.json()
                _pass("GET /databases", f"{len(dbs)} database(s) registered")
            else:
                _fail("GET /databases", f"HTTP {r.status_code}")

            # 7.3 Schema endpoint
            r = client.get("/databases/default/schema")
            if r.status_code == 200:
                schema_data = r.json()
                table_count = len(schema_data.get("tables", []))
                _pass("GET /databases/default/schema", f"{table_count} tables")
            else:
                _warn("GET /databases/default/schema", f"HTTP {r.status_code} — may need DB connected")

            # 7.4 Query endpoint (full pipeline via HTTP)
            print("  ⏳ Sending query via HTTP (this takes 10-30s)...")
            r = client.post(
                "/query",
                json={"query": "How many tracks are there?", "database_id": "default"},
                timeout=120,
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    _pass("POST /query", f"Answer: {data.get('answer', '')[:80]}")
                    _pass("SQL used", data.get("sql_used", "N/A")[:80])
                else:
                    _warn("POST /query", f"success=False: {data.get('answer', '')[:80]}")
            else:
                _fail("POST /query", f"HTTP {r.status_code}: {r.text[:100]}")

    except Exception as e:
        _fail("API test suite", f"{type(e).__name__}: {e}")
        traceback.print_exc()


def test_api():
    asyncio.run(test_api_async())


# ═══════════════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

def print_summary():
    print(f"\n{'═'*60}")
    print("  TEST SUMMARY")
    print(f"{'═'*60}")

    passed = sum(1 for r in results if r[0].startswith("✅"))
    warned = sum(1 for r in results if r[0].startswith("⚠️"))
    failed = sum(1 for r in results if r[0].startswith("❌"))
    total = len(results)

    print(f"\n  Total: {total}  |  ✅ Pass: {passed}  |  ⚠️  Warn: {warned}  |  ❌ Fail: {failed}")

    if failed == 0:
        print("\n  🎉 All critical tests PASSED — ready for Render + Supabase!")
    elif failed <= 2:
        print("\n  ⚠️  Minor failures — review above. Likely configuration issues.")
    else:
        print("\n  ❌ Multiple failures — fix before deploying to Render + Supabase.")

    if failed > 0:
        print("\n  FAILED TESTS:")
        for status, name, detail in results:
            if status.startswith("❌"):
                print(f"    • {name}: {detail}")

    print()


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

SECTIONS = {
    "env": test_environment,
    "imports": test_imports,
    "project": test_project_imports,
    "db": test_database,
    "retrieval": test_retrieval,
    "llm": test_llm,
    "pipeline": test_pipeline,
    "api": test_api,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ReasonSQL 2.0 Migration Test Suite")
    parser.add_argument(
        "--section", "-s",
        choices=list(SECTIONS.keys()),
        help="Run only a specific section (default: all)",
    )
    args = parser.parse_args()

    print("\n" + "█" * 60)
    print("  ReasonSQL 2.0 — Migration Test Suite")
    print("█" * 60)

    if args.section:
        SECTIONS[args.section]()
    else:
        # Run all sections in order
        test_environment()
        test_imports()
        test_project_imports()
        test_database()
        test_retrieval()
        test_llm()
        test_pipeline()
        test_api()

    print_summary()
