# NL2SQL Multi-Agent System

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CrewAI](https://img.shields.io/badge/Framework-CrewAI-green.svg)](https://github.com/joaomdmoura/crewai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![LLM: Gemini/Groq](https://img.shields.io/badge/LLM-Gemini%20%7C%20Groq-purple.svg)](https://ai.google.dev/)

> **Intelligent Natural Language to SQL using CrewAI Multi-Agent Architecture**

A sophisticated system that converts natural language questions into SQL queries through a **12-agent pipeline** with schema reasoning, self-correction, safety validation, and explainable AI.

**🚀 NEW: Quota-Optimized Orchestrator** - Uses only 4-6 LLM calls per query (down from 12) for sustainable API usage.

---

## ⚡ Quick Start (3 steps)

```bash
# 1. Clone and setup
git clone <repo-url>
cd nl2sql_system
python -m venv venv && venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# 2. Configure (get free API key from https://console.groq.com/keys or https://ai.google.dev/)
cp .env.example .env
# Edit .env and add your GROQ_API_KEY or GEMINI_API_KEY

# 3. Run setup and demo
python setup.py   # Downloads Chinook database
python demo.py    # See the system in action!
```

**Single query mode:**
```bash
python cli.py -q "How many customers are from Brazil?"
```

**Interactive mode:**
```bash
python cli.py
```

**Web UI:**
```bash
streamlit run ui/streamlit_app.py
```

---

## 🎯 Problem Statement

Traditional "prompt → LLM → SQL" approaches fail in many scenarios:

| Problem | Naive Approach | Our Solution |
|---------|----------------|--------------|
| Large schema | LLM hallucinates table names | **Schema exploration first** |
| Ambiguous queries | Makes arbitrary assumptions | **Asks clarifying questions** |
| Wrong SQL | No way to detect or fix | **Self-correction with retry** |
| Expensive queries | `SELECT *` on million-row tables | **Enforced column selection + LIMIT** |
| No transparency | Black box output | **Full reasoning trace visible** |

**Result:** Naive approaches hit ~50% accuracy. Our system achieves significantly higher through intelligent reasoning.

## 🏗️ Architecture (12-Agent Pipeline)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                USER QUERY                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. INTENT ANALYZER AGENT                                                    │
│     • Classifies: DATA_QUERY | META_QUERY | AMBIGUOUS                        │
│     • Detects query complexity                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
        [Data Query]           [Meta Query]             [Ambiguous]
              │                       │                       │
              │                       │                       ▼
              │                       │         ┌─────────────────────────────┐
              │                       │         │ 2. CLARIFICATION AGENT      │
              │                       │         │   • Resolves vague terms    │
              │                       │         │   • Provides defaults       │
              │                       │         │   • May ask user for input  │
              │                       │         └─────────────────────────────┘
              │                       │                       │
              └───────────────────────┼───────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  3. SCHEMA EXPLORER AGENT                                                    │
│     • Inspects database schema                                               │
│     • Retrieves tables, columns, relationships                               │
│     • Handles meta-queries (returns here for meta)                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
        [Complex Query]                                 [Simple Query]
              │                                               │
              ▼                                               │
┌─────────────────────────────┐                               │
│ 4. QUERY DECOMPOSER AGENT   │                               │
│   • Breaks into sub-queries │                               │
│   • Identifies CTEs/JOINs   │                               │
│   • Plans set operations    │                               │
└─────────────────────────────┘                               │
              │                                               │
              └───────────────────────┬───────────────────────┘
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
        [Needs Data Context]                             [Sufficient]
              │                                               │
              ▼                                               │
┌─────────────────────────────┐                               │
│ 5. DATA EXPLORER AGENT      │                               │
│   • Samples data            │                               │
│   • Checks value ranges     │                               │
│   • Informs query decisions │                               │
└─────────────────────────────┘                               │
              │                                               │
              └───────────────────────┬───────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  6. QUERY PLANNER AGENT                                                      │
│     • Designs query plan with tables, joins, filters                         │
│     • Enforces safety rules (no SELECT *, LIMIT required)                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  7. SQL GENERATOR AGENT                                                      │
│     • Converts plan to valid SQLite SQL                                      │
│     • Handles syntax, escaping, aliases                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  8. SAFETY VALIDATOR AGENT  🛡️ [GATE - Must Pass]                           │
│     • Validates: read-only, no destructive keywords                          │
│     • Checks: LIMIT present, no SELECT *                                     │
│     • Decision: APPROVED ✅ or REJECTED ❌                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
         [APPROVED]                                      [REJECTED]
              │                                               │
              ▼                                               │
┌─────────────────────────────────────────────────────────────┤
│  9. SQL EXECUTOR AGENT                                      │
│     • Executes query safely                                 │
│     • Captures results & errors                             │
└─────────────────────────────────────────────────────────────┘
              │                                               │
     ┌────────┴────────┐                                      │
     ▼                 ▼                                      │
 [Success]         [Failure]                                  │
     │                 │                                      │
     │                 ▼                                      │
     │    ┌─────────────────────────┐                         │
     │    │ 10. SELF-CORRECTION     │ ◄────────────────────────┘
     │    │   • Analyzes failure    │
     │    │   • Revises strategy    │
     │    │   • Retries (max 3)     │ ─────────► Back to Step 6
     │    └─────────────────────────┘
     │                 │
     └────────┬────────┘
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  11. RESULT VALIDATOR AGENT                                                  │
│      • Checks for anomalies (negative counts, NULLs)                         │
│      • Verifies results match query intent                                   │
│      • Flags suspicious outputs                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  12. RESPONSE SYNTHESIZER AGENT                                              │
│      • Converts results to human-readable answer                             │
│      • Explains query approach                                               │
│      • Handles empty results gracefully                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FINAL RESPONSE                                  │
│  • Human-readable answer                                                     │
│  • Generated SQL                                                             │
│  • Full reasoning trace with decision points                                 │
│  • Execution metrics                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 🤖 Agent Responsibilities (12 Specialized Agents)

### Core Agents (7)

| # | Agent | Role | Tools |
|---|-------|------|-------|
| 1 | **IntentAnalyzer** | Classifies query intent (DATA/META/AMBIGUOUS) | None (reasoning only) |
| 3 | **SchemaExplorer** | Inspects database schema, answers meta-queries | `SchemaInspectorTool`, `GetSchemaContextTool` |
| 6 | **QueryPlanner** | Designs safe query plans (no `SELECT *`, LIMIT required) | `SchemaInspectorTool` |
| 7 | **SQLGenerator** | Converts plans to valid SQLite SQL | `SQLValidatorTool` |
| 9 | **SQLExecutor** | Validates and executes queries safely | `SQLValidatorTool`, `SQLExecutorTool` |
| 10 | **SelfCorrection** | Analyzes failures, proposes fixes | `SchemaInspectorTool`, `SQLValidatorTool` |
| 12 | **ResponseSynthesizer** | Creates human-readable explanations | None (synthesis only) |

### Extended Agents (5 New)

| # | Agent | Role | Tools |
|---|-------|------|-------|
| 2 | **ClarificationAgent** | Resolves ambiguous terms ("recent", "top"), provides defaults | None (reasoning only) |
| 4 | **QueryDecomposer** | Breaks complex queries into CTEs, subqueries, set operations | `SchemaInspectorTool` |
| 5 | **DataExplorer** | Samples data to inform decisions (date ranges, value distributions) | `DataSamplerTool` |
| 8 | **SafetyValidator** | Pre-execution security gate - APPROVED ✅ or REJECTED ❌ | `SafetyCheckerTool` |
| 11 | **ResultValidator** | Sanity-checks results (no negative counts, missing data) | None (analysis only) |

### Why 12 Agents?

1. **IntentAnalyzer** → Prevents wrong query type handling
2. **ClarificationAgent** → Resolves "recent = 30 days" ambiguity
3. **SchemaExplorer** → No hallucinated table/column names
4. **QueryDecomposer** → Handles "customers who bought BOTH Rock AND Jazz"
5. **DataExplorer** → Knows actual date ranges before querying
6. **QueryPlanner** → Structured, safe query design
7. **SQLGenerator** → Correct syntax, escaping, aliases
8. **SafetyValidator** → GATE: Rejects `DROP TABLE`, ensures `LIMIT`
9. **SQLExecutor** → Safe execution with error capture
10. **SelfCorrection** → Retry with learned insights (max 3)
11. **ResultValidator** → Catches suspicious outputs before user sees them
12. **ResponseSynthesizer** → Human-friendly answer with context

## 📦 Installation

### Prerequisites

- Python 3.10+
- Groq API key (or Google Gemini API key)

### Setup

```bash
# Clone and navigate to the project
cd nl2sql_system

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Download Chinook database
mkdir -p data
# Download from: https://github.com/lerocha/chinook-database
# Place chinook.db in the data/ folder
```

### Environment Variables

```bash
# .env file
GROQ_API_KEY=your_groq_api_key_here
DATABASE_PATH=./data/chinook.db
LLM_PROVIDER=groq
LLM_MODEL=groq/llama-3.1-70b-versatile
VERBOSE=true
MAX_RETRIES=3
DEFAULT_LIMIT=100
```

## 🚀 Usage

### Command Line Interface

```bash
# Interactive mode
python cli.py

# Single query
python cli.py -q "How many customers are from Brazil?"

# Run demonstration
python cli.py --demo

# Verbose mode
python cli.py -q "Show me top 5 artists" --verbose
```

### Streamlit Web UI

```bash
streamlit run ui/streamlit_app.py
```

### Programmatic Usage

```python
from orchestrator import NL2SQLOrchestrator

# Initialize
orchestrator = NL2SQLOrchestrator(verbose=True)

# Process a query
response = orchestrator.process_query("How many customers are from Brazil?")

# Access results
print(response.answer)        # Human-readable answer
print(response.sql_used)      # Generated SQL
print(response.reasoning_trace)  # Full trace of agent decisions
```

## 🎮 Demo Queries

The system handles queries of increasing complexity:

### Simple
```
"How many customers are from Brazil?"
"List all albums by AC/DC"
```

### Meta-queries
```
"What tables exist in this database?"
"What columns does the Invoice table have?"
```

### Moderate (Joins & Aggregations)
```
"Which 5 artists have the most tracks?"
"Total revenue by country, sorted highest first"
```

### Complex (Reasoning Required)
```
"Which customers have never made a purchase?"
"Are there any genres with no tracks?"
```

### Ambiguous (Clarification Requested)
```
"Show me recent orders"        → Resolves: "recent" = last 30 days
"Who are our best customers?"  → Resolves: "best" = top 10 by revenue
```

## 🔒 Safety Features

1. **Read-only operations** - No INSERT, UPDATE, DELETE, DROP allowed
2. **No SELECT *** - All columns must be explicitly specified
3. **LIMIT enforced** - Every query must have a LIMIT clause
4. **SQL validation** - Queries are validated before execution
5. **Safety Gate** - SafetyValidatorAgent MUST approve before execution
6. **Error handling** - Graceful handling of all error conditions

## 📁 Project Structure

```
nl2sql_system/
├── agents/
│   ├── __init__.py
│   └── agent_definitions.py         # 12 specialized agents
├── config/
│   ├── __init__.py
│   └── settings.py                  # Configuration management
├── examples/
│   ├── __init__.py
│   └── reasoning_traces.py          # Example traces (ambiguous, self-correction, etc.)
├── models/
│   ├── __init__.py
│   ├── schemas.py                   # Pydantic models for data flow
│   └── agent_outputs.py             # Structured output models for each agent
├── orchestrator/
│   ├── __init__.py
│   ├── crew_orchestrator.py         # Legacy orchestrator
│   ├── enhanced_orchestrator.py     # Enhanced 12-agent orchestrator
│   └── deterministic_orchestrator.py # ⭐ RECOMMENDED: State-machine orchestrator
├── tasks/
│   ├── __init__.py
│   └── task_definitions.py          # CrewAI task definitions
├── tools/
│   ├── __init__.py
│   └── database_tools.py            # Custom CrewAI tools
├── ui/
│   ├── __init__.py
│   └── streamlit_app.py             # Web interface
├── data/
│   └── chinook.db                   # SQLite database
├── cli.py                           # Command-line interface
├── demo.py                          # Demonstration script
├── requirements.txt
├── .env.example
└── README.md
```

## 🔍 Why This System is Better

### Naive Approach vs Our System

| Scenario | Naive "Schema + Question → LLM → SQL" | Our Multi-Agent System |
|----------|---------------------------------------|------------------------|
| Unknown table name | ❌ Hallucinates a name | ✅ Explores schema first |
| Ambiguous "recent" | ❌ Picks arbitrary date | ✅ Asks for clarification |
| Wrong SQL syntax | ❌ Returns error to user | ✅ Self-corrects and retries |
| SELECT * on 1M rows | ❌ Crashes or expensive | ✅ Enforces column selection + LIMIT |
| Complex joins | ❌ Often misses relationships | ✅ Uses foreign key analysis |
| Empty results | ❌ "No data found" | ✅ Explains why and suggests alternatives |

### Key Differentiators

1. **Schema Understanding** - Explores database structure before attempting queries
2. **Intent Classification** - Distinguishes between data requests and metadata requests
3. **Transparent Reasoning** - Every decision is logged and explainable
4. **Self-Healing** - Automatically retries with corrected strategies
5. **Resource-Conscious** - Prevents expensive operations
6. **User-Centric** - Asks clarifying questions instead of assuming

## � Deterministic Orchestrator (State Machine)

The system uses a **deterministic state-machine orchestrator** that provides:

### Design Principles

1. **Central Control** - Orchestrator decides what runs next, not agents
2. **Explicit Flow** - Every branch is visible and documented  
3. **Structured I/O** - Agents return typed outputs, orchestrator inspects status
4. **No Agent-to-Agent Calls** - Agents never talk directly to each other
5. **Full Traceability** - Every decision is logged with reasoning

### Agent Output Structure

Every agent returns structured output with:

```python
{
    "status": "ok" | "ambiguous" | "error" | "retry" | "blocked",
    "reason": "Why this status was chosen",
    "data": {...}  # Agent-specific structured data
}
```

### Flow Control

```
User Input
→ IntentAnalyzerAgent
→ if intent == AMBIGUOUS:
     ClarificationAgent (blocks until resolved)
→ if intent == META_QUERY:
     SchemaExplorerAgent → ResponseSynthesizerAgent → END
→ SchemaExplorerAgent
→ if query is COMPLEX:
     QueryDecomposerAgent
→ if planner needs data context:
     DataExplorerAgent
→ QueryPlannerAgent
→ SQLGeneratorAgent
→ SafetyValidatorAgent  ← HARD GATE (must approve)
→ SQLExecutorAgent
→ if execution fails OR empty result:
     SelfCorrectionAgent (max retries = 3)
     → QueryPlannerAgent → SQLGeneratorAgent → SafetyValidatorAgent → SQLExecutorAgent
→ ResultValidatorAgent
→ ResponseSynthesizerAgent
→ FINAL RESPONSE
```

### Example Reasoning Trace

```python
from examples import print_trace, SELF_CORRECTION_TRACE
print_trace(SELF_CORRECTION_TRACE)
```

Output:
```
QUERY: Show me all tracks by artists named 'Beatles'
=====================================
FLOW:
  START → INTENT_ANALYSIS
  INTENT_ANALYSIS → SCHEMA_EXPLORATION
  ...
  SQL_EXECUTION → SELF_CORRECTION (empty result)
  SELF_CORRECTION → QUERY_PLANNING (retry 1)
  ...
  
Step 7: SelfCorrection
  Action: Analyzed failure and proposed fix
  Decision: Should retry: True, Skip to: PLANNER
  Diagnosis: Exact match 'Beatles' returned 0 rows. Using LIKE '%Beatles%' instead.
```

## �🛠️ Extending the System

### Adding New Agents

```python
# In agents/agent_definitions.py
def create_custom_agent() -> Agent:
    return Agent(
        role="Custom Role",
        goal="Your agent's goal",
        backstory="Your agent's backstory",
        tools=[YourCustomTool()],
        llm=get_llm(),
        verbose=VERBOSE
    )
```

### Adding Custom Tools

```python
# In tools/database_tools.py
from crewai.tools import BaseTool

class CustomTool(BaseTool):
    name: str = "custom_tool"
    description: str = "Description of what the tool does"
    
    def _run(self, input_param: str) -> str:
        # Your tool logic here
        return result
```

## 📊 Performance Considerations

- **LLM Context**: Use Llama 3.1 70B (131K context) for large schemas
- **Rate Limiting**: Configure `MAX_RPM` to avoid API rate limits
- **Caching**: Schema exploration results can be cached for repeated queries
- **Retry Limits**: Default is 3 retries, configurable via `MAX_RETRIES`

## 📄 License

MIT License - See LICENSE file for details.

## 🙏 Acknowledgments

- [CrewAI](https://github.com/joaomdmoura/crewai) - Multi-agent framework
- [Groq](https://groq.com/) - Fast LLM inference
- [Chinook Database](https://github.com/lerocha/chinook-database) - Sample database

---

**Built for the NL2SQL Challenge** | Demonstrating advanced multi-agent reasoning for database query generation.
