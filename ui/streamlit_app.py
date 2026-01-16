"""
Streamlit Web UI for NL2SQL Multi-Agent System.
Provides an interactive web interface with reasoning trace visualization.
"""
import streamlit as st
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator import NL2SQLOrchestrator
from models import ExecutionStatus, FinalResponse


# Page configuration
st.set_page_config(
    page_title="NL2SQL Multi-Agent System",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .agent-step {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
        border-left: 4px solid #1E88E5;
    }
    .sql-box {
        background-color: #1E1E1E;
        color: #D4D4D4;
        padding: 1rem;
        border-radius: 0.5rem;
        font-family: 'Consolas', monospace;
    }
    .success-box {
        background-color: #E8F5E9;
        border-left: 4px solid #4CAF50;
        padding: 1rem;
        border-radius: 0.5rem;
    }
    .error-box {
        background-color: #FFEBEE;
        border-left: 4px solid #F44336;
        padding: 1rem;
        border-radius: 0.5rem;
    }
    .warning-box {
        background-color: #FFF3E0;
        border-left: 4px solid #FF9800;
        padding: 1rem;
        border-radius: 0.5rem;
    }
    .metric-card {
        background-color: #E3F2FD;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if 'history' not in st.session_state:
        st.session_state.history = []
    if 'orchestrator' not in st.session_state:
        st.session_state.orchestrator = None


def create_orchestrator():
    """Create or return existing orchestrator."""
    if st.session_state.orchestrator is None:
        with st.spinner("Initializing agents..."):
            st.session_state.orchestrator = NL2SQLOrchestrator(verbose=False)
    return st.session_state.orchestrator


def display_reasoning_trace(response: FinalResponse):
    """Display the reasoning trace in an expandable format."""
    trace = response.reasoning_trace
    
    st.subheader("🧠 Reasoning Trace")
    
    for i, action in enumerate(trace.actions, 1):
        with st.expander(f"Step {i}: {action.agent_name}", expanded=(i == len(trace.actions))):
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.markdown(f"**Action:** {action.action}")
                if action.timestamp:
                    st.markdown(f"**Time:** {action.timestamp}")
            
            with col2:
                st.markdown("**Input:**")
                st.text(action.input_summary[:200])
                st.markdown("**Output:**")
                st.text(action.output_summary[:300])
            
            if action.reasoning:
                st.markdown("**Reasoning:**")
                st.info(action.reasoning)


def display_metrics(response: FinalResponse):
    """Display execution metrics."""
    trace = response.reasoning_trace
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("⏱️ Total Time", f"{trace.total_time_ms:.0f} ms")
    
    with col2:
        st.metric("🔄 Corrections", trace.correction_attempts)
    
    with col3:
        status_emoji = {
            ExecutionStatus.SUCCESS: "✅",
            ExecutionStatus.EMPTY: "📭",
            ExecutionStatus.ERROR: "❌",
            ExecutionStatus.VALIDATION_FAILED: "⚠️"
        }
        st.metric("📊 Status", f"{status_emoji.get(trace.final_status, '')} {trace.final_status.value}")
    
    with col4:
        st.metric("📋 Rows", response.row_count)


def display_sql(sql: str):
    """Display generated SQL with syntax highlighting."""
    st.subheader("📝 Generated SQL")
    st.code(sql, language="sql")


def display_answer(response: FinalResponse):
    """Display the final answer."""
    trace = response.reasoning_trace
    
    st.subheader("💡 Answer")
    
    if trace.final_status == ExecutionStatus.SUCCESS:
        st.success(response.answer)
    elif trace.final_status == ExecutionStatus.EMPTY:
        st.info(response.answer)
    elif trace.final_status == ExecutionStatus.ERROR:
        st.error(response.answer)
    else:
        st.warning(response.answer)
    
    if response.warnings:
        for warning in response.warnings:
            st.warning(f"⚠️ {warning}")


def sidebar():
    """Create the sidebar with controls and information."""
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/database.png", width=80)
        st.title("NL2SQL System")
        st.markdown("---")
        
        st.subheader("📚 Example Queries")
        example_queries = [
            "How many customers are from Brazil?",
            "What tables exist in this database?",
            "Which 5 artists have the most tracks?",
            "Total revenue by country, sorted highest first",
            "Show me recent orders",
            "List all albums by AC/DC",
            "Customers who never made a purchase",
        ]
        
        for query in example_queries:
            if st.button(query, key=f"example_{hash(query)}", use_container_width=True):
                st.session_state.current_query = query
        
        st.markdown("---")
        
        st.subheader("ℹ️ About")
        st.markdown("""
        This system uses **7 specialized AI agents** to:
        - 🔍 Explore database schema
        - 🎯 Analyze query intent
        - 📝 Plan and generate SQL
        - 🚀 Execute safely
        - 🔄 Self-correct on errors
        - 💬 Synthesize responses
        """)
        
        st.markdown("---")
        
        st.subheader("📊 Query History")
        if st.session_state.history:
            for i, item in enumerate(reversed(st.session_state.history[-5:])):
                with st.expander(f"{item['query'][:30]}...", expanded=False):
                    st.text(f"Time: {item['time']:.0f}ms")
                    st.text(f"Status: {item['status']}")


def main():
    """Main application entry point."""
    init_session_state()
    sidebar()
    
    # Main header
    st.markdown('<div class="main-header">🔍 NL2SQL Multi-Agent System</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Convert Natural Language to SQL with Intelligent Reasoning</div>', unsafe_allow_html=True)
    
    # Query input
    col1, col2 = st.columns([5, 1])
    
    with col1:
        default_query = st.session_state.get('current_query', '')
        query = st.text_input(
            "Ask a question about your database:",
            value=default_query,
            placeholder="e.g., How many customers are from Brazil?",
            key="query_input"
        )
    
    with col2:
        st.write("")  # Spacing
        st.write("")  # Spacing
        submit = st.button("🚀 Submit", type="primary", use_container_width=True)
    
    # Process query
    if submit and query:
        orchestrator = create_orchestrator()
        
        # Create a progress indicator
        progress_placeholder = st.empty()
        
        with progress_placeholder.container():
            with st.spinner("🤔 Processing your query..."):
                # Show step-by-step progress
                step_placeholder = st.empty()
                steps = [
                    "📊 Exploring database schema...",
                    "🎯 Analyzing query intent...",
                    "📝 Planning query strategy...",
                    "⚙️ Generating SQL...",
                    "🚀 Executing query...",
                    "💬 Synthesizing response..."
                ]
                
                for step in steps:
                    step_placeholder.info(step)
                    time.sleep(0.3)
                
                try:
                    response = orchestrator.process_query(query)
                    
                    # Add to history
                    st.session_state.history.append({
                        'query': query,
                        'time': response.reasoning_trace.total_time_ms,
                        'status': response.reasoning_trace.final_status.value
                    })
                    
                    step_placeholder.empty()
                    
                except Exception as e:
                    st.error(f"Error processing query: {str(e)}")
                    return
        
        progress_placeholder.empty()
        
        # Display results in tabs
        tab1, tab2, tab3 = st.tabs(["📊 Results", "🧠 Reasoning Trace", "📈 Metrics"])
        
        with tab1:
            display_sql(response.sql_used)
            display_answer(response)
        
        with tab2:
            display_reasoning_trace(response)
        
        with tab3:
            display_metrics(response)
            
            # Additional charts/visualizations could go here
            if response.reasoning_trace.actions:
                st.subheader("Agent Activity")
                agent_data = {}
                for action in response.reasoning_trace.actions:
                    agent_data[action.agent_name] = agent_data.get(action.agent_name, 0) + 1
                
                st.bar_chart(agent_data)
    
    elif submit:
        st.warning("Please enter a question.")
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #888;'>"
        "Built with CrewAI • Multi-Agent Architecture • Safe SQL Execution"
        "</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
