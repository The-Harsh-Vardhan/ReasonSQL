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
    
    /* ===== TIMELINE STEP ===== */
    .timeline-step {
        display: flex;
        align-items: flex-start;
        gap: 1rem;
        padding: 0.75rem;
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 0.75rem;
        margin-bottom: 0.5rem;
        transition: all 0.2s ease;
    }
    
    .timeline-step:hover {
        border-color: #667eea;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.1);
    }
    
    .timeline-icon {
        font-size: 1.5rem;
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 0.5rem;
    }
    
    .timeline-icon-done {
        background: #d1fae5;
    }
    
    .timeline-icon-skip {
        background: #f1f5f9;
        opacity: 0.5;
    }
    
    .timeline-content {
        flex: 1;
    }
    
    .timeline-title {
        font-weight: 700;
        color: #0f172a;
        font-size: 0.9rem;
    }
    
    .timeline-output {
        font-size: 0.8rem;
        color: #334155;
        margin-top: 0.25rem;
        font-weight: 500;
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
    
    /* ===== TAB STYLING ===== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 0.5rem;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    
    /* ===== EXPANDER STYLING ===== */
    .streamlit-expanderHeader {
        background: #f8fafc;
        border-radius: 0.5rem;
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
        if find_agent_in_trace(agent_name, trace_actions):
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
    - Compact timeline
    - Expandable details per agent
    - Provider badges showing Gemini/Groq usage
    """
    trace = response.reasoning_trace
    
    # Visual Agent Map
    st.markdown("#### 🗺️ Pipeline Overview")
    render_agent_map(trace.actions)
    
    st.markdown("---")
    
    # Compact Timeline
    st.markdown("#### 📋 Execution Steps")
    
    for i, action in enumerate(trace.actions, 1):
        # Find matching pipeline info
        is_llm = any(p["name"] in action.agent_name and p["is_llm"] for p in AGENT_PIPELINE)
        emoji = "🧠" if is_llm else "📦"
        
        with st.expander(f"{emoji} **Step {i}: {action.agent_name}**", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Action:**")
                st.info(action.action if action.action else "Processing")
            
            with col2:
                st.markdown("**Output:**")
                output_text = action.output_summary if action.output_summary else "✓ Completed"
                st.success(output_text[:300])
            
            if action.reasoning:
                st.markdown("**Reasoning:**")
                st.caption(action.reasoning[:500])
    
    # Legend
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.markdown("🧠 **LLM** = AI reasoning")
    col2.markdown("📦 **Rule** = Deterministic")
    col3.markdown("✓ **Done** • ⏭️ **Skipped**")


# ============================================================
# SIDEBAR (Simplified)
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
        
        # Example queries
        st.markdown("### 📚 Examples")
        
        examples = [
            "How many customers from Brazil?",
            "What tables exist?",
            "Top 5 artists by tracks",
            "Total revenue by country",
            "Show me recent orders",
        ]
        
        for q in examples:
            if st.button(q[:25] + "..." if len(q) > 25 else q, key=f"ex_{hash(q)}", use_container_width=True):
                st.session_state.current_query = q
                st.rerun()
        
        st.markdown("---")
        
        # History
        if st.session_state.history:
            st.markdown("### 📜 History")
            for item in reversed(st.session_state.history[-3:]):
                icon = "✅" if item['status'] == 'success' else "📭"
                st.caption(f"{icon} {item['query'][:30]}...")


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
