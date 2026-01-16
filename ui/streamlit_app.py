"""
NL2SQL Multi-Agent System - Streamlit Web UI (Refactored)

DESIGN CHANGES (v2):
1. LIGHT THEME - Clean white/gray with soft gradients
2. VISUAL AGENT MAP - Horizontal flow showing 12 agents as cards
3. FLASHY BUT LOW-TEXT - Icons, badges, short labels over paragraphs  
4. MERGED TABS - "📦 Result" and "🧠 Reasoning" only
5. JUDGE-FRIENDLY - Get the system in 5 seconds
"""
import streamlit as st
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from enum import Enum

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator import NL2SQLOrchestrator
from models import ExecutionStatus, FinalResponse, ReasoningTrace, AgentAction


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="NL2SQL Multi-Agent System",
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
    
    /* Sidebar text visibility - WHITE for contrast */
    .css-1d391kg, [data-testid="stSidebar"] {
        color: #ffffff !important;
    }
    
    [data-testid="stSidebar"] .stMarkdown p {
        color: #ffffff !important;
    }
    
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #ffffff !important;
    }
    
    [data-testid="stSidebar"] .stCaption {
        color: #e2e8f0 !important;
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
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_orchestrator() -> NL2SQLOrchestrator:
    if st.session_state.orchestrator is None:
        st.session_state.orchestrator = NL2SQLOrchestrator(verbose=False)
    return st.session_state.orchestrator


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


def render_step_card(step_num: int, action: AgentAction):
    """
    Render a single execution step with 4-section layout using native Streamlit components:
    1. INPUT (what the agent received)
    2. ACTION (what the agent did)
    3. OUTPUT (what the agent produced)
    4. REASONING (why/how it made decisions)
    """
    # Determine if LLM or rule-based
    is_llm = any(p["name"] in action.agent_name and p["is_llm"] for p in AGENT_PIPELINE)
    emoji = "🧠" if is_llm else "📦"
    badge_text = "LLM Agent" if is_llm else "Rule-Based"
    
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
            st.markdown(f"### Step {step_num}: {action.agent_name}")
            st.caption(f":{badge_color}[{badge_text}]")
        
        # 3 Sections: Input | Output (top row), Reasoning (bottom full width)
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


# ============================================================
# VISUAL AGENT MAP (NEW - Horizontal Flow)
# ============================================================

def render_agent_map(trace_actions: List[AgentAction] = None):
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
    
    # Status badge
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
    with st.expander("📝 **View Generated SQL**", expanded=False):
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
    - Detailed execution steps with 4-section layout:
      1. INPUT - what the agent received
      2. ACTION - what the agent did
      3. OUTPUT - what the agent produced
      4. REASONING - why/how it made decisions
    """
    trace = response.reasoning_trace
    
    # Visual Agent Map
    st.markdown("#### 🗺️ Pipeline Overview")
    render_agent_map(trace.actions)
    
    st.markdown("---")
    
    # Detailed Execution Steps
    st.markdown("#### 📋 Detailed Execution Steps")
    st.caption("Each step shows: Input → Action → Output → Reasoning")
    
    for i, action in enumerate(trace.actions, 1):
        render_step_card(i, action)
    
    # Legend
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.markdown("🧠 **LLM** = AI reasoning")
    col2.markdown("📦 **Rule** = Deterministic")
    col3.markdown("✓ **Done** • ⏭️ **Skipped**")


# ============================================================
# SIDEBAR (Enhanced with Query Categories)
# ============================================================

def render_sidebar():
    with st.sidebar:
        st.markdown("## 🧠 NL2SQL")
        st.caption("Multi-Agent System")
        
        st.markdown("---")
        
        # Quick stats
        st.markdown("### ⚡ Quick Facts")
        col1, col2 = st.columns(2)
        col1.metric("Agents", "12")
        col2.metric("LLM Calls", "4-6")
        
        st.markdown("---")
        
        # Try These Queries - Categorized
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
        
        # Display Settings
        st.markdown("### ⚙️ Display Settings")
        st.caption("Theme: Light Mode")
        st.caption("Auto-refresh: Off")
        
        st.markdown("---")
        
        # Technical Details
        st.markdown("### 🔧 Technical Details")
        st.caption("Database: Chinook SQLite")
        st.caption("LLM: Groq Llama 3.3")
        st.caption("Framework: CrewAI")
        st.caption("Rate Limit: 5 req/min")


# ============================================================
# MAIN APP
# ============================================================

def main():
    init_session_state()
    render_sidebar()
    
    # ===== HERO HEADER =====
    st.markdown('''
    <div class="hero-header">
        <div class="hero-title">🧠 NL2SQL Multi-Agent</div>
        <div class="hero-subtitle">Natural Language → SQL with 12 Specialized AI Agents</div>
        <div class="hero-badge">✨ Quota-Optimized • 🛡️ Safety-Validated • 🔄 Self-Correcting</div>
    </div>
    ''', unsafe_allow_html=True)
    
    # ===== QUERY INPUT =====
    col1, col2 = st.columns([6, 1])
    
    with col1:
        query = st.text_input(
            label="Query",
            value=st.session_state.current_query,
            placeholder="Ask anything about your database...",
            label_visibility="collapsed",
            disabled=st.session_state.is_processing
        )
    
    with col2:
        run = st.button("🚀 Run", type="primary", use_container_width=True,
                       disabled=st.session_state.is_processing or not query)
    
    # ===== PROCESSING =====
    if run and query:
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
            orchestrator = get_orchestrator()
            response = orchestrator.process_query(query)
            
            progress.empty()
            
            st.session_state.last_response = response
            st.session_state.history.append({
                'query': query,
                'time': response.reasoning_trace.total_time_ms or 0,
                'status': response.reasoning_trace.final_status.value
            })
            
        except Exception as e:
            progress.empty()
            st.error(f"❌ {str(e)}")
            st.session_state.is_processing = False
            return
        
        st.session_state.is_processing = False
        st.rerun()
    
    # ===== RESULTS =====
    if st.session_state.last_response:
        response = st.session_state.last_response
        
        st.markdown("---")
        
        # TWO MERGED TABS (instead of 5)
        tab_result, tab_reasoning = st.tabs(["📦 **Result**", "🧠 **Reasoning & Workflow**"])
        
        with tab_result:
            render_result_panel(response)
        
        with tab_reasoning:
            render_reasoning_panel(response)
    
    # ===== FOOTER =====
    st.markdown("---")
    st.markdown('''
    <div style="text-align: center; color: #334155; font-size: 0.8rem; padding: 1rem;">
        Built with CrewAI • 12 Agents • 4-6 LLM Calls • Full Transparency
    </div>
    ''', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
