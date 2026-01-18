"""
ReasonSQL Multi-Agent System - Streamlit Web UI (Refactored v3)

DESIGN CHANGES (v3 - Demo Ready):
1. LIGHT THEME - Clean white/gray with soft gradients
2. VISUAL AGENT MAP - Horizontal flow showing 12 agents as cards
3. FLASHY BUT LOW-TEXT - Icons, badges, short labels over paragraphs  
4. MERGED TABS - "📦 Result" and "🧠 Reasoning" only
5. JUDGE-FRIENDLY - Get the system in 5 seconds
6. DEMO MODE - 5 preset queries with auto-run option
7. JUDGE MODE - Collapsed reasoning by default, key steps highlighted
8. RATE LIMIT PROTECTION - Prevents demo failures
"""
import streamlit as st
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.orchestrator import ReasonSQLOrchestrator
from backend.models import ExecutionStatus, FinalResponse, ReasoningTrace, AgentAction
from backend.adapters import run_naive_query, format_naive_result_for_display, NAIVE_DISCLAIMER, NAIVE_COMPARISON_LABEL

# API Client for decoupled mode (Step 4 of migration)
from frontend.api_client import ReasonSQLClient, ExecutionStatusAPI


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

# Key agents to highlight in Simple Mode
KEY_AGENTS_FOR_JUDGES = [
    "IntentAnalyzer",
    "SchemaExplorer", 
    "QueryPlanner",
    "SafetyValidator",
    "ResponseSynthesizer"
]


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="ReasonSQL - Multi-Agent NL→SQL System",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed"  # Collapsed for cleaner look
)


# ============================================================
# LIGHT THEME CSS - Modern, clean, visual
# ============================================================

st.markdown("""
<style>
    /* ===== GLOBAL LIGHT THEME ===== */
    .stApp {
        background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
    }
    
    /* ===== HERO HEADER ===== */
    .hero-header {
        text-align: center;
        padding: 1.5rem 0;
        margin-bottom: 1rem;
    }
    
    .hero-title {
        font-size: 2.5rem;
        font-weight: 800;
        color: #dc2626;
        margin-bottom: 0.3rem;
    }
    
    .hero-subtitle {
        font-size: 1rem;
        color: #1e293b;
        font-weight: 500;
    }
    
    .hero-badge {
        display: inline-block;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.4rem 1rem;
        border-radius: 2rem;
        font-size: 0.8rem;
        font-weight: 600;
        margin-top: 0.8rem;
    }
    
    /* ===== AGENT MAP FLOW ===== */
    .agent-map {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 0.3rem;
        padding: 1rem;
        overflow-x: auto;
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        border-radius: 1rem;
        margin: 1rem 0;
    }
    
    .agent-node {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-width: 70px;
        padding: 0.6rem 0.4rem;
        border-radius: 0.75rem;
        transition: all 0.3s ease;
        cursor: default;
    }
    
    .agent-node-done {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
        border: 2px solid #10b981;
        box-shadow: 0 2px 8px rgba(16, 185, 129, 0.2);
    }
    
    .agent-node-running {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        border: 2px solid #f59e0b;
        box-shadow: 0 2px 12px rgba(245, 158, 11, 0.3);
        animation: glow 1.5s ease-in-out infinite;
    }
    
    @keyframes glow {
        0%, 100% { box-shadow: 0 2px 12px rgba(245, 158, 11, 0.3); }
        50% { box-shadow: 0 4px 20px rgba(245, 158, 11, 0.5); }
    }
    
    .agent-node-pending {
        background: #f1f5f9;
        border: 2px solid #cbd5e1;
        opacity: 0.5;
    }
    
    .agent-node-skipped {
        background: #f1f5f9;
        border: 2px dashed #94a3b8;
        opacity: 0.4;
    }
    
    .agent-emoji {
        font-size: 1.4rem;
        margin-bottom: 0.2rem;
    }
    
    .agent-label {
        font-size: 0.65rem;
        font-weight: 700;
        color: #0f172a;
        text-align: center;
        line-height: 1.1;
    }
    
    .agent-type-badge {
        font-size: 0.5rem;
        padding: 0.1rem 0.3rem;
        border-radius: 0.5rem;
        margin-top: 0.2rem;
    }
    
    .badge-llm {
        background: #dbeafe;
        color: #1d4ed8;
    }
    
    .badge-rule {
        background: #f3e8ff;
        color: #7c3aed;
    }
    
    .flow-arrow {
        color: #475569;
        font-size: 1.2rem;
        margin: 0 0.1rem;
    }
    
    /* ===== RESULT HERO CARD ===== */
    .result-hero {
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid #e2e8f0;
        border-radius: 1rem;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
    }
    
    .result-status {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.4rem 1rem;
        border-radius: 2rem;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    
    .status-success {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
        color: #047857;
    }
    
    .status-empty {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        color: #b45309;
    }
    
    .status-error {
        background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
        color: #b91c1c;
    }
    
    .result-answer {
        font-size: 1.3rem;
        font-weight: 600;
        color: #0f172a;
        line-height: 1.5;
    }
    
    /* ===== STAT CARDS ===== */
    .stat-row {
        display: flex;
        gap: 0.75rem;
        margin: 1rem 0;
        flex-wrap: wrap;
    }
    
    .stat-card {
        flex: 1;
        min-width: 100px;
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 0.75rem;
        padding: 0.75rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
    }
    
    .stat-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #dc2626;
    }
    
    .stat-label {
        font-size: 0.7rem;
        color: #0f172a;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 700;
    }
    
    /* ===== SQL CARD ===== */
    .sql-card {
        background: #1e293b;
        border-radius: 0.75rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .sql-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.5rem;
    }
    
    .sql-label {
        color: #e2e8f0;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 600;
    }
    
    /* ===== EXECUTION STEP CARDS (4-SECTION LAYOUT) ===== */
    .step-card {
        background: white;
        border: 2px solid #e2e8f0;
        border-radius: 0.75rem;
        padding: 1rem;
        margin-bottom: 1rem;
        transition: all 0.2s ease;
    }
    
    .step-card:hover {
        border-color: #667eea;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.1);
    }
    
    .step-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid #f1f5f9;
    }
    
    .step-icon {
        font-size: 1.8rem;
        width: 50px;
        height: 50px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 0.5rem;
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
    }
    
    .step-title {
        flex: 1;
    }
    
    .step-title-text {
        font-size: 1rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.25rem;
    }
    
    .step-badge {
        display: inline-block;
        font-size: 0.7rem;
        padding: 0.2rem 0.5rem;
        border-radius: 0.5rem;
        font-weight: 600;
    }
    
    .step-badge-llm {
        background: #dbeafe;
        color: #1d4ed8;
    }
    
    .step-badge-rule {
        background: #f3e8ff;
        color: #7c3aed;
    }
    
    /* 4-Section Grid */
    .step-sections {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.75rem;
        margin-top: 1rem;
    }
    
    .step-section {
        background: #f8fafc;
        border-radius: 0.5rem;
        padding: 0.75rem;
        border-left: 3px solid #cbd5e1;
    }
    
    .step-section-input {
        border-left-color: #3b82f6;
    }
    
    .step-section-action {
        border-left-color: #8b5cf6;
    }
    
    .step-section-output {
        border-left-color: #10b981;
    }
    
    .step-section-reasoning {
        border-left-color: #f59e0b;
        grid-column: 1 / -1; /* Full width */
    }
    
    .step-section-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.5rem;
    }
    
    .step-section-icon {
        font-size: 1rem;
    }
    
    .step-section-title {
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #475569;
    }
    
    .step-section-content {
        font-size: 0.85rem;
        color: #1e293b;
        line-height: 1.5;
    }
    
    .step-section-empty {
        font-style: italic;
        color: #94a3b8;
    }
    
    .step-section-long {
        max-height: 200px;
        overflow-y: auto;
        padding: 0.5rem;
        background: white;
        border-radius: 0.25rem;
        border: 1px solid #e2e8f0;
    }
    
    /* ===== HIDE DEFAULTS ===== */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* ===== INPUT STYLING ===== */
    .stTextInput > div > div > input {
        border-radius: 0.75rem;
        border: 2px solid #e2e8f0;
        padding: 0.75rem 1rem;
        font-size: 1rem;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    /* ===== BUTTON STYLING ===== */
    .stButton > button {
        border-radius: 0.75rem;
        font-weight: 600;
        padding: 0.5rem 1.5rem;
        transition: all 0.2s ease;
    }
    
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
    }
    
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
    }
    
    /* ===== TAB STYLING - FORCE VISIBILITY ===== */
    /* CRITICAL FIX: Tab text must be visible without hover on light theme */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 0.5rem;
        padding: 0.5rem 1rem;
        font-weight: 600;
        color: #000000 !important; /* Dark text always visible */
        background-color: #f1f5f9;
    }
    
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white !important;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #e2e8f0;
        color: #000000 !important;
    }
    
    .stTabs [data-baseweb="tab"][aria-selected="true"]:hover {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white !important;
    }
    
    /* ===== EXPANDER STYLING - BLACK TEXT, WHITE ON HOVER ===== */
    /* CRITICAL FIX: Expander text black by default, white on hover with dark background */
    .streamlit-expanderHeader {
        background: #f8fafc !important;
        border-radius: 0.5rem;
        color: #000000 !important; /* Black text by default */
        transition: all 0.3s ease;
    }
    
    .streamlit-expanderHeader p,
    .streamlit-expanderHeader span,
    .streamlit-expanderHeader strong,
    .streamlit-expanderHeader em,
    .streamlit-expanderHeader * {
        color: #000000 !important;
        font-weight: 600 !important;
        transition: color 0.3s ease;
    }
    
    .streamlit-expanderHeader:hover {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important;
    }
    
    .streamlit-expanderHeader:hover p,
    .streamlit-expanderHeader:hover span,
    .streamlit-expanderHeader:hover strong,
    .streamlit-expanderHeader:hover em,
    .streamlit-expanderHeader:hover * {
        color: #ffffff !important; /* White text on hover */
    }
    
    /* ===== REASONING PAGE TEXT VISIBILITY ===== */
    /* CRITICAL FIX: All text on reasoning page must be dark and readable */
    .stMarkdown, .stMarkdown p, .stMarkdown span {
        color: #000000 !important;
    }
    
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
        color: #000000 !important;
    }
    
    /* Force visibility in info/success/caption boxes */
    .stAlert p, .stSuccess p, .stInfo p, .stCaption {
        color: #000000 !important;
    }
    
    /* Sidebar text visibility - BLACK for light theme */
    .css-1d391kg, [data-testid="stSidebar"] {
        color: #000000 !important;
    }
    
    [data-testid="stSidebar"] .stMarkdown p {
        color: #000000 !important;
    }
    
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #000000 !important;
    }
    
    [data-testid="stSidebar"] .stCaption {
        color: #475569 !important;
    }
    
    /* Query example cards in sidebar */
    .query-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 0.5rem;
        padding: 0.75rem;
        margin-bottom: 0.5rem;
        transition: all 0.2s ease;
    }
    
    .query-card:hover {
        border-color: #667eea;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.1);
    }
    
    .query-category {
        font-size: 0.7rem;
        font-weight: 700;
        color: #94a3b8 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.25rem;
    }
    
    .query-text {
        font-size: 0.85rem;
        color: #e2e8f0 !important;
        font-weight: 500;
    }
    
    /* Recent query cards */
    .recent-query-card {
        background: #f8fafc;
        border-left: 3px solid #667eea;
        padding: 0.5rem;
        margin-bottom: 0.5rem;
        border-radius: 0.25rem;
    }
    
    .recent-query-status {
        font-size: 0.7rem;
        font-weight: 600;
        color: #94a3b8 !important;
    }
    
    .recent-query-text {
        font-size: 0.8rem;
        color: #ffffff !important;
        margin: 0.25rem 0;
    }
    
    .recent-query-time {
        font-size: 0.7rem;
        color: #cbd5e1 !important;
    }
    
    /* ===== COMPARISON MODE STYLES ===== */
    .comparison-header {
        text-align: center;
        padding: 0.75rem;
        margin-bottom: 1rem;
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        border-radius: 0.5rem;
        border: 2px solid #f59e0b;
    }
    
    .comparison-header-text {
        font-size: 0.9rem;
        font-weight: 600;
        color: #b45309;
    }
    
    .naive-panel {
        background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
        border: 2px solid #ef4444;
        border-radius: 0.75rem;
        padding: 1rem;
    }
    
    .multiagent-panel {
        background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
        border: 2px solid #22c55e;
        border-radius: 0.75rem;
        padding: 1rem;
    }
    
    .panel-title {
        font-size: 0.9rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .naive-title {
        color: #dc2626;
    }
    
    .multiagent-title {
        color: #16a34a;
    }
    
    .panel-subtitle {
        font-size: 0.7rem;
        color: #6b7280;
        margin-bottom: 1rem;
    }
    
    .naive-status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.75rem;
        font-weight: 600;
    }
    
    .naive-status-success {
        background: #dcfce7;
        color: #16a34a;
    }
    
    .naive-status-error {
        background: #fee2e2;
        color: #dc2626;
    }
    
    .naive-status-blocked {
        background: #fef3c7;
        color: #b45309;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# DATA MODELS
# ============================================================

class AgentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"


# Simplified agent pipeline for visual map (6 main stages)
AGENT_MAP_STAGES = [
    {"key": "intent", "emoji": "🎯", "label": "Intent", "agents": ["IntentAnalyzer", "ClarificationAgent"], "is_llm": True},
    {"key": "schema", "emoji": "📊", "label": "Schema", "agents": ["SchemaExplorer"], "is_llm": False},
    {"key": "plan", "emoji": "📝", "label": "Plan", "agents": ["QueryDecomposer", "QueryPlanner", "DataExplorer"], "is_llm": True},
    {"key": "generate", "emoji": "⚙️", "label": "Generate", "agents": ["SQLGenerator"], "is_llm": True},
    {"key": "validate", "emoji": "🛡️", "label": "Safety", "agents": ["SafetyValidator"], "is_llm": False},
    {"key": "execute", "emoji": "🚀", "label": "Execute", "agents": ["SQLExecutor", "SelfCorrection", "ResultValidator"], "is_llm": False},
    {"key": "respond", "emoji": "💬", "label": "Respond", "agents": ["ResponseSynthesizer"], "is_llm": True},
]

# Full 12-agent pipeline for detailed view
AGENT_PIPELINE = [
    {"name": "IntentAnalyzer", "short": "Intent", "emoji": "🎯", "is_llm": True},
    {"name": "ClarificationAgent", "short": "Clarify", "emoji": "❓", "is_llm": True},
    {"name": "SchemaExplorer", "short": "Schema", "emoji": "📊", "is_llm": False},
    {"name": "QueryDecomposer", "short": "Decompose", "emoji": "🔨", "is_llm": True},
    {"name": "DataExplorer", "short": "Data", "emoji": "🔍", "is_llm": False},
    {"name": "QueryPlanner", "short": "Plan", "emoji": "📝", "is_llm": True},
    {"name": "SQLGenerator", "short": "SQL", "emoji": "⚙️", "is_llm": True},
    {"name": "SafetyValidator", "short": "Safety", "emoji": "🛡️", "is_llm": False},
    {"name": "SQLExecutor", "short": "Execute", "emoji": "🚀", "is_llm": False},
    {"name": "SelfCorrection", "short": "Fix", "emoji": "🔄", "is_llm": True},
    {"name": "ResultValidator", "short": "Check", "emoji": "✓", "is_llm": False},
    {"name": "ResponseSynthesizer", "short": "Answer", "emoji": "💬", "is_llm": True},
]


# ============================================================
# SESSION STATE
# ============================================================

def init_session_state():
    defaults = {
        'history': [],
        'orchestrator': None,
        'current_query': "",
        'is_processing': False,
        'last_response': None,
        # Demo Mode additions - ON by default for GitHub demo
        'demo_mode': True,
        'demo_index': 0,
        'demo_running': False,
        # Simple Mode (Simple Mode) - OFF by default for full reasoning display
        'judge_mode': False,
        # Rate limiting
        'last_query_time': None,
        'query_count_this_minute': 0,
        'provider_status': 'primary',  # 'primary', 'fallback', or 'exhausted'
        # Naive comparison mode - OFF by default (can overwhelm judges)
        'compare_naive': False,
        'naive_result': None,
        # API Mode - Use FastAPI backend instead of direct orchestrator
        'use_api_mode': False,  # Toggle in sidebar
        'api_client': None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value



def get_orchestrator() -> ReasonSQLOrchestrator:
    if st.session_state.orchestrator is None:
        st.session_state.orchestrator = ReasonSQLOrchestrator(verbose=False)
    return st.session_state.orchestrator


def check_rate_limit() -> tuple[bool, str]:
    """
    Check if we're within safe rate limits for demo.
    Returns (is_allowed, message)
    """
    now = datetime.now()
    
    # Reset counter every minute
    if st.session_state.last_query_time:
        time_since_last = now - st.session_state.last_query_time
        if time_since_last > timedelta(minutes=1):
            st.session_state.query_count_this_minute = 0
    
    # Allow max 4 queries per minute (safe for demo)
    if st.session_state.query_count_this_minute >= 4:
        seconds_to_wait = 60 - (now - st.session_state.last_query_time).seconds
        return False, f"⏳ Rate limit reached. Please wait {seconds_to_wait}s before next query."
    
    return True, ""


def update_rate_limit():
    """Update rate limit counters after a query."""
    st.session_state.last_query_time = datetime.now()
    st.session_state.query_count_this_minute += 1


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def find_agent_in_trace(agent_name: str, trace_actions: List[AgentAction]) -> Optional[Dict]:
    """Find agent's result in trace."""
    for action in trace_actions:
        if agent_name in action.agent_name:
            return {
                "output": action.output_summary,
                "input": action.input_summary,
                "reasoning": action.reasoning or ""
            }
    return None


def get_stage_status(stage: Dict, trace_actions: List[AgentAction]) -> AgentStatus:
    """Determine if a stage was executed."""
    for agent_name in stage["agents"]:
        result = find_agent_in_trace(agent_name, trace_actions)
        if result:
            return AgentStatus.DONE
    # Check if any action contains the stage key in its name (partial match)
    for action in trace_actions:
        for agent_name in stage["agents"]:
            if agent_name.lower() in action.agent_name.lower():
                return AgentStatus.DONE
    return AgentStatus.SKIPPED


def extract_llm_calls(trace: ReasoningTrace) -> int:
    """Extract LLM call count from trace."""
    max_calls = 0
    for action in trace.actions:
        if action.reasoning and "LLM calls" in action.reasoning:
            try:
                parts = action.reasoning.split(":")
                if len(parts) >= 2:
                    max_calls = max(max_calls, int(parts[-1].strip()))
            except:
                pass
    return max_calls if max_calls > 0 else 4


def render_step_card(step_num: int, action: AgentAction, compact: bool = False):
    """
    Render a single execution step with 3-section layout using native Streamlit components:
    1. INPUT (what the agent received)
    2. OUTPUT (what the agent produced)
    3. REASONING (why/how it made decisions)
    
    compact: If True, shows abbreviated view for Simple Mode
    """
    # Determine if LLM or rule-based
    is_llm = any(p["name"] in action.agent_name and p["is_llm"] for p in AGENT_PIPELINE)
    emoji = "🧠" if is_llm else "📦"
    badge_text = "LLM Agent" if is_llm else "Rule-Based"
    
    # Check if this is a key agent (highlight in Simple Mode)
    is_key_agent = action.agent_name in KEY_AGENTS_FOR_JUDGES
    
    # Extract content with fallbacks - show data as-is from backend
    input_text = action.input_summary if action.input_summary else "Not applicable"
    action_text = action.action if action.action else "Processing step"
    output_text = action.output_summary if action.output_summary else "Completed"
    reasoning_text = action.reasoning if action.reasoning else ("Deterministic step (no LLM reasoning)" if not is_llm else "No reasoning recorded")
    
    # Truncate helper
    def truncate(text, limit=300):
        return text if len(text) <= limit else text[:limit] + "..."
    
    # Create step card container
    with st.container():
        # Header row
        header_col1, header_col2 = st.columns([0.1, 0.9])
        with header_col1:
            st.markdown(f"## {emoji}")
        with header_col2:
            badge_color = "blue" if is_llm else "violet"
            key_badge = " ⭐" if is_key_agent else ""
            st.markdown(f"### Step {step_num}: {action.agent_name}{key_badge}")
            st.caption(f":{badge_color}[{badge_text}]")
        
        if compact:
            # COMPACT MODE for Simple Mode - single line summary
            with st.container(border=True):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.markdown("**Output:**")
                with col2:
                    st.markdown(truncate(output_text, 150))
        else:
            # FULL MODE - 3 Sections: Input | Output (top row), Reasoning (bottom full width)
            col1, col2 = st.columns(2)
            
            with col1:
                # INPUT Section
                st.markdown("##### 📥 Input")
                with st.container(border=True):
                    display_text = truncate(input_text, 200)
                    st.markdown(display_text)
                    if len(input_text) > 200:
                        with st.expander("Show full input"):
                            st.text(input_text)
            
            with col2:
                # OUTPUT Section
                st.markdown("##### 📤 Output")
                with st.container(border=True):
                    display_text = truncate(output_text, 250)
                    st.markdown(display_text)
                    if len(output_text) > 250:
                        with st.expander("Show full output"):
                            st.text(output_text)
            
            # REASONING Section (full width)
            st.markdown("##### 🤔 Reasoning")
            with st.container(border=True):
                display_text = truncate(reasoning_text, 400)
                st.markdown(display_text)
                if len(reasoning_text) > 400:
                    with st.expander("Show full reasoning"):
                        st.text(reasoning_text)
        
        st.divider()


def render_skipped_agent(step_num: int, agent_info: Dict):
    """
    Render a placeholder for an agent that was skipped during execution.
    """
    is_llm = agent_info["is_llm"]
    emoji = agent_info["emoji"]
    agent_name = agent_info["name"]
    badge_text = "LLM Agent" if is_llm else "Rule-Based"
    
    with st.container():
        # Header row
        header_col1, header_col2 = st.columns([0.1, 0.9])
        with header_col1:
            st.markdown(f"## {emoji}")
        with header_col2:
            st.markdown(f"### Step {step_num}: {agent_name}")
            st.caption(":gray[⏭️ Skipped - Not executed in this query]")
        
        # Simple message
        st.info("This agent was not needed for this query and was skipped.")
        
        st.divider()


# ============================================================
# VISUAL AGENT MAP (NEW - Horizontal Flow)
# ============================================================

def render_agent_map(trace_actions: Optional[List[AgentAction]] = None):
    """
    Render a horizontal visual agent map showing the pipeline flow.
    Each stage is a node with status indicator.
    """
    html_parts = ['<div class="agent-map">']
    
    for i, stage in enumerate(AGENT_MAP_STAGES):
        # Determine status
        if trace_actions:
            status = get_stage_status(stage, trace_actions)
        else:
            status = AgentStatus.PENDING
        
        # Status-based styling
        node_class = {
            AgentStatus.DONE: "agent-node-done",
            AgentStatus.RUNNING: "agent-node-running",
            AgentStatus.PENDING: "agent-node-pending",
            AgentStatus.SKIPPED: "agent-node-skipped",
        }.get(status, "agent-node-pending")
        
        # Type badge
        type_badge = '<span class="agent-type-badge badge-llm">LLM</span>' if stage["is_llm"] else '<span class="agent-type-badge badge-rule">Rule</span>'
        
        html_parts.append(f'''
            <div class="agent-node {node_class}">
                <span class="agent-emoji">{stage["emoji"]}</span>
                <span class="agent-label">{stage["label"]}</span>
                {type_badge}
            </div>
        ''')
        
        # Add arrow between nodes (not after last)
        if i < len(AGENT_MAP_STAGES) - 1:
            html_parts.append('<span class="flow-arrow">→</span>')
    
    html_parts.append('</div>')
    st.markdown(''.join(html_parts), unsafe_allow_html=True)


# ============================================================
# NAIVE COMPARISON PANEL
# ============================================================

def render_naive_comparison_panel():
    """
    Render side-by-side comparison of naive vs multi-agent results.
    
    Layout:
    - Header: "Why Multi-Agent Matters"
    - Left column: Naive baseline (red theme)
    - Right column: Multi-agent system (green theme)
    """
    naive_result = st.session_state.get('naive_result')
    response = st.session_state.get('last_response')
    
    if not naive_result or not response:
        return
    
    # Format the naive result for display
    naive_display = format_naive_result_for_display(naive_result)
    
    # Comparison header
    st.markdown('''
    <div class="comparison-header">
        <div class="comparison-header-text">
            ⚖️ COMPARISON MODE: Why Multi-Agent Reasoning Matters
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    # Side-by-side columns
    col_naive, col_multiagent = st.columns(2)
    
    # ===== LEFT: NAIVE BASELINE =====
    with col_naive:
        st.markdown('''
        <div class="panel-title naive-title">
            ❌ Naive Baseline
        </div>
        <div class="panel-subtitle">
            Single LLM call • No reasoning • No validation
        </div>
        ''', unsafe_allow_html=True)
        
        # Status badge
        status_class = f"naive-status-{naive_display['badge_type']}"
        st.markdown(f'''
        <span class="naive-status-badge {status_class}">{naive_display['status_label']}</span>
        ''', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Generated SQL
        st.markdown("**Generated SQL:**")
        if naive_display['sql'] and naive_display['sql'] != "No SQL generated":
            st.code(naive_display['sql'], language="sql")
        else:
            st.error("Failed to generate SQL")
        
        # Error message (if any)
        if naive_display['error']:
            st.error(f"**Error:** {naive_display['error']}")
        
        # Results preview
        if naive_display['is_success'] and naive_display['data_preview']:
            st.markdown(f"**Results:** {naive_display['row_count']} rows")
            import pandas as pd
            df = pd.DataFrame(naive_display['data_preview'])
            st.dataframe(df, use_container_width=True, hide_index=True)
        elif naive_display['is_success']:
            st.info("Query executed but returned 0 rows")
        
        # Limitations callout
        with st.expander("⚠️ Naive Approach Limitations", expanded=False):
            st.markdown("""
            - **No schema reasoning**: Doesn't explore relationships
            - **No clarification**: Guesses on ambiguous terms
            - **No validation**: Syntax errors hit the database
            - **No self-correction**: Fails permanently on first error
            """)
    
    # ===== RIGHT: MULTI-AGENT SYSTEM =====
    with col_multiagent:
        st.markdown('''
        <div class="panel-title multiagent-title">
            ✅ Multi-Agent System
        </div>
        <div class="panel-subtitle">
            12 agents • Schema reasoning • Self-correcting
        </div>
        ''', unsafe_allow_html=True)
        
        # Status badge (special handling for meta-queries)
        if response.is_meta_query:
            st.markdown('<span class="naive-status-badge naive-status-success">✅ Meta Query Resolved</span>', unsafe_allow_html=True)
        else:
            status = response.reasoning_trace.final_status
            if status == ExecutionStatus.SUCCESS:
                st.markdown('<span class="naive-status-badge naive-status-success">✅ Success</span>', unsafe_allow_html=True)
            else:
                st.markdown(f'<span class="naive-status-badge naive-status-error">❌ {status.value}</span>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Generated SQL (special handling for meta-queries)
        st.markdown("**Generated SQL:**")
        if response.is_meta_query:
            st.info("ℹ️ Intent-aware meta-query handling – no SQL execution by design")
            st.caption("The system explicitly reasons about schema without querying SQLite internals.")
        elif response.sql_used and response.sql_used != "No SQL needed (meta query)":
            st.code(response.sql_used, language="sql")
        else:
            st.info("No SQL needed (meta query)")
        
        # Answer
        st.markdown("**Answer:**")
        st.success(response.answer[:500] if response.answer else "No answer generated")
        
        # Results count (only for non-meta queries)
        if not response.is_meta_query and response.data_preview:
            st.markdown(f"**Results:** {len(response.data_preview)} rows")
            import pandas as pd
            df = pd.DataFrame(response.data_preview[:5])
            st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Advantages callout
        with st.expander("✨ Multi-Agent Advantages", expanded=False):
            st.markdown("""
            - **Schema exploration**: Understands table relationships
            - **Clarification**: Resolves ambiguous terms automatically
            - **Safety validation**: Blocks destructive queries
            - **Self-correction**: Retries with better SQL on errors
            """)
    
    st.markdown("---")


# ============================================================
# RESULT PANEL (MERGED: Answer + SQL + Metrics)
# ============================================================

def render_result_panel(response: FinalResponse):
    """
    Unified result panel with:
    - Hero answer card at top
    - Compact metrics row
    - Collapsible SQL
    """
    trace = response.reasoning_trace
    status = trace.final_status
    
    # Status badge (special handling for meta-queries)
    if response.is_meta_query:
        status_text = "✅ Meta Query Resolved"
        status_class = "status-success"
    else:
        status_config = {
            ExecutionStatus.SUCCESS: ("✅ Success", "status-success"),
            ExecutionStatus.EMPTY: ("📭 Empty Result", "status-empty"),
            ExecutionStatus.ERROR: ("❌ Error", "status-error"),
            ExecutionStatus.BLOCKED: ("🛡️ Blocked", "status-error"),
        }
        status_text, status_class = status_config.get(status, ("❓ Unknown", "status-empty"))
    
    # Hero Result Card
    st.markdown(f'''
    <div class="result-hero">
        <div class="result-status {status_class}">{status_text}</div>
        <div class="result-answer">{response.answer}</div>
    </div>
    ''', unsafe_allow_html=True)
    
    # Compact Metrics Row
    llm_calls = extract_llm_calls(trace)
    time_ms = trace.total_time_ms or 0
    
    st.markdown(f'''
    <div class="stat-row">
        <div class="stat-card">
            <div class="stat-value">⏱️ {time_ms:.0f}ms</div>
            <div class="stat-label">Time</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">🧠 {llm_calls}/8</div>
            <div class="stat-label">LLM Calls</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">🔄 {trace.correction_attempts}</div>
            <div class="stat-label">Retries</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">📋 {response.row_count}</div>
            <div class="stat-label">Rows</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">📦 {len(trace.actions)}</div>
            <div class="stat-label">Steps</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    # SQL Section (collapsible)
    if response.is_meta_query:
        with st.expander("ℹ️ **No SQL Generated**", expanded=False):
            st.info("Schema introspection – no SQL execution required")
            st.caption("This query was resolved through intent-aware meta-query handling.")
    else:
        with st.expander("📝 **View Generated SQL**", expanded=True):
            if trace.correction_attempts > 0:
                st.warning(f"🔄 Self-corrected {trace.correction_attempts} time(s)")
            st.code(response.sql_used, language="sql")
    
    # Warnings
    if response.warnings:
        for w in response.warnings:
            st.warning(w)


# ============================================================
# REASONING PANEL (MERGED: Agent Map + Timeline + Details)
# ============================================================

def render_reasoning_panel(response: FinalResponse):
    """
    Unified reasoning panel with:
    - Visual agent map at top
    - Detailed execution steps showing ALL 12 agents (executed or skipped)
    - Simple Mode: Shows only key steps by default, expandable for full details
    """
    trace = response.reasoning_trace
    judge_mode = st.session_state.get('judge_mode', True)
    
    # Visual Agent Map
    st.markdown("#### 🗺️ Pipeline Overview")
    render_agent_map(trace.actions)
    
    st.markdown("---")
    
    # Simple Mode vs Full Mode toggle is in sidebar
    if judge_mode:
        # JUDGE MODE: Highlight key steps only
        st.markdown("#### 🎯 Key Decision Points (Simple Mode)")
        st.caption("Showing the most important agents. Toggle 'Simple Mode' in sidebar for full details.")
        
        # Create a map of executed agents
        executed_agents = {action.agent_name: action for action in trace.actions}
        
        # Show only key agents
        step_num = 1
        for agent_info in AGENT_PIPELINE:
            agent_name = agent_info["name"]
            
            # Only show key agents in Simple Mode
            if agent_name not in KEY_AGENTS_FOR_JUDGES:
                continue
            
            if agent_name in executed_agents:
                render_step_card(step_num, executed_agents[agent_name], compact=True)
            else:
                render_skipped_agent(step_num, agent_info)
            
            step_num += 1
        
        # Expandable section for full trace
        with st.expander("📋 Show Full 12-Agent Trace", expanded=False):
            step_num = 1
            for agent_info in AGENT_PIPELINE:
                agent_name = agent_info["name"]
                
                if agent_name in executed_agents:
                    render_step_card(step_num, executed_agents[agent_name], compact=False)
                else:
                    render_skipped_agent(step_num, agent_info)
                
                step_num += 1
    else:
        # FULL MODE: Show all 12 agents
        st.markdown("#### 📋 Detailed Execution Steps (All 12 Agents)")
        st.caption("Showing all agents in pipeline - executed and skipped")
        
        # Create a map of executed agents
        executed_agents = {action.agent_name: action for action in trace.actions}
        
        # Show all 12 agents in order
        step_num = 1
        for agent_info in AGENT_PIPELINE:
            agent_name = agent_info["name"]
            
            if agent_name in executed_agents:
                render_step_card(step_num, executed_agents[agent_name], compact=False)
            else:
                render_skipped_agent(step_num, agent_info)
            
            step_num += 1
    
    # Legend
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.markdown("🧠 **LLM** = AI reasoning")
    col2.markdown("📦 **Rule** = Deterministic")
    col3.markdown("✓ **Done** • ⏭️ **Skipped**")


# ============================================================
# SIDEBAR (Enhanced with Demo Mode, Simple Mode, Query Categories)
# ============================================================

def render_sidebar():
    with st.sidebar:
        st.markdown("## ReasonSQL")
        st.caption("Multi-Agent NL→SQL System")
        
        st.markdown("---")
        
        # ===== DEMO MODE SECTION =====
        st.markdown("### 🎮 Demo Mode")
        
        demo_mode = st.toggle("Enable Demo Mode", value=st.session_state.demo_mode, 
                              help="Run 5 preset queries showcasing system capabilities")
        st.session_state.demo_mode = demo_mode
        
        if demo_mode:
            st.success("Demo Mode Active")
            st.caption("5 curated queries ready to demonstrate the system")
            
            # Show demo queries as buttons
            for i, demo in enumerate(DEMO_QUERIES):
                col1, col2 = st.columns([0.8, 0.2])
                with col1:
                    if st.button(f"{i+1}. {demo['category']}", key=f"demo_{i}", use_container_width=True):
                        st.session_state.current_query = demo['query']
                        st.session_state.demo_index = i
                        st.rerun()
                with col2:
                    st.caption(f"#{i+1}")
            
            st.caption(f"Query {st.session_state.demo_index + 1}/5 selected")
        
        st.markdown("---")
        
        # ===== JUDGE MODE SECTION =====
        st.markdown("### 🎯 Simple Mode")
        
        judge_mode = st.toggle("Simple Mode (Simplified)", value=st.session_state.judge_mode,
                               help="Show only key decision points. Disable for full 12-agent trace.")
        st.session_state.judge_mode = judge_mode
        
        if judge_mode:
            st.info("Showing key agents only")
            st.caption("IntentAnalyzer → SchemaExplorer → QueryPlanner → SafetyValidator → ResponseSynthesizer")
        else:
            st.warning("Full trace mode")
            st.caption("All 12 agents visible")
        
        st.markdown("---")
        
        # ===== COMPARISON MODE SECTION =====
        st.markdown("### ⚖️ Comparison Mode")
        
        compare_naive = st.toggle("Compare with Naive NL→SQL", value=st.session_state.compare_naive,
                                   help="Show side-by-side: single-shot baseline vs multi-agent system")
        st.session_state.compare_naive = compare_naive
        
        if compare_naive:
            st.warning("Comparison Active")
            st.caption("Shows WHY multi-agent reasoning matters")
        else:
            st.caption("Enable to see naive baseline failures")
        
        st.markdown("---")
        
        # ===== PROVIDER STATUS =====
        st.markdown("### 🤖 LLM Status")
        
        provider_status = st.session_state.get('provider_status', 'primary')
        query_count = st.session_state.get('query_count_this_minute', 0)
        
        if provider_status == 'primary':
            st.success("✅ Primary Provider (Gemini)")
        elif provider_status == 'fallback':
            st.warning("⚠️ Using Fallback (Groq)")
            st.caption("Primary provider quota exceeded")
        else:
            st.error("❌ Both providers exhausted")
        
        # Rate limit indicator
        rate_color = "green" if query_count < 3 else "orange" if query_count < 4 else "red"
        st.markdown(f"**Queries this minute:** :{rate_color}[{query_count}/4]")
        
        if query_count >= 3:
            st.caption("⚠️ Approaching rate limit")
        
        st.markdown("---")
        
        # ===== API MODE TOGGLE =====
        st.markdown("### 🔌 Backend Mode")
        use_api = st.toggle("Use FastAPI Backend", value=st.session_state.use_api_mode,
                            help="Route queries through FastAPI (http://localhost:8000) instead of direct orchestrator")
        st.session_state.use_api_mode = use_api
        
        if use_api:
            st.info("📡 API Mode Active")
            st.caption("Queries go to FastAPI → Orchestrator")
        else:
            st.caption("Direct mode: Orchestrator in-process")
        
        st.markdown("---")
        
        # Quick stats
        st.markdown("### ⚡ Quick Facts")
        col1, col2 = st.columns(2)
        col1.metric("Agents", "12")
        col2.metric("LLM Calls", "4-6")
        
        st.markdown("---")
        
        # Try These Queries - Categorized (when not in demo mode)
        if not demo_mode:
            st.markdown("### 🎯 Try These Queries")
            
            query_categories = {
                "📊 Simple": [
                    "Show me all customers",
                    "List all artists",
                ],
                "🔍 Meta": [
                    "What tables exist?",
                    "Show me the schema",
                ],
                "📈 Aggregate": [
                    "How many tracks are there?",
                    "Total revenue by country",
                ],
                "🔗 Join": [
                    "Top 5 artists by tracks",
                    "Customer purchases by genre",
                ],
                "❓ Ambiguous": [
                    "Show me recent orders",
                    "Popular items",
                ],
                "🧩 Complex": [
                    "Top customers with most purchases",
                    "Artists with no albums",
                ]
            }
            
            for category, queries in query_categories.items():
                with st.expander(f"**{category}**", expanded=False):
                    for q in queries:
                        if st.button(q, key=f"cat_{hash(category + q)}", use_container_width=True):
                            st.session_state.current_query = q
                            st.rerun()
            
            st.markdown("---")
        
        # Recent Queries
        if st.session_state.history:
            st.markdown("### 📜 Recent Queries")
            for item in reversed(st.session_state.history[-3:]):
                status_icon = "✅" if item['status'] == 'success' else "❌"
                time_text = f"{item['time']:.0f}ms" if 'time' in item else "N/A"
                
                st.markdown(f"""
                <div class="recent-query-card">
                    <div class="recent-query-status">{status_icon} {item['status'].upper()}</div>
                    <div class="recent-query-text">{item['query'][:40]}...</div>
                    <div class="recent-query-time">⏱️ {time_text}</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Technical Details
        st.markdown("### 🔧 Technical Details")
        st.caption("Database: Chinook SQLite")
        st.caption("LLM: Gemini + Groq fallback")
        st.caption("Framework: CrewAI")
        st.caption("Safe Rate: 4 req/min")


# ============================================================
# MAIN APP
# ============================================================

def main():
    init_session_state()
    render_sidebar()
    
    # ===== HERO HEADER =====
    st.markdown('''
    <div class="hero-header">
        <div class="hero-title">ReasonSQL</div>
        <div class="hero-subtitle">Natural Language → SQL with 12 Specialized AI Agents</div>
        <div class="hero-badge">✨ Quota-Optimized • 🛡️ Safety-Validated • 🔄 Self-Correcting</div>
    </div>
    ''', unsafe_allow_html=True)

    
    # ===== DEMO MODE BANNER =====
    if st.session_state.demo_mode:
        demo = DEMO_QUERIES[st.session_state.demo_index]
        st.info(f"""
        **🎮 Demo Mode Active** | Query {st.session_state.demo_index + 1}/5: **{demo['category']}**
        
        *{demo['description']}*
        """)
    
    # ===== QUERY INPUT =====
    col1, col2 = st.columns([6, 1])
    
    with col1:
        # Pre-fill with demo query if in demo mode
        default_query = st.session_state.current_query
        if st.session_state.demo_mode and not default_query:
            default_query = DEMO_QUERIES[st.session_state.demo_index]['query']
            st.session_state.current_query = default_query
        
        query = st.text_input(
            label="Query",
            value=default_query,
            placeholder="Ask anything about your database...",
            label_visibility="collapsed",
            disabled=st.session_state.is_processing
        )
    
    with col2:
        run = st.button("🚀 Run", type="primary", use_container_width=True,
                       disabled=st.session_state.is_processing or not query)
    
    # ===== RATE LIMIT CHECK =====
    can_run, rate_msg = check_rate_limit()
    if not can_run:
        st.warning(rate_msg)
    
    # ===== PROCESSING =====
    if run and query and can_run:
        st.session_state.is_processing = True
        st.session_state.current_query = query
        
        progress = st.empty()
        
        with progress.container():
            # Show animated agent map during processing
            st.markdown("#### ⏳ Processing through agent pipeline...")
            
            # Animated progress simulation
            prog_bar = st.progress(0)
            status_text = st.empty()
            
            steps = ["🎯 Intent", "📊 Schema", "📝 Planning", "⚙️ SQL", "🛡️ Safety", "🚀 Execute", "💬 Response"]
            
            for i, step in enumerate(steps):
                prog_bar.progress((i + 1) / len(steps))
                status_text.markdown(f"**{step}**...")
                time.sleep(0.1)
        
        try:
            # ===== RUN NAIVE BASELINE (if comparison mode is ON) =====
            if st.session_state.compare_naive:
                naive_progress = st.empty()
                with naive_progress.container():
                    st.markdown("#### ⚡ Running naive baseline (single LLM call)...")
                naive_result = run_naive_query(query)
                st.session_state.naive_result = naive_result
                naive_progress.empty()
            else:
                st.session_state.naive_result = None
            
            # ===== RUN MULTI-AGENT SYSTEM =====
            if st.session_state.use_api_mode:
                # API MODE: Call FastAPI endpoint
                if st.session_state.api_client is None:
                    st.session_state.api_client = ReasonSQLClient()
                
                api_response = st.session_state.api_client.query(query)
                
                # Convert API response to FinalResponse-like object for compatibility
                # Create a compatible trace object
                class APIReasoningTrace:
                    def __init__(self, api_trace):
                        self.actions = []
                        if api_trace:
                            for a in api_trace.actions:
                                self.actions.append(type('AgentAction', (), {
                                    'agent_name': a.agent_name,
                                    'action': 'Processed',
                                    'input_summary': 'API call',
                                    'output_summary': a.summary,
                                    'reasoning': a.detail,
                                    'timestamp': None
                                })())
                            self.final_status = ExecutionStatus(api_trace.final_status.value)
                            self.total_time_ms = api_trace.total_time_ms
                            self.correction_attempts = api_trace.correction_attempts
                        else:
                            self.final_status = ExecutionStatus.ERROR
                            self.total_time_ms = 0
                            self.correction_attempts = 0
                
                # Create FinalResponse-like object
                response = type('FinalResponse', (), {
                    'answer': api_response.answer,
                    'sql_used': api_response.sql_used or "No SQL",
                    'data_preview': api_response.data_preview,
                    'row_count': api_response.row_count,
                    'is_meta_query': api_response.is_meta_query,
                    'reasoning_trace': APIReasoningTrace(api_response.reasoning_trace),
                    'warnings': api_response.warnings or []
                })()
            else:
                # DIRECT MODE: Call orchestrator directly
                orchestrator = get_orchestrator()
                response = orchestrator.process_query(query)
            
            progress.empty()
            
            # Update rate limit counter
            update_rate_limit()
            
            # Check if fallback was used (from response metadata if available)
            if hasattr(response, 'execution_metrics') and response.execution_metrics:
                if response.execution_metrics.get('fallback_used'):
                    st.session_state.provider_status = 'fallback'
                    st.warning("⚠️ Primary provider quota exceeded. Switched to fallback provider (Groq).")
            
            st.session_state.last_response = response
            st.session_state.history.append({
                'query': query,
                'time': response.reasoning_trace.total_time_ms or 0,
                'status': response.reasoning_trace.final_status.value
            })
            
            # Auto-advance demo mode
            if st.session_state.demo_mode:
                if st.session_state.demo_index < len(DEMO_QUERIES) - 1:
                    st.toast(f"✅ Demo {st.session_state.demo_index + 1}/5 complete!")
            
        except Exception as e:
            progress.empty()
            error_msg = str(e).lower()
            
            # Handle quota/rate limit errors gracefully
            if "quota" in error_msg or "rate limit" in error_msg or "429" in error_msg:
                st.session_state.provider_status = 'fallback'
                st.error("⚠️ **Provider Quota Exceeded**")
                st.warning("The primary LLM provider has hit its rate limit. Please wait a moment and try again, or the system will automatically switch to the fallback provider.")
            else:
                st.error(f"❌ {str(e)}")
            
            st.session_state.is_processing = False
            return
        
        st.session_state.is_processing = False
        st.rerun()
    
    # ===== RESULTS =====
    if st.session_state.last_response:
        response = st.session_state.last_response
        
        st.markdown("---")
        
        # Show comparison panel if comparison mode is active
        if st.session_state.compare_naive and st.session_state.naive_result:
            render_naive_comparison_panel()
        
        # TWO MERGED TABS (instead of 5)
        tab_result, tab_reasoning = st.tabs(["📦 **Result**", "🧠 **Reasoning & Workflow**"])
        
        with tab_result:
            render_result_panel(response)
        
        with tab_reasoning:
            render_reasoning_panel(response)
        
        # Demo Mode: Next query button
        if st.session_state.demo_mode and st.session_state.demo_index < len(DEMO_QUERIES) - 1:
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("➡️ Next Demo Query", type="primary", use_container_width=True):
                    st.session_state.demo_index += 1
                    st.session_state.current_query = DEMO_QUERIES[st.session_state.demo_index]['query']
                    st.session_state.last_response = None
                    st.rerun()
    
    # ===== FOOTER =====
    st.markdown("---")
    mode_text = "Demo Mode" if st.session_state.demo_mode else "Interactive Mode"
    judge_text = "Judge View" if st.session_state.judge_mode else "Full Trace"
    compare_text = " | ⚖️ Comparison" if st.session_state.compare_naive else ""
    st.markdown(f'''
    <div style="text-align: center; color: #334155; font-size: 0.8rem; padding: 1rem;">
        Built with CrewAI • 12 Agents • 4-6 LLM Calls • Full Transparency<br>
        <span style="color: #667eea;">{mode_text} | {judge_text}{compare_text}</span>
    </div>
    ''', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
